#!/usr/bin/env python3
"""Targeted import check for app.main to triage import-time errors.

Sets minimal environment defaults, imports the FastAPI app object, and reports
results. Does not start the server or execute startup hooks.
"""

from __future__ import annotations

import os
import sys
import traceback


def ensure_env_defaults() -> None:
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("JWT_SECRET_KEY", "ci-test-secret")
    os.environ.setdefault("SECRET_KEY", "ci-test-secret")
    os.environ.setdefault("SESSION_SECRET", "ci-test-session")
    # Prefer SQLite to avoid needing a running DB for import-time checks
    os.environ.setdefault("DATABASE_URL", "sqlite:///./ci-import.db")
    # Intentionally DO NOT set REDIS_URL so code paths can switch to in-memory


def main() -> int:
    ensure_env_defaults()
    # Ensure backend is importable as a module root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    backend_root = os.path.join(repo_root, "backend")
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    try:
        from app.main import app  # type: ignore
    except Exception:
        print("IMPORT_ERROR: Failed to import app.main:app")
        traceback.print_exc()
        return 1

    try:
        # Try to access basic attributes (routes) without starting the app
        route_count = len(getattr(app, "routes", []))
        print(f"OK: Imported app with {route_count} routes")
        return 0
    except Exception:
        print("RUNTIME_ERROR: Imported app but failed inspecting routes")
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

