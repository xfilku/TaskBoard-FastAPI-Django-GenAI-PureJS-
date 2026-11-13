"""Register accounts, verify credentials and expose the current public profile."""

from sqlite3 import SQLITE_CONSTRAINT_UNIQUE

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.user import User
from schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from security import create_access_token, get_current_user, hash_password, verify_password
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

TASKBOARD_DUMMY_HASH = hash_password("EKSTRATAJNYKLUCZSPECJALNY")

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=201, response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)) -> User:
    """Store a password hash and reject duplicate email addresses with HTTP 409."""
    new_user = User(email=user.email, password_hash=hash_password(user.password.get_secret_value()))

    db.add(new_user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlite_errorcode", None) == SQLITE_CONSTRAINT_UNIQUE:
            raise HTTPException(
                status_code=409, detail="Konto z tym adresem e-mail już istnieje."
            ) from exc
        raise

    db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Wprowadzone dane logowania są nieprawidłowe."}},
)
def login_user(data: UserLogin, db: Session = Depends(get_db)) -> dict[str, str]:
    """Issue a token after verifying credentials with a generic failure response.

    Unknown accounts still perform a password verification against a dummy hash
    to reduce the timing difference between missing users and incorrect passwords.
    """
    statement = select(User).where(User.email == data.email)
    user = db.scalars(statement).first()

    if user is None:
        stored_hash = TASKBOARD_DUMMY_HASH
    else:
        stored_hash = user.password_hash

    password_ok = verify_password(data.password.get_secret_value(), stored_hash)

    if user is None or not password_ok:
        raise HTTPException(
            status_code=401,
            detail="Wprowadzone dane logowania są nieprawidłowe.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id)

    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def read_current_user(user: User = Depends(get_current_user)) -> User:
    """Return the authenticated profile without its stored password hash."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Coś poszło nie tak... Spróbuj zalogować się ponownie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
