from unittest.mock import Mock

import jwt
import pytest
from models.user import User
from routers import users as users_router
from security import create_access_token, verify_password
from sqlalchemy import select


def test_registration_returns_public_profile_and_stores_a_password_hash(client, db_session):
    response = client.post("/users", json={"email": "new@example.com", "password": "abcde"})

    assert response.status_code == 201
    profile = response.json()
    assert set(profile) == {"id", "email"}
    assert profile["email"] == "new@example.com"
    stored_user = db_session.get(User, profile["id"])
    assert stored_user.email == profile["email"]
    assert stored_user.password_hash != "abcde"
    assert verify_password("abcde", stored_user.password_hash) is True


def test_duplicate_email_is_rejected_and_another_registration_still_succeeds(
    client, registered_user, db_session
):
    duplicate = client.post(
        "/users", json={"email": registered_user["email"], "password": "other-password"}
    )
    another = client.post("/users", json={"email": "another@example.com", "password": "abcde"})

    assert duplicate.status_code == 409
    assert another.status_code == 201
    assert len(db_session.scalars(select(User)).all()) == 2
    original = db_session.get(User, registered_user["id"])
    assert verify_password("abcde", original.password_hash) is True


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"email": "invalid-email", "password": "abcde"}, id="bad-email"),
        pytest.param({"email": "new@example.com", "password": "abcd"}, id="short-password"),
        pytest.param({"password": "private-test-password"}, id="missing-email"),
        pytest.param({"email": "new@example.com"}, id="missing-password"),
        pytest.param({"email": "new@example.com", "password": None}, id="null-password"),
    ],
)
def test_registration_validation_redacts_input_and_creates_no_user(client, db_session, payload):
    response = client.post("/users", json=payload)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors
    assert all(set(error) == {"loc", "msg", "type"} for error in errors)
    assert db_session.scalars(select(User)).all() == []


def test_malformed_registration_json_does_not_echo_the_request_body(client):
    response = client.post(
        "/users",
        content='{"password":"private-test-password",',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert "private-test-password" not in response.text
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])


def test_login_returns_a_signed_access_token(client, registered_user, jwt_secret):
    response = client.post(
        "/users/login",
        json={"email": registered_user["email"], "password": "abcde"},
    )

    assert response.status_code == 200
    tokens = response.json()
    assert set(tokens) == {"access_token", "token_type"}
    assert tokens["token_type"] == "bearer"
    claims = jwt.decode(
        tokens["access_token"],
        jwt_secret,
        algorithms=["HS256"],
        options={"require": ["sub", "exp"]},
    )
    assert claims["sub"] == str(registered_user["id"])


def test_wrong_password_and_missing_account_return_the_same_unauthorized_response(
    client, registered_user
):
    wrong_password = client.post(
        "/users/login",
        json={"email": registered_user["email"], "password": "wrong-password"},
    )
    missing_account = client.post(
        "/users/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )

    assert wrong_password.status_code == missing_account.status_code == 401
    assert wrong_password.json() == missing_account.json()
    assert wrong_password.headers["WWW-Authenticate"] == "Bearer"
    assert missing_account.headers["WWW-Authenticate"] == "Bearer"


def test_missing_account_is_rejected_even_if_password_verification_succeeds(client, monkeypatch):
    password_verifier = Mock(return_value=True)
    monkeypatch.setattr(users_router, "verify_password", password_verifier)

    response = client.post(
        "/users/login",
        json={"email": "missing@example.com", "password": "abcde"},
    )

    assert response.status_code == 401
    password_verifier.assert_called_once_with("abcde", users_router.TASKBOARD_DUMMY_HASH)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"password": "private-test-password"}, id="missing-email"),
        pytest.param({"email": "new@example.com"}, id="missing-password"),
        pytest.param(
            {"email": "invalid-email", "password": "private-test-password"},
            id="invalid-email",
        ),
    ],
)
def test_login_validation_redacts_input(client, payload):
    response = client.post("/users/login", json=payload)

    assert response.status_code == 422
    assert "private-test-password" not in response.text
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])


def test_current_profile_matches_the_token(client, registered_user, auth_headers):
    response = client.get("/users/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == registered_user


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic dGVzdDp0ZXN0", "Bearer invalid-token"],
    ids=["missing-token", "wrong-scheme", "malformed-token"],
)
def test_current_profile_requires_valid_authentication(client, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get("/users/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_current_profile_rejects_a_token_for_a_deleted_user(
    client, registered_user, auth_headers, db_session
):
    db_session.delete(db_session.get(User, registered_user["id"]))
    db_session.commit()

    response = client.get("/users/me", headers=auth_headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_current_profile_rejects_a_token_for_an_unknown_user(client):
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {create_access_token(999999)}"},
    )

    assert response.status_code == 401


def test_other_validation_errors_keep_the_default_format(client, auth_headers):
    response = client.get("/boards/not-an-integer", headers=auth_headers)

    assert response.status_code == 422
    assert response.json()["detail"][0]["input"] == "not-an-integer"
