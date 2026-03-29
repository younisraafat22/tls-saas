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
    Must try MM-YYYY before MM-YY — otherwise 05-2026 is misread as 05-20 + stray digits.
    """
    m4 = re.search(r"month=(\d{2})-(\d{4})(?:\b|&|#)", url, re.I)
    if m4:
        return (int(m4.group(1)), int(m4.group(2)), False)
    m2 = re.search(r"month=(\d{2})-(\d{2})(?:\b|&|#)", url, re.I)
    if m2:
        return (int(m2.group(1)), 2000 + int(m2.group(2)), True)
    return None


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
        label = f"{month_names[cur_m - 1]} {cur_y}"
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


def next_two_month_urls_from_seed(seed_url: str) -> list[tuple[str, str]]:
    """
    Next two calendar months after the month= in seed — same as editing the URL by hand
    (e.g. month=05-2026 → 06-2026 → 07-2026). Preserves MM-YY vs MM-YYYY style.
    """
    parsed = parse_month_param(seed_url)
    if not parsed:
        return []
    mm, y, two_digit = parsed
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    out: list[tuple[str, str]] = []
    cur_m, cur_y = mm, y
    for step in (1, 2):
        cur_m, cur_y = increment_month(cur_m, cur_y)
        param = format_month_param(cur_m, cur_y, two_digit)
        label = f"{month_names[cur_m - 1]} {cur_y}"
        out.append((label, replace_month_in_url(seed_url, param)))
    return out


def fourth_fifth_probe_entries_from_links(
    current_url: str,
    hrefs: list[str],
) -> tuple[list[tuple[str, str]], set[str]]:
    """
    After click navigation, probe the next two months by only changing month= in the URL.
    Uses the latest (rightmost) month= on the page — the month you are on after clicking —
    not the earliest month in the strip (which could skew to the wrong calendar month).
    """
    probe_urls: set[str] = set()
    seed = best_seed_url_for_probes_from_list(current_url, hrefs)
    out: list[tuple[str, str]] = []
    for label, u in next_two_month_urls_from_seed(seed):
        out.append((label, u))
        probe_urls.add(u)
    return out[:2], probe_urls


def best_seed_url_for_probes(driver, current_url: str) -> str:
    """Prefer the chronologically latest month= URL from page + current location."""
    return best_seed_url_for_probes_from_list(current_url, collect_month_hrefs_from_driver(driver))
