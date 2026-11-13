"""Define public account data and keep plaintext passwords out of model reprs."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class UserCreate(BaseModel):
    """Validate registration input using the project's existing password policy."""

    email: EmailStr
    password: SecretStr = Field(min_length=5)


class UserResponse(BaseModel):
    """Expose an account ID and email while excluding its password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class UserLogin(BaseModel):
    """Accept credentials without applying new-account rules to existing users."""

    email: EmailStr
    password: SecretStr


class TokenResponse(BaseModel):
    """Return the bearer access token issued after successful authentication."""

    access_token: str
    token_type: str
