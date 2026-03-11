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
import logging
import os
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
    import random

    if service_type == "legalization":
        # Shared check: try up to 4 random users, share result with all
        candidates = random.sample(users, min(4, len(users)))
        decrypt_failures = 0
        attempt_failures = 0
        for u in candidates:
            if not u.get("email_encrypted"):
                continue
            try:
                email = decrypt_credential(u["email_encrypted"])
                pw    = decrypt_credential(u["password_encrypted"])
            except Exception as exc:
                logger.warning(f"Decrypt failed for user {u['user_id']}: {exc}")
                decrypt_failures += 1
                continue

            res = await tls_checker.check_branch(
                branch_url=branch_url,
                tls_email=email,
                tls_password=pw,
                branch_name=branch_name,
                service_type=service_type,
            )
            err = res.get("error", "")
            if _is_captcha_failure(err):
                logger.warning(f"[{branch_name}] Captcha blocked for user {u['user_id']} — trying next")
                attempt_failures += 1
                continue
            if _is_login_failure(err):
                logger.warning(f"[{branch_name}] Login failed for user {u['user_id']}: {err}")
                attempt_failures += 1
                continue
            return res
        if decrypt_failures > 0 and attempt_failures == 0:
            error_msg = (f"Credential decryption failed for {decrypt_failures} user(s) — "
                         "ensure ENCRYPTION_KEY in .env.worker matches the server key")
        else:
            error_msg = "All attempts failed"
        return {"slots_available": False, "slot_details": None, "error": error_msg, "duration": 0}

    else:
        # Visa: individual check per user — return first result (worker posts each individually)
        results = []
        for u in users:
            if not u.get("email_encrypted"):
                continue
            try:
                email = decrypt_credential(u["email_encrypted"])
                pw    = decrypt_credential(u["password_encrypted"])
            except Exception as exc:
                logger.warning(f"Decrypt failed for user {u['user_id']}: {exc}")
                continue
            res = await tls_checker.check_branch(
                branch_url=branch_url,
                tls_email=email,
                tls_password=pw,
                branch_name=branch_name,
                service_type=service_type,
            )
            results.append(res)
        # Return first non-error result, or the last result
        for r in results:
            if not r.get("error"):
                return r
        return results[-1] if results else {"slots_available": False, "slot_details": None, "error": "No users", "duration": 0}


async def check_cycle():
    """One full check cycle: fetch jobs → run checks → post results."""
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
            logger.error(f"Failed to fetch jobs from Fly.io: {exc}")
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
        branch_id   = job["branch_id"]
        branch_name = job["branch_name"]
        service_type = job["service_type"]
        logger.info(f"Checking [{branch_name}] ({service_type}) — {len(job['users'])} user(s)")

        try:
            res = await run_check(job)
        except Exception as exc:
            logger.error(f"[{branch_name}] Check crashed: {exc}", exc_info=True)
            res = {"slots_available": False, "slot_details": None, "error": str(exc), "duration": 0}

        # Build logs: banner + checker step logs
        banner = [{"level": "info", "message": f"Worker checking [{branch_name}] ({service_type}) — {len(job['users'])} user(s)"}]
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
        }
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


async def _poll_force_run_signal() -> bool:
    """Ask the backend if the admin has requested a force-run. Returns True and clears the flag."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{FLY_BACKEND_URL}/api/monitoring/worker/signal", headers=HEADERS)
            r.raise_for_status()
            return r.json().get("force_run", False)
    except Exception:
        return False


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
            if await _poll_force_run_signal():
                logger.info("Force-run signal received from admin panel — starting immediate cycle")
                break


if __name__ == "__main__":
    asyncio.run(main())
