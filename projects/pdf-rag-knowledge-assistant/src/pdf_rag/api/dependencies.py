"""Shared FastAPI dependencies: settings injection and API key authentication."""

from fastapi import Depends, Header, HTTPException, status

from pdf_rag.config import Settings, get_settings


def settings_dependency() -> Settings:
    return get_settings()


def require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(settings_dependency),
) -> None:
    """
    Simple shared-secret API key check.

    For a multi-tenant production deployment this would be replaced with
    OAuth2 / JWT-based auth (see docs/security.md for the upgrade path).
    """
    if not settings.api_key:
        # No API key configured (e.g. local dev) -> auth disabled.
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )
