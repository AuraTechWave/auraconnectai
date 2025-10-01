"""Application factory for Docker/compose environments.

This file provides a resilient FastAPI app loader. The full AuraConnect backend
imports hundreds of routers and optional integrations. In the current codebase
those imports fail in fresh clones (missing migrations, placeholder modules,
etc.), which historically crashed Docker based workflows. The factory attempts
to load the full application and gracefully falls back to a lightweight health
app when dependencies are unavailable. The fallback keeps `docker compose up`
alive for local development while the real fixes are tackled separately.
"""

from __future__ import annotations

import logging
import os
from typing import Literal

from fastapi import FastAPI

LOGGER = logging.getLogger(__name__)

FallbackMode = Literal["disabled", "minimal"]


def _create_minimal_app() -> FastAPI:
    """Return a very small FastAPI app with a root endpoint and docs."""

    app = FastAPI(
        title="AuraConnect Backend (minimal profile)",
        description="Temporary minimal app used when full backend startup fails.",
        version="0.0.0",
    )

    @app.get("/", tags=["health"])
    def read_root() -> dict[str, str]:
        return {
            "status": "ok",
            "profile": "minimal",
            "message": "AuraConnect backend loaded in minimal profile.",
        }

    return app


def create_app() -> FastAPI:
    """Create the FastAPI application based on configured profile.

    Environment variables:
        BACKEND_STARTUP_PROFILE: "full" (default) or "minimal".
        ALLOW_MINIMAL_FALLBACK: when "false", raise the original failure.
    """

    profile = os.getenv("BACKEND_STARTUP_PROFILE", "full").lower()
    fallback: FallbackMode = (
        "disabled"
        if os.getenv("ALLOW_MINIMAL_FALLBACK", "true").lower() in {"false", "0"}
        else "minimal"
    )

    if profile != "full":
        LOGGER.warning("Using backend startup profile '%s'", profile)
        return _create_minimal_app()

    try:
        from app.main import app as full_app  # pylint: disable=import-error

        return full_app
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.error("Failed to load full backend app: %s", exc, exc_info=True)
        if fallback == "minimal":
            LOGGER.warning(
                "Falling back to minimal backend profile. Set ALLOW_MINIMAL_FALLBACK=false "
                "to disable this behaviour."
            )
            return _create_minimal_app()
        raise
