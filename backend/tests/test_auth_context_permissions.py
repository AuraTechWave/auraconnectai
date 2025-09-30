"""Integration tests for auth context aware permission enforcement."""

from typing import Dict, List, Optional

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from core.auth import User, create_access_token, require_permission
from core.tenant_context import TenantIsolationMiddleware


def _make_token(
    user_id: int, username: str, roles: List[str], tenant_ids: Optional[List[int]] = None
) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "email": f"{username}@example.com",
        "roles": roles,
        "tenant_ids": tenant_ids or [1],
    }
    return create_access_token(payload)


def _auth_headers(token: str, tenant_id: Optional[int] = 1) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if tenant_id is not None:
        headers["X-Tenant-ID"] = str(tenant_id)
    return headers


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """Provide a FastAPI test client with tenant isolation enabled."""

    app = FastAPI()
    app.add_middleware(TenantIsolationMiddleware)

    # Avoid hitting the database when resolving users during tests.
    monkeypatch.setattr("core.auth.get_user", lambda *args, **kwargs: None)

    @app.get("/manager-action")
    @require_permission("order:write")
    async def manager_action() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/staff-view")
    async def staff_view(current_user: User = Depends(require_permission("order:read"))) -> dict[str, list[str] | str]:
        return {"user": current_user.username, "roles": current_user.roles}

    return TestClient(app)


def test_manager_route_allows_manager_and_admin(client: TestClient) -> None:
    admin_token = _make_token(1, "admin", ["admin"], [1])
    manager_token = _make_token(2, "manager", ["manager"], [1])

    admin_response = client.get("/manager-action", headers=_auth_headers(admin_token))
    manager_response = client.get("/manager-action", headers=_auth_headers(manager_token))

    assert admin_response.status_code == 200
    assert manager_response.status_code == 200


def test_manager_route_blocks_staff(client: TestClient) -> None:
    staff_token = _make_token(3, "staff", ["staff"], [1])
    response = client.get("/manager-action", headers=_auth_headers(staff_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "Missing required permission: order:write"


def test_staff_view_returns_user_from_context(client: TestClient) -> None:
    staff_token = _make_token(4, "waiter", ["staff"], [7])
    response = client.get("/staff-view", headers=_auth_headers(staff_token, tenant_id=7))
    assert response.status_code == 200
    data = response.json()
    assert data["user"] == "waiter"
    assert data["roles"] == ["staff"]


def test_tenant_mismatch_denied(client: TestClient) -> None:
    manager_token = _make_token(5, "manager", ["manager"], [5])
    response = client.get("/manager-action", headers=_auth_headers(manager_token, tenant_id=99))
    assert response.status_code == 403
    assert response.json()["detail"] == "Valid tenant selection required"


def test_missing_token_yields_forbidden(client: TestClient) -> None:
    response = client.get("/manager-action")
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant context required for this operation"
