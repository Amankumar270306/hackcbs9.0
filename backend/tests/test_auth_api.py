import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import verify_password
from app.database.models.auth import RefreshToken
from app.database.models.identity import Organization, OrganizationMember, User


def test_registration_success(client: TestClient, db_session: Session):
    unique_email = f"test_owner_{uuid.uuid4().hex[:8]}@compliance-sentinel.io"
    payload = {
        "full_name": "Alice Auditor",
        "email": unique_email,
        "password": "SuperSecretPassword123!",
        "organization_name": "Alice CyberSec",
    }

    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["email"] == unique_email
    assert data["role"] == "owner"
    assert data["organization_name"] == "Alice CyberSec"
    assert "access_token" in data
    assert settings.COOKIE_NAME in res.cookies

    # Verify user exists in database and password was hashed with Argon2id
    stmt = select(User).where(User.email == unique_email)
    user = db_session.scalars(stmt).first()
    assert user is not None
    assert user.hashed_password.startswith("$argon2id$")
    assert verify_password("SuperSecretPassword123!", user.hashed_password)


def test_registration_duplicate_email(client: TestClient):
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@compliance-sentinel.io"
    payload = {
        "full_name": "Bob Builder",
        "email": unique_email,
        "password": "Password123!",
        "organization_name": "Bob Industries",
    }

    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_login_flow(client: TestClient):
    unique_email = f"login_{uuid.uuid4().hex[:8]}@compliance-sentinel.io"
    password = "CorrectHorseBatteryStaple1!"

    # Register
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Login Tester",
            "email": unique_email,
            "password": password,
            "organization_name": "Login Corp",
        },
    )

    # Valid Login
    res = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert res.status_code == 200
    login_data = res.json()
    assert login_data["email"] == unique_email
    assert login_data["role"] == "owner"
    assert "access_token" in login_data
    assert settings.COOKIE_NAME in res.cookies

    # Invalid password
    bad_res = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "WrongPassword!"},
    )
    assert bad_res.status_code == 401


def test_inactive_user_cannot_login(client: TestClient, db_session: Session):
    unique_email = f"inactive_{uuid.uuid4().hex[:8]}@compliance-sentinel.io"
    password = "ValidPassword123!"

    client.post(
        "/api/auth/register",
        json={
            "full_name": "Inactive User",
            "email": unique_email,
            "password": password,
            "organization_name": "Ghost Org",
        },
    )

    # Deactivate user
    stmt = select(User).where(User.email == unique_email)
    user = db_session.scalars(stmt).first()
    user.is_active = False
    db_session.commit()

    res = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert res.status_code == 403
    assert "inactive" in res.json()["detail"].lower()


def test_current_user_profile_me(client: TestClient):
    unique_email = f"me_{uuid.uuid4().hex[:8]}@compliance-sentinel.io"
    reg_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Me Tester",
            "email": unique_email,
            "password": "Password123!",
            "organization_name": "Me Testing Org",
        },
    )
    token = reg_res.json()["access_token"]

    # Call /api/auth/me with Bearer token
    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    me_data = res.json()
    assert me_data["email"] == unique_email
    assert me_data["full_name"] == "Me Tester"
    assert me_data["is_active"] is True
    assert len(me_data["organizations"]) >= 1
    assert me_data["organizations"][0]["role"] == "owner"
    assert me_data["organizations"][0]["organization_name"] == "Me Testing Org"


def test_token_refresh_and_logout(client: TestClient):
    unique_email = f"refresh_{uuid.uuid4().hex[:8]}@compliance-sentinel.io"
    reg_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Refresh Tester",
            "email": unique_email,
            "password": "Password123!",
            "organization_name": "Refresh Org",
        },
    )
    refresh_cookie = reg_res.cookies.get(settings.COOKIE_NAME)
    assert refresh_cookie is not None

    # Rotate refresh token
    ref_res = client.post(
        "/api/auth/refresh",
        cookies={settings.COOKIE_NAME: refresh_cookie},
    )
    assert ref_res.status_code == 200
    ref_data = ref_res.json()
    assert "access_token" in ref_data
    new_refresh_cookie = ref_res.cookies.get(settings.COOKIE_NAME)
    assert new_refresh_cookie is not None
    assert new_refresh_cookie != refresh_cookie  # Rotated!

    # Logout
    logout_res = client.post(
        "/api/auth/logout",
        cookies={settings.COOKIE_NAME: new_refresh_cookie},
    )
    assert logout_res.status_code == 200

    # Old cookie or revoked cookie cannot refresh anymore
    stale_res = client.post(
        "/api/auth/refresh",
        cookies={settings.COOKIE_NAME: new_refresh_cookie},
    )
    assert stale_res.status_code == 401
