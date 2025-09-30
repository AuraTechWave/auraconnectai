"""Integration tests for RBAC-backed authentication endpoints."""

import os
import sys
import types
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("SECRET_KEY", "test-app-secret")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ARGON2_ENABLED", "false")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class _AsyncFile:
    """Minimal async file stub for aiofiles.open."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def write(self, _data):
        return 0


aiofiles_stub = types.ModuleType("aiofiles")
aiofiles_stub.open = lambda *args, **kwargs: _AsyncFile()
sys.modules.setdefault("aiofiles", aiofiles_stub)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.auth as auth_module
from core.auth import get_password_hash, verify_password
from modules.auth.routes.auth_routes import router as auth_router
from core.session_manager import session_manager as global_session_manager


test_app = FastAPI()
test_app.include_router(auth_router)


class _StubRateLimiter:
    async def check_rate_limit(self, *_args, **_kwargs):
        return True, None

    async def record_failed_attempt(self, *_args, **_kwargs):
        return None

    async def record_successful_attempt(self, *_args, **_kwargs):
        return None


test_app.state.auth_rate_limiter = _StubRateLimiter()


class StubRole:
    def __init__(self, name: str):
        self.name = name


class StubRBACUser:
    def __init__(
        self,
        user_id: int,
        username: str,
        email: str,
        hashed_password: str,
        accessible_tenant_ids=None,
        default_tenant_id=None,
    ):
        self.id = user_id
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.accessible_tenant_ids = list(accessible_tenant_ids or [])
        self.default_tenant_id = default_tenant_id
        self.is_active = True
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login = None


class StubRBACService:
    def __init__(self):
        self.reset()

    def reset(self):
        self.users_by_id = {}
        self.users_by_username = {}
        self.roles = {}
        self.user_roles = {}
        self.user_role_tenants = {}
        self._id_seq = 1

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        accessible_tenant_ids=None,
        default_tenant_id=None,
    ) -> StubRBACUser:
        user_id = self._id_seq
        self._id_seq += 1
        hashed_password = get_password_hash(password)
        user = StubRBACUser(
            user_id,
            username,
            email,
            hashed_password,
            accessible_tenant_ids,
            default_tenant_id,
        )
        self.users_by_id[user_id] = user
        self.users_by_username[username] = user
        return user

    def get_user_by_id(self, user_id: int) -> StubRBACUser | None:
        return self.users_by_id.get(user_id)

    def get_user_by_username(self, username: str) -> StubRBACUser | None:
        return self.users_by_username.get(username)

    def authenticate_user(self, username: str, password: str) -> StubRBACUser | None:
        user = self.get_user_by_username(username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        return user

    def create_role(self, name: str) -> StubRole:
        role = self.roles.get(name)
        if role is None:
            role = StubRole(name)
            self.roles[name] = role
        return role

    def assign_role_to_user(
        self,
        user_id: int,
        role_id,
        tenant_id: int | None = None,
        **_,
    ) -> None:
        role = self.roles.get(role_id)
        if role is None:
            role = StubRole(str(role_id))
            self.roles[role_id] = role
        self.user_roles.setdefault(user_id, []).append(role)
        if tenant_id is not None:
            self.user_role_tenants.setdefault(user_id, set()).add(tenant_id)

    def get_user_roles(self, user_id: int, tenant_id: int | None = None):
        return self.user_roles.get(user_id, [])


stub_service = StubRBACService()


@contextmanager
def _dummy_session():
    class _Session:
        def commit(self):
            return None

        def close(self):
            return None

    yield _Session()


def _collect_stub_tenant_ids(rbac_user: StubRBACUser, service: StubRBACService):
    tenant_ids = set(rbac_user.accessible_tenant_ids or [])
    if rbac_user.default_tenant_id is not None:
        tenant_ids.add(rbac_user.default_tenant_id)
    tenant_ids.update(service.user_role_tenants.get(rbac_user.id, set()))
    return sorted(tenant_ids)


auth_module._get_sync_session = _dummy_session
auth_module._build_rbac_service = lambda _db: stub_service
auth_module._collect_active_tenant_ids = _collect_stub_tenant_ids
global_session_manager.redis = None
global_session_manager._memory_sessions = {}
global_session_manager._blacklisted_tokens = set()

_original_jwt_decode = auth_module.jwt.decode


def _jwt_decode_with_fallback(*args, **kwargs):
    try:
        return _original_jwt_decode(*args, **kwargs)
    except TypeError:
        filtered = {k: v for k, v in kwargs.items() if k != "leeway"}
        return _original_jwt_decode(*args, **filtered)


auth_module.jwt.decode = _jwt_decode_with_fallback


@pytest.fixture(autouse=True)
def reset_stub_service():
    stub_service.reset()
    yield
    stub_service.reset()


@pytest.fixture()
def client():
    with TestClient(test_app) as test_client:
        yield test_client


def _seed_user(
    *,
    username: str = "authuser",
    password: str = "AuthPass123!",
    accessible_tenants=None,
):
    user = stub_service.create_user(
        username=username,
        email=f"{username}@example.com",
        password=password,
        accessible_tenant_ids=accessible_tenants or [1, 2],
        default_tenant_id=1,
    )
    stub_service.create_role("admin")
    stub_service.assign_role_to_user(user.id, "admin", tenant_id=1)
    return user, password


def test_login_refresh_logout_flow(client):
    user, password = _seed_user()

    response = client.post(
        "/auth/login",
        data={"username": user.username, "password": password},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["user_info"]["username"] == user.username
    assert sorted(payload["user_info"]["tenant_ids"]) == [1, 2]
    assert "admin" in payload["user_info"]["roles"]

    access_token = payload["access_token"]
    refresh_token = payload["refresh_token"]

    me_response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == user.username

    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["token_type"] == "bearer"
    assert refreshed["access_token"]

    logout_response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"logout_all_sessions": False},
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully"


def test_login_with_invalid_password_fails(client):
    user, _ = _seed_user()

    bad_response = client.post(
        "/auth/login",
        data={"username": user.username, "password": "WrongPass!"},
    )
    assert bad_response.status_code == 401
    assert bad_response.json()["detail"] == "Incorrect username or password"
