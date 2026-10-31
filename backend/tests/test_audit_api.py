import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.identity import Organization, OrganizationMember, User


def create_authenticated_user(client: TestClient, org_name: str = "Test Org") -> dict:
    """Helper to register a user and get auth header + details."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"user_{unique_id}@sentinel-test.com"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": f"User {unique_id}",
            "email": email,
            "password": "Password123!",
            "organization_name": org_name,
        },
    )
    assert res.status_code == 201
    data = res.json()
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": data["user_id"],
        "email": email,
        "org_id": data["organization_id"],
        "org_name": org_name,
    }


def test_organization_crud(client: TestClient):
    user_a = create_authenticated_user(client, "Alpha Corp")
    headers = user_a["headers"]

    # List organizations
    list_res = client.get("/api/organizations", headers=headers)
    assert list_res.status_code == 200
    orgs = list_res.json()
    assert len(orgs) >= 1
    assert any(o["id"] == user_a["org_id"] for o in orgs)

    # Create another organization
    create_res = client.post(
        "/api/organizations",
        json={"name": "Beta Division"},
        headers=headers,
    )
    assert create_res.status_code == 201
    beta_org = create_res.json()
    assert beta_org["name"] == "Beta Division"
    assert beta_org["role"] == "owner"

    # Update organization name
    patch_res = client.patch(
        f"/api/organizations/{beta_org['id']}",
        json={"name": "Beta Division Global"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Beta Division Global"


def test_member_management_and_rbac(client: TestClient):
    owner = create_authenticated_user(client, "Security Operations")
    org_id = owner["org_id"]
    headers = owner["headers"]

    # Register a second user (without org initially, or with their own org)
    member_user = create_authenticated_user(client, "Member Personal Org")

    # Add member_user to owner's org as 'auditor'
    add_res = client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": member_user["email"], "role": "auditor"},
        headers=headers,
    )
    assert add_res.status_code == 201
    member_record = add_res.json()
    assert member_record["role"] == "auditor"
    assert member_record["email"] == member_user["email"]

    # List members
    members_res = client.get(f"/api/organizations/{org_id}/members", headers=headers)
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 2

    # Promote auditor to admin
    role_res = client.patch(
        f"/api/organizations/{org_id}/members/{member_user['user_id']}",
        json={"role": "admin"},
        headers=headers,
    )
    assert role_res.status_code == 200
    assert role_res.json()["role"] == "admin"

    # Attempt to demote/remove the last owner (should fail with 400)
    demote_owner_res = client.patch(
        f"/api/organizations/{org_id}/members/{owner['user_id']}",
        json={"role": "viewer"},
        headers=headers,
    )
    assert demote_owner_res.status_code == 400
    assert "last owner" in demote_owner_res.json()["detail"].lower()

    # Remove the admin member
    del_res = client.delete(
        f"/api/organizations/{org_id}/members/{member_user['user_id']}",
        headers=headers,
    )
    assert del_res.status_code == 204


def test_audit_lifecycle_and_runs(client: TestClient):
    user = create_authenticated_user(client, "FinTech Cloud")
    org_id = user["org_id"]
    headers = user["headers"]

    # 1. Create audit
    create_res = client.post(
        f"/api/organizations/{org_id}/audits",
        json={
            "name": "Core Banking Payment Gateway v2.4",
            "application_name": "Tier-0 Production VPC",
            "description": "Continuous multi-agent audit across PCI-DSS and SOC 2",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    audit = create_res.json()
    audit_id = audit["id"]
    assert audit["name"] == "Core Banking Payment Gateway v2.4"
    assert audit["status"] == "draft"

    # 2. List audits with search
    list_res = client.get(
        f"/api/organizations/{org_id}/audits?search=Gateway",
        headers=headers,
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert list_data["items"][0]["id"] == audit_id

    # 3. Create Audit Run #1
    run1_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/runs",
        json={"summary": "Initial baseline run", "config": {"depth": "full"}},
        headers=headers,
    )
    assert run1_res.status_code == 201
    run1 = run1_res.json()
    assert run1["run_number"] == 1
    assert run1["status"] == "queued"

    # 4. Create Audit Run #2 (sequential run numbering)
    run2_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/runs",
        json={"summary": "Follow-up verification run", "config": {"depth": "fast"}},
        headers=headers,
    )
    assert run2_res.status_code == 201
    run2 = run2_res.json()
    assert run2["run_number"] == 2

    # 5. List runs
    runs_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/runs",
        headers=headers,
    )
    assert runs_res.status_code == 200
    runs = runs_res.json()
    assert len(runs) == 2
    assert runs[0]["run_number"] == 2
    assert runs[1]["run_number"] == 1

    # 6. Check audit details reflected runs
    audit_detail_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}",
        headers=headers,
    )
    assert audit_detail_res.status_code == 200
    detail = audit_detail_res.json()
    assert detail["runs_count"] == 2
    assert detail["latest_run"]["run_number"] == 2

    # 7. Update audit
    patch_res = client.patch(
        f"/api/organizations/{org_id}/audits/{audit_id}",
        json={"name": "Core Banking Payment Gateway v2.5"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Core Banking Payment Gateway v2.5"

    # 8. Archive audit
    archive_res = client.delete(
        f"/api/organizations/{org_id}/audits/{audit_id}",
        headers=headers,
    )
    assert archive_res.status_code == 204

    # Verification: default list excludes archived audits
    after_archive_res = client.get(
        f"/api/organizations/{org_id}/audits",
        headers=headers,
    )
    assert after_archive_res.status_code == 200
    assert not any(a["id"] == audit_id for a in after_archive_res.json()["items"])


def test_cross_tenant_isolation(client: TestClient):
    # Org A
    user_a = create_authenticated_user(client, "Tenant Alpha")
    org_a_id = user_a["org_id"]
    headers_a = user_a["headers"]

    # Org B
    user_b = create_authenticated_user(client, "Tenant Beta")
    org_b_id = user_b["org_id"]
    headers_b = user_b["headers"]

    # User A creates an audit in Org A
    create_res = client.post(
        f"/api/organizations/{org_a_id}/audits",
        json={
            "name": "Secret Alpha System",
            "application_name": "Alpha App",
        },
        headers=headers_a,
    )
    assert create_res.status_code == 201
    audit_a_id = create_res.json()["id"]

    # User B attempts to access Org A's audit (should return 404 to avoid tenant leaking)
    unauth_res = client.get(
        f"/api/organizations/{org_a_id}/audits/{audit_a_id}",
        headers=headers_b,
    )
    assert unauth_res.status_code == 404

    # User B attempts to list Org A's audits
    unauth_list_res = client.get(
        f"/api/organizations/{org_a_id}/audits",
        headers=headers_b,
    )
    assert unauth_list_res.status_code == 404

    # User B attempts to create an audit run in Org A
    unauth_run_res = client.post(
        f"/api/organizations/{org_a_id}/audits/{audit_a_id}/runs",
        json={"summary": "Malicious run"},
        headers=headers_b,
    )
    assert unauth_run_res.status_code == 404
