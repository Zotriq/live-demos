from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Core
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/lead_qualification",
        description="Async-compatible PostgreSQL connection string (asyncpg driver).",
    )
    OPENAI_API_KEY: str = Field(default="", description="OpenAI secret key.")
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model used for lead analysis and email generation.",
    )
    APP_BASE_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend / app base URL (used in generated links).",
    )
    BACKEND_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="Backend base URL (used in webhook callbacks, etc.).",
    )

    # ------------------------------------------------------------------ #
    # Slack
    # ------------------------------------------------------------------ #
    SLACK_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Incoming-webhook URL for Slack notifications.",
    )

    # ------------------------------------------------------------------ #
    # Google Sheets
    # ------------------------------------------------------------------ #
    GOOGLE_SHEETS_ENABLED: bool = Field(
        default=False,
        description="Enable Google Sheets integration.",
    )
    GOOGLE_SHEETS_SPREADSHEET_ID: Optional[str] = Field(
        default=None,
        description="Target spreadsheet ID.",
    )
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = Field(
        default=None,
        description="Serialised service-account JSON (single-line or base64).",
    )

    # ------------------------------------------------------------------ #
    # Airtable
    # ------------------------------------------------------------------ #
    AIRTABLE_ENABLED: bool = Field(default=False, description="Enable Airtable integration.")
    AIRTABLE_API_KEY: Optional[str] = Field(default=None, description="Airtable personal access token.")
    AIRTABLE_BASE_ID: Optional[str] = Field(default=None, description="Airtable base ID.")
    AIRTABLE_TABLE_NAME: str = Field(default="Leads", description="Airtable table name.")

    # ------------------------------------------------------------------ #
    # HubSpot
    # ------------------------------------------------------------------ #
    HUBSPOT_ENABLED: bool = Field(default=False, description="Enable HubSpot CRM integration.")
    HUBSPOT_API_KEY: Optional[str] = Field(default=None, description="HubSpot private app token.")

    # ------------------------------------------------------------------ #
    # n8n
    # ------------------------------------------------------------------ #
    N8N_WEBHOOK_ENABLED: bool = Field(default=False, description="Enable n8n webhook forwarding.")
    N8N_WEBHOOK_URL: Optional[str] = Field(default=None, description="n8n webhook URL.")

    # ------------------------------------------------------------------ #
    # Email / SMTP
    # ------------------------------------------------------------------ #
    EMAIL_SENDING_ENABLED: bool = Field(
        default=False,
        description="Allow the system to send emails via SMTP.",
    )
    SMTP_HOST: Optional[str] = Field(default=None, description="SMTP server hostname.")
    SMTP_PORT: int = Field(default=587, description="SMTP server port (587 = STARTTLS).")
    SMTP_USER: Optional[str] = Field(default=None, description="SMTP login username.")
    SMTP_PASSWORD: Optional[str] = Field(default=None, description="SMTP login password.")
    FROM_EMAIL: Optional[str] = Field(
        default=None,
        description="Sender address used in outgoing emails.",
    )

    # ------------------------------------------------------------------ #
    # Security / Dashboard
    # ------------------------------------------------------------------ #
    WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="Shared secret for verifying inbound webhook signatures.",
    )
    DASHBOARD_USERNAME: str = Field(
        default="admin",
        description="Username for the built-in dashboard basic-auth.",
    )
    DASHBOARD_PASSWORD: str = Field(
        default="admin123",
        description="Password for the built-in dashboard basic-auth.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once at startup)."""
    return Settings()
