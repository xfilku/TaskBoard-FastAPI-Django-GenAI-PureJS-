from fastapi import FastAPI
from routers import boards

app = FastAPI(title="TaskBoard API")

app.include_router(boards.router)


@app.get("/health", tags=["health"])
def health_check():
    """Sprawdza status aplikacji"""
    return {
            "status": "ok",
            "application": "TaskBoard",
            "version": "0.0.1"
        }