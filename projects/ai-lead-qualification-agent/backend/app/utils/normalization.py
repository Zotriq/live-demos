"""
Utility functions for normalising raw lead field values before they are
stored or scored by the AI qualification pipeline.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Budget normalisation
# ---------------------------------------------------------------------------

_K_SUFFIX = re.compile(r"(\d[\d,]*\.?\d*)\s*k", re.IGNORECASE)
_M_SUFFIX = re.compile(r"(\d[\d,]*\.?\d*)\s*m", re.IGNORECASE)
_RANGE_SEP = re.compile(r"\s*[-–—to]+\s*", re.IGNORECASE)
_CURRENCY_STRIP = re.compile(r"[$£€¥₹,\s]")
_NUMBER = re.compile(r"(\d[\d,]*\.?\d*)")


def _expand_k_m(token: str) -> str:
    """Expand shorthand suffixes: 5k -> 5000, 1.2m -> 1200000."""
    token = _K_SUFFIX.sub(lambda m: str(float(m.group(1).replace(",", "")) * 1_000), token)
    token = _M_SUFFIX.sub(lambda m: str(float(m.group(1).replace(",", "")) * 1_000_000), token)
    return token


def _parse_single_amount(raw: str) -> Optional[float]:
    """Extract the first numeric value from a string, returning None on failure."""
    raw = _expand_k_m(raw)
    raw = _CURRENCY_STRIP.sub("", raw)
    match = _NUMBER.search(raw)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def normalize_budget(budget_str: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse budget strings into a (min, max) float tuple.

    Handles formats such as:
      "$5,000 - $10,000"   -> (5000.0, 10000.0)
      "$5k-$10k"           -> (5000.0, 10000.0)
      "5000"               -> (5000.0, 5000.0)
      "10k+"               -> (10000.0, None)
      "< $1,000"           -> (None, 1000.0)
      "unknown" / ""       -> (None, None)

    Returns (None, None) for any unparseable input.
    """
    if not budget_str or not budget_str.strip():
        return (None, None)

    raw = budget_str.strip()

    # Handle "unknown" or purely non-numeric strings early
    if re.fullmatch(r"[a-zA-Z\s]+", raw):
        return (None, None)

    # "less than" / "under" -> upper bound only
    less_than = re.match(r"(?:less\s+than|under|<)\s*(.+)", raw, re.IGNORECASE)
    if less_than:
        val = _parse_single_amount(less_than.group(1))
        return (None, val)

    # "more than" / "over" / "+" suffix -> lower bound only
    more_than = re.match(r"(?:more\s+than|over|above|greater\s+than)\s*(.+)", raw, re.IGNORECASE)
    if more_than:
        val = _parse_single_amount(more_than.group(1))
        return (val, None)

    # "10k+" at the end
    plus_suffix = re.match(r"(.+?)\+\s*$", raw)
    if plus_suffix:
        val = _parse_single_amount(plus_suffix.group(1))
        return (val, None)

    # Range: "5,000 - 10,000"
    parts = _RANGE_SEP.split(raw, maxsplit=1)
    if len(parts) == 2:
        lo = _parse_single_amount(parts[0])
        hi = _parse_single_amount(parts[1])
        if lo is not None or hi is not None:
            return (lo, hi)

    # Single value
    val = _parse_single_amount(raw)
    if val is not None:
        return (val, val)

    return (None, None)


# ---------------------------------------------------------------------------
# Timeline normalisation
# ---------------------------------------------------------------------------

_TIMELINE_PATTERNS: list[Tuple[re.Pattern, str]] = [
    (re.compile(r"\basap\b|immediately|right\s+away|urgent|now", re.IGNORECASE), "asap"),
    (re.compile(r"this\s+month|current\s+month|\bmonth\b", re.IGNORECASE), "this_month"),
    (re.compile(r"next\s+month|1\s+month|one\s+month|30\s+days", re.IGNORECASE), "next_month"),
    (re.compile(r"this\s+quarter|current\s+quarter|q[1-4]\s+\d{4}", re.IGNORECASE), "this_quarter"),
    (re.compile(r"next\s+quarter|[23]\s+months?|60\s+days|90\s+days", re.IGNORECASE), "next_quarter"),
]


def normalize_timeline(timeline_str: Optional[str]) -> str:
    """
    Normalise a free-text timeline description to a canonical bucket.

    Returns one of: "asap", "this_month", "next_month",
                    "this_quarter", "next_quarter", "unknown".
    """
    if not timeline_str or not timeline_str.strip():
        return "unknown"

    for pattern, bucket in _TIMELINE_PATTERNS:
        if pattern.search(timeline_str):
            return bucket

    return "unknown"


# ---------------------------------------------------------------------------
# Company size normalisation
# ---------------------------------------------------------------------------

_SIZE_KEYWORDS: dict[str, int] = {
    "solo": 1,
    "freelance": 1,
    "individual": 1,
    "startup": 10,
    "small": 25,
    "smb": 100,
    "mid": 250,
    "mid-size": 250,
    "midsize": 250,
    "medium": 250,
    "large": 1000,
    "enterprise": 5000,
    "corporation": 5000,
    "corporate": 5000,
}


def normalize_company_size(size_str: Optional[str]) -> Optional[int]:
    """
    Extract an approximate employee count from a size string.

    Handles:
      "50-100"      -> 75  (midpoint)
      "100+"        -> 100
      "1,000-5,000" -> 3000
      "small"       -> 25
      "enterprise"  -> 5000
      None / ""     -> None
    """
    if not size_str or not size_str.strip():
        return None

    raw = size_str.strip().lower()

    # Keyword lookup
    for keyword, approx in _SIZE_KEYWORDS.items():
        if keyword in raw:
            return approx

    # "100+" style
    plus_match = re.match(r"([\d,]+)\+", raw)
    if plus_match:
        try:
            return int(plus_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Range style "50-100" or "50 to 100"
    range_match = re.match(r"([\d,]+)\s*[-–to]+\s*([\d,]+)", raw)
    if range_match:
        try:
            lo = int(range_match.group(1).replace(",", ""))
            hi = int(range_match.group(2).replace(",", ""))
            return (lo + hi) // 2
        except ValueError:
            pass

    # Single integer
    single_match = re.fullmatch(r"[\d,]+", raw.replace(" ", ""))
    if single_match:
        try:
            return int(raw.replace(",", "").replace(" ", ""))
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Industry normalisation
# ---------------------------------------------------------------------------

def normalize_industry(industry_str: Optional[str]) -> str:
    """
    Return a lowercase, stripped version of the industry string.

    Returns an empty string when the input is None or blank.
    """
    if not industry_str:
        return ""
    return industry_str.strip().lower()
