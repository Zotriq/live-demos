"""Configuration: environment loading, API-key auto-detection, and tunable constants."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
EXECUTION_LOG_PATH = PROJECT_ROOT / "agent_execution.log"

load_dotenv(ENV_PATH)

# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #
MAIN_MODEL = os.getenv("MAIN_MODEL", "openai/gpt-oss-120b")
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "openai/gpt-oss-20b")

MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "8"))
WINDOW_TURNS = int(os.getenv("WINDOW_TURNS", "5"))

SEARCH_RESULTS = int(os.getenv("SEARCH_RESULTS", "5"))
FILE_READ_MAX_CHARS = int(os.getenv("FILE_READ_MAX_CHARS", "12000"))
FILE_READ_BASE_DIR = Path(os.getenv("FILE_READ_BASE_DIR", str(PROJECT_ROOT))).resolve()

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

_GROQ_PREFIX = "gsk_"


def _looks_like_groq(value: str | None) -> bool:
    return bool(value) and value.strip().startswith(_GROQ_PREFIX)


def _resolve_keys() -> tuple[str, str]:
    """Return (groq_key, serpapi_key), tolerating the two env vars being swapped.

    The bundled ``.env`` has the values crossed over (``GROQ_API_KEY`` holds a
    SerpAPI-shaped hex string and ``SERP_API_KEY`` holds a ``gsk_`` Groq key), so
    we pick by value shape rather than trusting the variable names.
    """
    raw_groq = (os.getenv("GROQ_API_KEY") or "").strip()
    raw_serp = (os.getenv("SERP_API_KEY") or os.getenv("SERPAPI_KEY") or "").strip()

    if _looks_like_groq(raw_groq):
        return raw_groq, raw_serp
    if _looks_like_groq(raw_serp):
        warnings.warn(
            "GROQ_API_KEY / SERP_API_KEY appear swapped in .env; using value shape "
            "to assign them (the 'gsk_' value is treated as the Groq key).",
            RuntimeWarning,
            stacklevel=2,
        )
        return raw_serp, raw_groq

    # Neither looks like a Groq key — hand back the named values and let the
    # caller fail loudly when it actually tries to use them.
    return raw_groq, raw_serp


GROQ_API_KEY, SERPAPI_KEY = _resolve_keys()


def require_groq_key() -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("No Groq API key found. Set GROQ_API_KEY in .env")
    return GROQ_API_KEY


def require_serpapi_key() -> str:
    if not SERPAPI_KEY:
        raise RuntimeError("No SerpAPI key found. Set SERP_API_KEY in .env")
    return SERPAPI_KEY
