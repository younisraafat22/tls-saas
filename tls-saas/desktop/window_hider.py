"""
Chrome Window Hider — make Chrome practically invisible while keeping it
"visible" from the OS/anti-bot perspective.

Uses Win32 layered-window transparency (alpha=1 out of 255) so the window
is technically rendered on-screen at normal coordinates.  Anti-bot systems
(Cloudflare Turnstile, Google reCAPTCHA) see a fully visible, non-minimized,
non-off-screen window and pass all checks.  The human eye cannot perceive
alpha=1 so the Chrome window is effectively invisible to the user.

The window is also:
  • removed from the taskbar  (WS_EX_TOOLWINDOW)
  • placed behind all other windows (HWND_BOTTOM z-order)
  • kept at normal screen position (0,0) so pyautogui clicks can reach it

During CAPTCHA-solving the window is temporarily made opaque (alpha=255)
so that if the user happens to glance at the screen they can see progress.
After CAPTCHA passes the window goes transparent again.
"""

import ctypes
import ctypes.wintypes as wintypes
import time
import sys

# ── Win32 constants ─────────────────────────────────────────────────
GWL_EXSTYLE       = -20
WS_EX_LAYERED     = 0x00080000
WS_EX_TOOLWINDOW  = 0x00000080
WS_EX_APPWINDOW   = 0x00040000
LWA_ALPHA         = 0x00000002
SWP_NOMOVE        = 0x0002
SWP_NOSIZE        = 0x0001
SWP_NOACTIVATE    = 0x0010
HWND_BOTTOM       = 1
HWND_TOPMOST      = -1
HWND_NOTOPMOST    = -2

user32 = ctypes.windll.user32

# ── Low-level helpers ───────────────────────────────────────────────

def _get_ex_style(hwnd: int) -> int:
    return user32.GetWindowLongW(hwnd, GWL_EXSTYLE)


def _set_ex_style(hwnd: int, style: int):
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def _set_alpha(hwnd: int, alpha: int):
    """Set window transparency.  alpha: 0 = fully transparent, 255 = opaque."""
    user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)


def _set_z_order(hwnd: int, insert_after: int):
    user32.SetWindowPos(
        hwnd, insert_after,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )


# ── Chrome window discovery ────────────────────────────────────────

def get_chrome_hwnds() -> set[int]:
    """Return the set of all visible Chrome window handles."""
    results: set[int] = set()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        # Chrome's main browser window class name
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "Chrome_WidgetWin_1":
            results.add(hwnd)
        return True

    user32.EnumWindows(_cb, 0)
    return results


def find_new_chrome_hwnd(before: set[int], timeout: float = 10.0) -> int | None:
    """Wait for a new Chrome window to appear and return its hwnd."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        after = get_chrome_hwnds()
        new = after - before
        if new:
            # Return the first (usually only) new Chrome window
            return next(iter(new))
        time.sleep(0.3)
    return None


# ── Public API ──────────────────────────────────────────────────────

class ChromeWindowHider:
    """Manages hiding/showing of a Chrome browser window."""

    def __init__(self):
        self._hwnd: int | None = None
        self._original_ex_style: int | None = None
        self._hidden = False

    @property
    def hwnd(self) -> int | None:
        return self._hwnd

    def attach(self, hwnd: int):
        """Attach to a Chrome window handle."""
        self._hwnd = hwnd
        self._original_ex_style = _get_ex_style(hwnd)
        self._hidden = False

    # ── Hide (make transparent) ─────────────────────────────────────

    def hide(self):
        """Make Chrome practically invisible: near-transparent, no taskbar icon,
        behind all windows."""
        if not self._hwnd or self._hidden:
            return
        try:
            # Add WS_EX_LAYERED + WS_EX_TOOLWINDOW, remove WS_EX_APPWINDOW
            ex = _get_ex_style(self._hwnd)
            ex |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
            ex &= ~WS_EX_APPWINDOW
            _set_ex_style(self._hwnd, ex)

            # Set alpha to 1 (practically invisible — 1/255 ≈ 0.4% opacity)
            _set_alpha(self._hwnd, 1)

            # Push window behind everything
            _set_z_order(self._hwnd, HWND_BOTTOM)

            self._hidden = True
        except Exception as e:
            print(f"[WindowHider] hide() error: {e}")

    # ── Show (restore for debugging or CAPTCHA) ─────────────────────

    def show(self):
        """Restore Chrome to fully visible (opaque, on taskbar, normal z-order)."""
        if not self._hwnd:
            return
        try:
            # Restore original extended style (or sensible default)
            if self._original_ex_style is not None:
                _set_ex_style(self._hwnd, self._original_ex_style)
            else:
                ex = _get_ex_style(self._hwnd)
                ex &= ~(WS_EX_TOOLWINDOW | WS_EX_LAYERED)
                ex |= WS_EX_APPWINDOW
                _set_ex_style(self._hwnd, ex)

            # Fully opaque
            _set_alpha(self._hwnd, 255)

            # Bring to top but not topmost
            _set_z_order(self._hwnd, HWND_NOTOPMOST)

            self._hidden = False
        except Exception as e:
            print(f"[WindowHider] show() error: {e}")

    # ── Cleanup ─────────────────────────────────────────────────────

    def detach(self):
        """Detach from the window (does not restore — call show() first if
        you want to restore before closing)."""
        self._hwnd = None
        self._original_ex_style = None
        self._hidden = False

    @property
    def is_hidden(self) -> bool:
        return self._hidden
