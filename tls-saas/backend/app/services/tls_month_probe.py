"""
Helpers to probe TLS appointment-booking months beyond visible/enabled UI links.
Some months show as disabled in the MonthSelector but still load slots when the
`month=MM-YY` (or `MM-YYYY`) query parameter is incremented manually.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def parse_month_param(url: str) -> tuple[int, int, bool] | None:
    """
    Parse month= from URL. Returns (month 1-12, full_year, uses_two_digit_year_in_url).
    Supports month=05-26 and month=05-2026.
    """
    m = re.search(r"month=(\d{2})-(\d{2}|\d{4})", url, re.I)
    if not m:
        return None
    mm = int(m.group(1))
    y_raw = m.group(2)
    if len(y_raw) == 2:
        y = 2000 + int(y_raw)
        return (mm, y, True)
    y = int(y_raw)
    return (mm, y, False)


def increment_month(mm: int, y: int) -> tuple[int, int]:
    mm2 = mm + 1
    y2 = y
    if mm2 > 12:
        mm2 = 1
        y2 += 1
    return mm2, y2


def format_month_param(mm: int, y: int, two_digit_year: bool) -> str:
    if two_digit_year:
        return f"{mm:02d}-{y % 100:02d}"
    return f"{mm:02d}-{y}"


def replace_month_in_url(url: str, month_param: str) -> str:
    """Set or replace the `month` query parameter, preserving other params."""
    p = urlparse(url)
    qs = parse_qs(p.query, keep_blank_values=True)
    flat = {k: v[0] if v else "" for k, v in qs.items()}
    flat["month"] = month_param
    new_query = urlencode(flat)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def synthetic_future_month_urls(seed_url: str, max_extra: int = 8) -> list[tuple[str, str]]:
    """
    From a TLS appointment-booking URL, generate up to max_extra subsequent calendar months.
    Returns list of (label, full_url).
    """
    parsed = parse_month_param(seed_url)
    if not parsed:
        return []
    mm, y, two_digit = parsed
    out: list[tuple[str, str]] = []
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    cur_m, cur_y = mm, y
    for _ in range(max_extra):
        cur_m, cur_y = increment_month(cur_m, cur_y)
        param = format_month_param(cur_m, cur_y, two_digit)
        label = f"{month_names[cur_m - 1]} {cur_y} (URL probe)"
        out.append((label, replace_month_in_url(seed_url, param)))
    return out


def collect_month_hrefs_from_driver(driver) -> list[str]:
    """All distinct appointment-booking month URLs visible in the DOM."""
    hrefs: list[str] = []
    seen: set[str] = set()
    try:
        from selenium.webdriver.common.by import By

        for link in driver.find_elements(
            By.CSS_SELECTOR,
            "a[href*='appointment-booking?month='], a[href*='appointment-booking?']",
        ):
            try:
                h = (link.get_attribute("href") or "").strip()
                if "month=" in h and h not in seen:
                    seen.add(h)
                    hrefs.append(h)
            except Exception:
                continue
    except Exception:
        pass
    return hrefs


def best_seed_url_for_probes_from_list(current_url: str, hrefs: list[str]) -> str:
    """Prefer the chronologically latest month= URL from candidates."""
    candidates = [current_url] + list(hrefs)
    best = current_url
    best_key: tuple[int, int] | None = None
    for u in candidates:
        p = parse_month_param(u)
        if not p:
            continue
        mm, y, _ = p
        key = (y, mm)
        if best_key is None or key > best_key:
            best_key = key
            best = u
    return best


def best_seed_url_for_probes(driver, current_url: str) -> str:
    """Prefer the chronologically latest month= URL from page + current location."""
    return best_seed_url_for_probes_from_list(current_url, collect_month_hrefs_from_driver(driver))
