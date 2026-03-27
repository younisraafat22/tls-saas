"""
TLS Monitoring Worker — runs on the LOCAL LAPTOP.

Architecture:
  Fly.io  →  hosts FastAPI (auth, payments, dashboard, license checks) — WORKER_MODE=true
  Laptop  →  runs this script, polls /api/worker/jobs, runs Selenium, posts results back

Setup:
  1. Set FLY_BACKEND_URL in .env.worker (e.g. https://backend-cold-sound-6496.fly.dev)
  2. Set WORKER_SECRET in .env.worker — must match the Fly.io WORKER_SECRET env var
  3. Run:  python worker.py

The worker loops every CHECK_INTERVAL_MINUTES (default 30), fetches jobs, runs checks,
posts results.  It uses the same checker code already in app/services/.
"""

import asyncio
import base64
import logging
import os
import queue as _queue
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load worker-specific env file first, then fall back to .env
load_dotenv(Path(__file__).parent / ".env.worker", override=True)
load_dotenv(Path(__file__).parent / ".env")

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker")

FLY_BACKEND_URL = os.environ.get("FLY_BACKEND_URL", "").rstrip("/")
WORKER_SECRET   = os.environ.get("WORKER_SECRET", "")
CHECK_INTERVAL  = int(os.environ.get("CHECK_INTERVAL_MINUTES", "30")) * 60  # seconds

if not FLY_BACKEND_URL:
    logger.error("FLY_BACKEND_URL not set in .env.worker — exiting")
    sys.exit(1)
if not WORKER_SECRET:
    logger.error("WORKER_SECRET not set in .env.worker — exiting")
    sys.exit(1)

HEADERS = {
    "Content-Type": "application/json",
    "X-Worker-Secret": WORKER_SECRET,
}

# ── Real-time log streaming ──────────────────────────────────────────────────
# Intercepts checker/visa_checker_sb log records during a check cycle and
# streams them to the backend immediately so the admin panel shows live progress.

_log_stream_queue: _queue.Queue = _queue.Queue()
_streaming_active = False
_STREAM_LOGGER_NAMES = {"checker", "visa_checker_sb"}


class _WorkerStreamHandler(logging.Handler):
    """Puts checker log records into the stream queue (thread-safe)."""
    def emit(self, record):
        if not _streaming_active or record.name not in _STREAM_LOGGER_NAMES:
            return
        level = (
            "error" if record.levelno >= logging.ERROR
            else "warn" if record.levelno >= logging.WARNING
            else "info"
        )
        _log_stream_queue.put_nowait({"level": level, "message": record.getMessage()})


_stream_handler = _WorkerStreamHandler()
logging.getLogger().addHandler(_stream_handler)


async def _drain_log_stream(branch: str = ""):
    """Background task: drain the log queue and POST each entry to the backend."""
    async with httpx.AsyncClient(timeout=5) as client:
        while True:
            try:
                try:
                    entry = _log_stream_queue.get_nowait()
                except _queue.Empty:
                    await asyncio.sleep(0.2)
                    continue
                entry["branch"] = branch
                try:
                    await client.post(
                        f"{FLY_BACKEND_URL}/api/monitoring/worker/log",
                        json=entry,
                        headers=HEADERS,
                    )
                except Exception:
                    pass
            except asyncio.CancelledError:
                # Drain any remaining entries before exiting
                while not _log_stream_queue.empty():
                    try:
                        entry = _log_stream_queue.get_nowait()
                        entry["branch"] = branch
                        await client.post(
                            f"{FLY_BACKEND_URL}/api/monitoring/worker/log",
                            json=entry,
                            headers=HEADERS,
                        )
                    except Exception:
                        pass
                raise


async def run_check(job: dict) -> dict:
    """
    Run a single branch check using the existing checker service.
    Returns the result dict.
    """
    branch_url   = job["branch_url"]
    branch_name  = job["branch_name"]
    service_type = job["service_type"]
    users        = job["users"]

    # Import checker here so we only need the Selenium deps on the laptop
    from app.services.checker import tls_checker, decrypt_credential
    from app.services.scheduler import _is_login_failure, _is_captcha_failure

    # Both legalization and visa: check every subscriber individually.
    # For legalization, the slot result is the same for all users, but we still
    # try each in turn so bad/blocked credentials don't block everyone else.
    results = []
    last_login_failure_result = None  # preserve so we can return its real error
    total = len(users)
    for i, u in enumerate(users, 1):
        if not u.get("email_encrypted"):
            continue
        user_label = u.get("user_email", f"user#{u['user_id']}")
        try:
            email = decrypt_credential(u["email_encrypted"])
            pw    = decrypt_credential(u["password_encrypted"])
        except Exception as exc:
            logger.warning(f"[{branch_name}] Decrypt failed for {user_label}: {exc}")
            continue

        logger.info(f"[{branch_name}] Checking user: {user_label} ({i}/{total})")
        # Also push directly to stream queue so the admin panel shows it in real-time
        if _streaming_active:
            _log_stream_queue.put_nowait({"level": "info", "message": f"Checking user: {user_label} ({i}/{total})"})
        res = await tls_checker.check_branch(
            branch_url=branch_url,
            tls_email=email,
            tls_password=pw,
            branch_name=branch_name,
            service_type=service_type,
        )
        err = res.get("error", "")
        if _is_captcha_failure(err):
            logger.warning(f"[{branch_name}] Captcha blocked for {user_label} — trying next")
            continue
        if _is_login_failure(err):
            logger.warning(f"[{branch_name}] Login failed for {user_label}: {err}")
            last_login_failure_result = res  # save so we can notify the user
            continue
        results.append(res)

    # Return first clean (no-error) result; fall back to last result.
    # If everything was a login failure, return that result (with the real error)
    # so _persist_and_notify can detect it and send an error email to the user.
    for r in results:
        if not r.get("error"):
            return r
    if results:
        return results[-1]
    if last_login_failure_result:
        return last_login_failure_result
    return {"slots_available": False, "slot_details": None, "error": "All attempts failed", "duration": 0}


async def check_cycle():
    """One full check cycle: fetch jobs → run checks → post results."""
    global _streaming_active
    now = datetime.now(timezone.utc)
    logger.info("=== Worker check cycle starting ===")
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{FLY_BACKEND_URL}/api/monitoring/worker/jobs", headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", [])
            # Use interval from DB if provided (admin can change it via the panel)
            db_interval = data.get("interval_minutes")
            if db_interval and isinstance(db_interval, int) and db_interval >= 1:
                global CHECK_INTERVAL
                CHECK_INTERVAL = db_interval * 60
        except Exception as exc:
            # Log with full traceback and response body if available
            resp_body = ""
            try:
                resp_body = resp.text[:500]
            except Exception:
                pass
            logger.error(
                f"Failed to fetch jobs from Fly.io: {type(exc).__name__}: {exc!r} | body: {resp_body!r}",
                exc_info=True,
            )
            return

    # Post heartbeat so the admin panel shows last/next run times
    next_run_at = (now + timedelta(seconds=CHECK_INTERVAL)).isoformat()
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(
                f"{FLY_BACKEND_URL}/api/monitoring/worker/heartbeat",
                json={"last_run_at": now.isoformat(), "next_run_at": next_run_at,
                      "interval_minutes": CHECK_INTERVAL // 60},
                headers=HEADERS,
            )
        except Exception as exc:
            logger.warning(f"Heartbeat failed (non-fatal): {exc}")

    logger.info(f"Got {len(jobs)} job(s) to run")

    for job in jobs:
        branch_id    = job["branch_id"]
        branch_name  = job["branch_name"]
        service_type = job["service_type"]
        n_users = len(job["users"])
        user_emails = ", ".join(u.get("user_email", f"user#{u['user_id']}") for u in job["users"])
        logger.info(f"Checking [{branch_name}] ({service_type}) — {n_users} subscriber(s): {user_emails}")

        # Clear any stale queue entries, then enable real-time log streaming
        while not _log_stream_queue.empty():
            try:
                _log_stream_queue.get_nowait()
            except _queue.Empty:
                break
        _streaming_active = True
        stream_task = asyncio.create_task(_drain_log_stream(branch=branch_name))

        try:
            res = await run_check(job)
        except Exception as exc:
            logger.error(f"[{branch_name}] Check crashed: {exc}", exc_info=True)
            res = {"slots_available": False, "slot_details": None, "error": str(exc), "duration": 0}
        finally:
            # Stop streaming: let queue flush, then cancel
            _streaming_active = False
            await asyncio.sleep(0.5)
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass

        # Build logs: banner + checker step logs (logs already streamed live, skip replay)
        n_users = len(job["users"])
        user_emails = ", ".join(u.get("user_email", f"user#{u['user_id']}") for u in job["users"])
        banner = [{"level": "info", "message": f"Worker checking [{branch_name}] ({service_type}) — {n_users} subscriber(s): {user_emails}"}]
        step_logs = res.get("logs") or []
        raw_details = res.get("slot_details")
        # API expects slot_details as str | None; the checker may return a dict
        if isinstance(raw_details, dict):
            import json as _json
            raw_details = _json.dumps(raw_details, ensure_ascii=False)
        payload = {
            "branch_id": branch_id,
            "slots_available": res.get("slots_available", False),
            "slot_details": raw_details,
            "error": res.get("error", ""),
            "duration_seconds": res.get("duration", 0),
            "source": "worker",
            "logs": banner + step_logs,
            "skip_log_replay": True,  # logs already streamed in real-time
        }
        screenshot_bytes = res.get("screenshot")
        if isinstance(screenshot_bytes, (bytes, bytearray)):
            payload["screenshot_b64"] = base64.b64encode(screenshot_bytes).decode()
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r2 = await client.post(
                    f"{FLY_BACKEND_URL}/api/monitoring/worker/result",
                    json=payload,
                    headers=HEADERS,
                )
                r2.raise_for_status()
                logger.info(f"[{branch_name}] Result posted: slots={res.get('slots_available')}")
            except Exception as exc:
                logger.error(f"[{branch_name}] Failed to post result: {exc}")

    logger.info("=== Worker check cycle complete ===")


async def _poll_worker_signal() -> dict:
    """Ask backend for worker control signals. Flags are cleared server-side when read."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{FLY_BACKEND_URL}/api/monitoring/worker/signal", headers=HEADERS)
            r.raise_for_status()
            data = r.json() or {}
            return {
                "force_run": bool(data.get("force_run")),
                "restart_laptop": bool(data.get("restart_laptop")),
            }
    except Exception:
        return {"force_run": False, "restart_laptop": False}


def _restart_host_machine():
    """Request OS restart on the worker machine."""
    if os.name == "nt":
        logger.warning("Restart signal received - rebooting Windows worker laptop in 5 seconds")
        subprocess.Popen(["shutdown", "/r", "/t", "5", "/f"])
        return
    logger.warning("Restart signal received, but automatic restart is only implemented for Windows workers")


async def main():
    logger.info(f"Worker started — polling {FLY_BACKEND_URL} every {CHECK_INTERVAL // 60} min")
    while True:
        try:
            await check_cycle()
        except Exception as exc:
            logger.error(f"Unexpected error in check cycle: {exc}", exc_info=True)
        logger.info(f"Sleeping {CHECK_INTERVAL // 60} min until next cycle (force-run checked every 30s)...")
        slept = 0
        while slept < CHECK_INTERVAL:
            await asyncio.sleep(30)
            slept += 30
            signals = await _poll_worker_signal()
            if signals.get("restart_laptop"):
                _restart_host_machine()
                # Give the OS a moment to process reboot command.
                await asyncio.sleep(10)
            if signals.get("force_run"):
                logger.info("Force-run signal received from admin panel - starting immediate cycle")
                break


if __name__ == "__main__":
    asyncio.run(main())
