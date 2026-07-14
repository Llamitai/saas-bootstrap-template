from unittest.mock import ANY
from uuid import uuid4

import pytest
import requests
from expects import equal, expect

from src.common.domain.constants.status import HTTP_200_OK, HTTP_201_CREATED
from tests.api.conftest import BASE_URL, LoginTestContext

MEMBER_PASSWORD = "pass1234567890"


@pytest.fixture(scope="session")
def tenant_member_payloads() -> list[dict]:
    suffix = uuid4().hex[:8]
    return [
        {
            "email": f"tenant-user1-{suffix}@test.com",
            "password": MEMBER_PASSWORD,
            "firstName": "John",
            "lastName": "Doe",
        },
        {
            "email": f"tenant-user2-{suffix}@test.com",
            "password": MEMBER_PASSWORD,
            "firstName": "Jane",
            "lastName": "Smith",
        },
    ]


def _tenant_headers(login_user: LoginTestContext) -> dict:
    return {
        "Authorization": f"Bearer {login_user.access_token}",
        "x-tenant": login_user.tenant_slug,
    }


@pytest.fixture(scope="session")
def tenant_members(login_user: LoginTestContext, tenant_member_payloads: list[dict]) -> list[dict]:
    headers = _tenant_headers(login_user)
    invite_response = requests.post(
        url=f"{BASE_URL}/v1/tenants/invitations",
        headers=headers,
        json={
            "members": [{"email": payload["email"], "roleSlug": "member"} for payload in tenant_member_payloads],
        },
        timeout=30,
    )

    expect(invite_response.status_code).to(equal(HTTP_201_CREATED))
    invitations = invite_response.json()["data"]["invitations"]
    expect(len(invitations)).to(equal(len(tenant_member_payloads)))

    for payload, invitation in zip(tenant_member_payloads, invitations, strict=True):
        accept_response = requests.post(
            url=f"{BASE_URL}/v1/invitations/{invitation['token']}/accept",
            json={
                "password": payload["password"],
                "firstName": payload["firstName"],
                "lastName": payload["lastName"],
            },
            timeout=30,
        )
        expect(accept_response.status_code).to(equal(HTTP_200_OK))

    list_response = requests.get(
        url=f"{BASE_URL}/v1/tenants/users",
        headers=headers,
        timeout=30,
    )
    expect(list_response.status_code).to(equal(HTTP_200_OK))

    members_by_email = {
        member["emailAddress"]["email"]: member
        for member in list_response.json()["data"]
        if member.get("emailAddress")
    }
    missing_emails = [
        payload["email"] for payload in tenant_member_payloads if payload["email"] not in members_by_email
    ]
    if missing_emails:
        pytest.fail(f"Accepted members not found in tenant users list: {missing_emails}")

    members = [members_by_email[payload["email"]] for payload in tenant_member_payloads]
    return members


@pytest.mark.api
def test_create_tenant_users(tenant_members: list[dict], tenant_member_payloads: list[dict]):
    """Test tenant members can be created through invitation acceptance."""
    expect([member["emailAddress"]["email"] for member in tenant_members]).to(
        equal([payload["email"] for payload in tenant_member_payloads])
    )


@pytest.mark.api
def test_tenant_user_list(login_user: LoginTestContext, tenant_members: list[dict]):
    """Test listing tenant users"""
    headers = _tenant_headers(login_user)

    response = requests.get(
        url=f"{BASE_URL}/v1/tenants/users",
        headers=headers,
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_200_OK))
    # The shared dev database may hold members from earlier sessions; assert
    # this session's members are listed instead of an exact total.
    listed_ids = {member["uuid"] for member in response.json()["data"]}
    expected_ids = {member["uuid"] for member in tenant_members}
    expect(expected_ids - listed_ids).to(equal(set()))


@pytest.mark.api
def test_get_tenant_user(login_user: LoginTestContext, tenant_members: list[dict]):
    """Test getting a single tenant user by ID"""
    headers = _tenant_headers(login_user)

    tenant_user_id = tenant_members[0]["uuid"]
    response = requests.get(
        url=f"{BASE_URL}/v1/tenants/users/{tenant_user_id}",
        headers=headers,
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_200_OK))
    data = response.json()["data"]
    expect(data["uuid"]).to(equal(tenant_user_id))


@pytest.mark.api
def test_update_tenant_user(
    login_user: LoginTestContext,
    tenant_members: list[dict],
    tenant_member_payloads: list[dict],
):
    """Test updating a tenant user"""
    headers = _tenant_headers(login_user)

    tenant_user_id = tenant_members[0]["uuid"]
    updated_email = f"updated-{tenant_member_payloads[0]['email']}"
    response = requests.put(
        url=f"{BASE_URL}/v1/tenants/users/{tenant_user_id}",
        headers=headers,
        json={
            "email": updated_email,
            "firstName": "Updated John",
            "lastName": "Updated Doe",
            "isOwner": False,
            "status": "INACTIVE",
            "phoneNumber": None,
        },
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_200_OK))
    data = response.json()["data"]
    expect(data).to(
        equal(
            {
                "uuid": ANY,
                "firstName": "Updated John",
                "lastName": "Updated Doe",
                "phoneNumber": None,
                "emailAddress": ANY,
                "isOwner": False,
                "isSupport": False,
                "photoUrl": None,
                "status": "INACTIVE",
                "tenantRole": ANY,
                "createdAt": ANY,
            }
        )
    )


@pytest.mark.api
def test_delete_tenant_user(login_user: LoginTestContext, tenant_members: list[dict]):
    """Test deleting a tenant user"""
    headers = _tenant_headers(login_user)

    tenant_user_id = tenant_members[1]["uuid"]
    response = requests.delete(
        url=f"{BASE_URL}/v1/tenants/users/{tenant_user_id}",
        headers=headers,
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_200_OK))
