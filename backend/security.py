"""Hash account passwords and authorize JWT-authenticated access to owned boards."""

import os
from datetime import UTC, datetime, timedelta

import jwt
from database import get_db
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models.board import Board
from models.user import User
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

taskboard_bearer = HTTPBearer()

taskboard_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password with pwdlib's recommended Argon2 configuration."""
    return taskboard_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Compare a plaintext password with its stored hash without logging either value."""
    return taskboard_hasher.verify(password, stored_hash)


def create_access_token(user_id: int) -> str:
    """Sign a 30-minute HS256 token whose subject is the account ID.

    The signing key comes from TASKBOARD_JWT_SECRET, loaded from the environment
    or the root .env file by the database configuration.
    """
    secret_key = os.environ["TASKBOARD_JWT_SECRET"]
    expires_at = datetime.now(UTC) + timedelta(minutes=30)

    payload = {"sub": str(user_id), "exp": expires_at}

    return jwt.encode(payload, secret_key, algorithm="HS256")


def get_current_user_id(auth: HTTPAuthorizationCredentials = Depends(taskboard_bearer)) -> int:
    """Validate the token signature, expiry and subject, or raise HTTP 401."""
    try:
        claims = jwt.decode(
            auth.credentials,
            os.environ["TASKBOARD_JWT_SECRET"],
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
        result = int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Coś poszło nie tak... Spróbuj zalogować się ponownie.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return result


def get_current_user(
    user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)
) -> User:
    """Load the token's account, rejecting tokens belonging to deleted users."""
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Coś poszło nie tak... Spróbuj zalogować się ponownie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_own_board(
    board_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Board:
    """Return an owned board or raise 401, 404 or 403 for invalid access.

    Legacy boards without an owner are inaccessible. Ownership must be checked
    before reading or mutating any task belonging to the board.
    """
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Coś poszło nie tak... Spróbuj zalogować się ponownie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    board = db.get(Board, board_id)

    if board is None:
        raise HTTPException(status_code=404, detail="Tablica o wskazanym ID nie istnieje.")

    if board.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Nie posiadasz uprawnień do tej tablicy.")

    return board
