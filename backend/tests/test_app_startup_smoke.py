"""Smoke tests focused on startup-critical components."""

from __future__ import annotations

import ast
import importlib
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI


def _ensure_backend_packages() -> None:
    """Add backend packages to sys.path and alias namespace packages."""
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    modules_pkg = importlib.import_module("backend.modules")
    sys.modules.setdefault("modules", modules_pkg)

    if "aiofiles" not in sys.modules:
        class _AsyncFile:
            async def __aenter__(self):  # pragma: no cover - stub
                return self

            async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - stub
                return False

            async def write(self, *_args, **_kwargs):  # pragma: no cover - stub
                return None

            async def flush(self):  # pragma: no cover - stub
                return None

        def _aiofiles_open(*_args, **_kwargs):  # pragma: no cover - stub
            return _AsyncFile()

        sys.modules["aiofiles"] = types.SimpleNamespace(open=_aiofiles_open)


def test_order_inventory_router_can_be_included(monkeypatch) -> None:
    """Previously missing import should now resolve and register without errors."""
    _ensure_backend_packages()

    # Minimal environment so the router dependencies (auth) can load
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt")
    monkeypatch.setenv("SESSION_SECRET", "test-session")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ENVIRONMENT", "development")

    routes_module = importlib.import_module(
        "modules.orders.routes.order_inventory_routes"
    )
    app = FastAPI()
    app.include_router(routes_module.router)

    paths = {route.path for route in app.router.routes}
    assert any(path.startswith("/orders/") for path in paths)


def test_root_handler_returns_expected_message() -> None:
    """Verify the literal response returned by read_root stays consistent."""
    main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    module_ast = ast.parse(main_path.read_text(encoding="utf-8"))

    for node in module_ast.body:
        if isinstance(node, ast.FunctionDef) and node.name == "read_root":
            for stmt in node.body:
                if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                    keys = [k.value for k in stmt.value.keys if isinstance(k, ast.Constant)]
                    values = [v.value for v in stmt.value.values if isinstance(v, ast.Constant)]
                    assert keys == ["message"]
                    assert values == ["AuraConnect backend is running"]
                    return
            pytest.fail("read_root does not return a simple dict literal")

    pytest.fail("read_root endpoint not found in backend/app/main.py")
