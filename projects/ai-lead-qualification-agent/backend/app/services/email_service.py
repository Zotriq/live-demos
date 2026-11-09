"""
Email sending service (SMTP via aiosmtplib).

Sends transactional emails using an async SMTP connection.  The
integration is opt-in: if EMAIL_SENDING_ENABLED is False, or if the
required SMTP settings are missing, every call returns a "skipped"
status.

Dependencies:
    pip install aiosmtplib
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Send emails via async SMTP (aiosmtplib)."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        *,
        html_body: str | None = None,
    ) -> dict[str, Any]:
        """Send an email to *to_email*.

        Parameters
        ----------
        to_email:
            Recipient email address.
        subject:
            Email subject line.
        body:
            Plain-text body.
        html_body:
            Optional HTML body.  When provided, the email is sent as
            multipart/alternative with both plain-text and HTML parts.

        Returns a dict with at minimum:
            {
                "status":  "success" | "skipped" | "error",
                "message": str,
            }
        """
        settings = self._settings

        if not settings.EMAIL_SENDING_ENABLED:
            logger.warning(
                "EmailService: email sending is disabled "
                "(EMAIL_SENDING_ENABLED=False). Skipping send."
            )
            return self._skipped("Email sending is disabled.")

        if not settings.SMTP_HOST:
            logger.warning("EmailService: SMTP_HOST is not set. Skipping send.")
            return self._skipped("SMTP_HOST is not configured.")

        if not settings.FROM_EMAIL:
            logger.warning("EmailService: FROM_EMAIL is not set. Skipping send.")
            return self._skipped("FROM_EMAIL is not configured.")

        if not to_email or "@" not in to_email:
            return self._error(f"Invalid recipient email address: '{to_email}'.")

        try:
            return await self._send(to_email, subject, body, html_body=html_body)
        except Exception as exc:
            logger.exception("EmailService: unexpected error sending email: %s", exc)
            return self._error(str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _send(
        self,
        to_email: str,
        subject: str,
        body: str,
        *,
        html_body: str | None = None,
    ) -> dict[str, Any]:
        try:
            import aiosmtplib  # type: ignore
        except ImportError:
            return self._error(
                "aiosmtplib is not installed. Run: pip install aiosmtplib"
            )

        settings = self._settings

        msg = EmailMessage()
        msg["From"]    = settings.FROM_EMAIL
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        if html_body:
            # attach HTML alternative
            msg.add_alternative(html_body, subtype="html")

        smtp_kwargs: dict[str, Any] = {
            "hostname": settings.SMTP_HOST,
            "port":     settings.SMTP_PORT,
            "username": settings.SMTP_USER or None,
            "password": settings.SMTP_PASSWORD or None,
        }

        # Port 465 → implicit TLS; port 587 → STARTTLS; other ports → plain
        if settings.SMTP_PORT == 465:
            smtp_kwargs["use_tls"] = True
        elif settings.SMTP_PORT == 587:
            smtp_kwargs["start_tls"] = True

        try:
            await aiosmtplib.send(msg, **smtp_kwargs)
        except aiosmtplib.SMTPAuthenticationError as exc:
            logger.error("EmailService: SMTP authentication failed: %s", exc)
            return self._error(f"SMTP authentication error: {exc}")
        except aiosmtplib.SMTPConnectError as exc:
            logger.error("EmailService: SMTP connection failed: %s", exc)
            return self._error(f"SMTP connection error: {exc}")
        except aiosmtplib.SMTPException as exc:
            logger.error("EmailService: SMTP error: %s", exc)
            return self._error(f"SMTP error: {exc}")

        logger.info(
            "EmailService: email '%s' sent to '%s' via %s:%s.",
            subject,
            to_email,
            settings.SMTP_HOST,
            settings.SMTP_PORT,
        )
        return {
            "status":  "success",
            "message": f"Email '{subject}' sent successfully to '{to_email}'.",
        }

    # ------------------------------------------------------------------
    # Response factories
    # ------------------------------------------------------------------

    @staticmethod
    def _skipped(message: str) -> dict[str, Any]:
        return {"status": "skipped", "message": message}

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"status": "error", "message": message}
