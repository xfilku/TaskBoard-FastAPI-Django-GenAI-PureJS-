import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from models.board import Board
from models.user import User
from security import (
    create_access_token,
    get_current_user,
    get_current_user_id,
    get_own_board,
    hash_password,
    verify_password,
)
from sqlalchemy.orm import Session


@pytest.mark.parametrize("password", ["abcde", "zażółć gęślą jaźń"])
def test_password_hash_can_be_verified(password):
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True


def test_wrong_password_is_rejected():
    password_hash = hash_password("abcde")

    assert verify_password("wrong-password", password_hash) is False


def test_access_token_contains_user_id_and_expires_in_thirty_minutes(jwt_secret):
    before = datetime.now(UTC)
    token = create_access_token(7)
    after = datetime.now(UTC)
    claims = jwt.decode(
        token,
        jwt_secret,
        algorithms=["HS256"],
        options={"require": ["sub", "exp"]},
    )

    assert claims["sub"] == "7"
    assert int(before.timestamp()) + 1800 <= claims["exp"]
    assert claims["exp"] <= int(after.timestamp()) + 1800


def test_valid_token_returns_integer_user_id(jwt_secret):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_access_token(7))

    user_id = get_current_user_id(credentials)

    assert user_id == 7
    assert isinstance(user_id, int)


def test_malformed_token_is_rejected(jwt_secret):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")

    with pytest.raises(HTTPException) as error:
        get_current_user_id(credentials)

    assert error.value.status_code == 401
    assert error.value.headers["WWW-Authenticate"] == "Bearer"


def test_expired_token_is_rejected(jwt_secret):
    token = jwt.encode(
        {"sub": "7", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        jwt_secret,
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as error:
        get_current_user_id(credentials)

    assert error.value.status_code == 401
    assert error.value.headers["WWW-Authenticate"] == "Bearer"


def test_token_signed_with_another_key_is_rejected(jwt_secret):
    token = jwt.encode(
        {"sub": "7", "exp": datetime.now(UTC) + timedelta(minutes=30)},
        secrets.token_hex(32),
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as error:
        get_current_user_id(credentials)

    assert error.value.status_code == 401


@pytest.mark.parametrize("missing_claim", ["sub", "exp"])
def test_token_requires_subject_and_expiration(jwt_secret, missing_claim):
    claims = {
        "sub": "7",
        "exp": datetime.now(UTC) + timedelta(minutes=30),
    }
    del claims[missing_claim]
    token = jwt.encode(claims, jwt_secret, algorithm="HS256")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as error:
        get_current_user_id(credentials)

    assert error.value.status_code == 401


@pytest.mark.parametrize("subject", [None, 7, "not-an-integer", "7.5"])
def test_invalid_token_subject_is_rejected(jwt_secret, subject):
    token = jwt.encode(
        {"sub": subject, "exp": datetime.now(UTC) + timedelta(minutes=30)},
        jwt_secret,
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as error:
        get_current_user_id(credentials)

    assert error.value.status_code == 401


def test_token_with_another_algorithm_is_rejected(jwt_secret):
    token = jwt.encode(
        {"sub": "7", "exp": datetime.now(UTC) + timedelta(minutes=30)},
        jwt_secret,
        algorithm="HS384",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as error:
        get_current_user_id(credentials)

    assert error.value.status_code == 401


def test_current_user_returns_the_loaded_user():
    session = Mock(spec=Session)
    user = User(id=7, email="owner@example.com")
    session.get.return_value = user

    assert get_current_user(user_id=7, db=session) is user


def test_current_user_rejects_a_deleted_account():
    session = Mock(spec=Session)
    session.get.return_value = None

    with pytest.raises(HTTPException) as error:
        get_current_user(user_id=7, db=session)

    assert error.value.status_code == 401
    assert error.value.headers["WWW-Authenticate"] == "Bearer"


def test_owner_receives_the_requested_board():
    session = Mock(spec=Session)
    board = Board(id=1, owner_id=7)
    session.get.return_value = board

    assert get_own_board(1, user=User(id=7), db=session) is board


@pytest.mark.parametrize("owner_id", [8, None], ids=["another-owner", "legacy-board"])
def test_inaccessible_board_is_forbidden(owner_id):
    session = Mock(spec=Session)
    session.get.return_value = Board(id=1, owner_id=owner_id)

    with pytest.raises(HTTPException) as error:
        get_own_board(1, user=User(id=7), db=session)

    assert error.value.status_code == 403


def test_missing_board_is_not_found():
    session = Mock(spec=Session)
    session.get.return_value = None

    with pytest.raises(HTTPException) as error:
        get_own_board(999, user=User(id=7), db=session)

    assert error.value.status_code == 404


def test_missing_user_is_rejected_before_loading_a_board():
    session = Mock(spec=Session)

    with pytest.raises(HTTPException) as error:
        get_own_board(1, user=None, db=session)

    assert error.value.status_code == 401
    assert error.value.headers["WWW-Authenticate"] == "Bearer"
    session.get.assert_not_called()
