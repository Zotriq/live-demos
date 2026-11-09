from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import close_db, init_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan  (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise resources on startup and release them on shutdown."""
    logger.info("Starting up – initialising database …")
    await init_db()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down – disposing database connections …")
    await close_db()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AI Lead Qualification Agent",
        description=(
            "Automated lead capture, AI-powered qualification scoring, "
            "follow-up email generation and CRM/notification integrations."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.APP_BASE_URL,
            settings.BACKEND_BASE_URL,
            # Allow localhost variants during local development
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Request-Id"],
    )

    # ------------------------------------------------------------------ #
    # Routers  – imported here to avoid circular imports at module load
    # ------------------------------------------------------------------ #
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    """
    Import and mount all API routers.

    Routers are imported inside this function so that the module graph
    does not create circular dependencies during testing.
    Each router already defines its own prefix (e.g. /api/leads), so
    we do NOT add an extra prefix here to avoid double-prefixed URLs.
    """
    try:
        from app.routes import leads  # noqa: PLC0415
        app.include_router(leads.router, tags=["Leads"])
    except ImportError:
        logger.warning("Router 'leads' not found – skipping.")

    try:
        from app.routes import email_approval  # noqa: PLC0415
        app.include_router(email_approval.router, tags=["Emails"])
    except ImportError:
        logger.warning("Router 'email_approval' not found – skipping.")

    try:
        from app.routes import dashboard  # noqa: PLC0415
        app.include_router(dashboard.router, tags=["Dashboard"])
    except ImportError:
        logger.warning("Router 'dashboard' not found – skipping.")

    try:
        from app.routes import webhooks  # noqa: PLC0415
        app.include_router(webhooks.router, tags=["Webhooks"])
    except ImportError:
        logger.warning("Router 'webhooks' not found – skipping.")


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = create_app()


# ---------------------------------------------------------------------------
# Health / readiness endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    tags=["Health"],
    summary="Liveness probe",
    response_class=JSONResponse,
)
async def health_check() -> dict:
    """
    Returns ``200 OK`` as long as the process is running.

    Suitable for use as a Docker / Kubernetes liveness probe.
    """
    return {"status": "ok", "service": "ai-lead-qualification-agent"}


@app.get(
    "/ready",
    tags=["Health"],
    summary="Readiness probe",
    response_class=JSONResponse,
)
async def readiness_check() -> dict:
    """
    Verifies that the application can reach the database before reporting ready.

    Suitable for use as a Kubernetes readiness probe.
    """
    from sqlalchemy import text  # noqa: PLC0415
    from app.database import _get_engine  # noqa: PLC0415

    try:
        engine = _get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.error("Readiness check – DB ping failed: %s", exc)
        db_status = f"error: {exc}"

    ready = db_status == "ok"
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": {"database": db_status},
        },
    )
