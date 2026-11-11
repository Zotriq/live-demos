from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / "profiles"

load_dotenv(ROOT / ".env")

ALL_SOURCES = ["greenhouse", "lever", "ashby", "remotive"]


def is_public(profile: dict) -> bool:
    """Public demo mode (portfolio site): sample data first, limited live runs,
    profile edits kept per visitor, Remotive off (it allows only a few calls a day)."""
    import os
    return bool(profile.get("public_demo")) or os.getenv("JOB_RADAR_PUBLIC") == "1"


def list_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILE_DIR.glob("*.yaml"))


def load_profile(name: str = "default") -> dict:
    return yaml.safe_load((PROFILE_DIR / f"{name}.yaml").read_text())


def save_profile(profile: dict, name: str = "default"):
    (PROFILE_DIR / f"{name}.yaml").write_text(yaml.safe_dump(profile, sort_keys=False, allow_unicode=True))
