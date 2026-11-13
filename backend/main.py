"""Expose the TaskBoard API and redact credentials from authentication errors."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from routers import ai, boards, tasks, users
from starlette.responses import Response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Reject startup without a signing key before accepting account requests."""
    if not os.environ.get("TASKBOARD_JWT_SECRET", "").strip():
        raise RuntimeError("Set TASKBOARD_JWT_SECRET in the environment or the root .env file.")
    yield


app = FastAPI(title="TaskBoard API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
    """Omit submitted credentials from registration and login validation responses."""
    if request.method == "POST" and (
        request.url.path == "/users" or request.url.path == "/users/login"
    ):
        details = []
        for error in exc.errors():
            details.append(
                {
                    "loc": error["loc"],
                    "msg": error["msg"],
                    "type": error["type"],
                }
            )
        return JSONResponse(status_code=422, content={"detail": details})
    return await request_validation_exception_handler(request, exc)


app.include_router(boards.router)
app.include_router(tasks.router)
app.include_router(users.router)
app.include_router(ai.router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return application identity and liveness without exposing configuration."""
    return {"status": "ok", "application": "TaskBoard", "version": "0.0.1"}
