"""
Validation and sanitisation helpers for incoming lead payloads.
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Domains commonly associated with disposable / throwaway email services
_DISPOSABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "guerrillamail.net",
        "guerrillamail.org",
        "guerrillamailblock.com",
        "grr.la",
        "sharklasers.com",
        "spam4.me",
        "trashmail.com",
        "trashmail.me",
        "trashmail.net",
        "dispostable.com",
        "tempmail.com",
        "temp-mail.org",
        "fakeinbox.com",
        "yopmail.com",
        "yopmail.fr",
        "cool.fr.nf",
        "jetable.fr.nf",
        "nospam.ze.tc",
        "nomail.xl.cx",
        "mega.zik.dj",
        "speed.1s.fr",
        "courriel.fr.nf",
        "moncourrier.fr.nf",
        "monemail.fr.nf",
        "monmail.fr.nf",
        "throwam.com",
        "throwam.net",
        "maildrop.cc",
        "discard.email",
        "spamgourmet.com",
        "trashmail.at",
        "trashmail.io",
        "guerrillamail.info",
        "10minutemail.com",
        "10minutemail.net",
        "10minutemail.org",
        "emailondeck.com",
        "mohmal.com",
        "mintemail.com",
        "getnada.com",
        "tempr.email",
        "cfl.fr",
        "mailnull.com",
        "spamfree24.org",
    }
)

_SPAM_PHRASES: frozenset[str] = frozenset(
    {
        "click here",
        "buy now",
        "free money",
        "you have won",
        "you've won",
        "congratulations you",
        "limited time offer",
        "act now",
        "earn extra cash",
        "make money fast",
        "work from home",
        "100% free",
        "casino",
        "online pharmacy",
        "cheap meds",
        "weight loss",
        "enlargement",
        "nigerian prince",
        "wire transfer",
        "bank account",
        "credit card required",
        "no credit card",
        "free trial",
        "risk free",
        "satisfaction guaranteed",
        "unsubscribe",
        "opt out",
        "this is not spam",
        "not spam",
        "dear friend",
        "dear beneficiary",
    }
)

# Rough email validation (intentionally lenient; Pydantic's EmailStr is the
# authoritative check).  This is used as a lightweight format guard.
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# Tags to strip during sanitisation
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_DANGEROUS_CHARS_RE = re.compile(r"[<>{}\[\]\\`]")

# Maximum length for sanitised free-text fields
_MAX_TEXT_LENGTH = 5_000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_lead_payload(data: dict) -> list[str]:
    """
    Validate a raw lead payload dict and return a list of error strings.

    An empty list means the payload is valid.

    Checks performed:
    - Presence and non-emptiness of required fields: name, email.
    - Basic email format.
    - Disposable email domain detection.
    - Spam detection via :func:`is_spam`.
    """
    errors: list[str] = []

    # --- Required field: name ---
    name = data.get("name")
    if not name or not str(name).strip():
        errors.append("Field 'name' is required and cannot be empty.")
    else:
        name = str(name).strip()

    # --- Required field: email ---
    email = data.get("email")
    if not email or not str(email).strip():
        errors.append("Field 'email' is required and cannot be empty.")
    else:
        email = str(email).strip().lower()
        if not _EMAIL_RE.match(email):
            errors.append(f"Field 'email' does not appear to be a valid email address: '{email}'.")
        else:
            domain = email.split("@", 1)[-1]
            if domain in _DISPOSABLE_DOMAINS:
                errors.append(
                    f"Email domain '{domain}' is associated with disposable addresses and is not accepted."
                )

    # --- Spam detection ---
    message = str(data.get("message") or "")
    name_val = str(data.get("name") or "")
    email_val = str(data.get("email") or "")
    if is_spam(message, name_val, email_val):
        errors.append("Submission was identified as potential spam and rejected.")

    return errors


def is_spam(message: str, name: str, email: str) -> bool:
    """
    Perform basic heuristic spam detection.

    Returns True when any of the following conditions is met:

    - The message is predominantly upper-case (ALL CAPS).
    - The message contains a known spam phrase.
    - The email domain is in the disposable-domain list.
    - The name consists entirely of digits or is suspiciously short.
    - The message or name contains a URL (http/https links are rarely
      legitimate in an initial contact form).
    """
    # All-caps message (ignore very short messages)
    if message and len(message) > 20:
        alpha = [c for c in message if c.isalpha()]
        if alpha and sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.85:
            return True

    # Known spam phrases (case-insensitive)
    message_lower = message.lower()
    for phrase in _SPAM_PHRASES:
        if phrase in message_lower:
            return True

    # Disposable email domain
    if email and "@" in email:
        domain = email.strip().lower().split("@", 1)[-1]
        if domain in _DISPOSABLE_DOMAINS:
            return True

    # Name is purely digits or unrealistically short (single char)
    name_stripped = name.strip()
    if name_stripped and (name_stripped.isdigit() or len(name_stripped) < 2):
        return True

    # URL in the message or name
    url_pattern = re.compile(r"https?://\S+", re.IGNORECASE)
    if url_pattern.search(message) or url_pattern.search(name):
        return True

    return False


def sanitize_text(text: Optional[str], max_length: int = _MAX_TEXT_LENGTH) -> str:
    """
    Clean a free-text string for safe storage and display.

    Steps:
    1. Return an empty string for None / falsy input.
    2. Strip leading/trailing whitespace.
    3. Remove HTML tags.
    4. Remove characters that could be used for injection attacks.
    5. Collapse runs of whitespace to a single space.
    6. Truncate to ``max_length`` characters.
    """
    if not text:
        return ""

    result = text.strip()

    # Remove HTML tags
    result = _HTML_TAG_RE.sub("", result)

    # Remove dangerous characters
    result = _DANGEROUS_CHARS_RE.sub("", result)

    # Collapse whitespace
    result = re.sub(r"\s{2,}", " ", result)

    # Enforce length limit
    if len(result) > max_length:
        result = result[:max_length]

    return result.strip()
