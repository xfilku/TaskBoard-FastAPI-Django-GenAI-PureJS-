import secrets

import database
import pytest
from fastapi.testclient import TestClient
from main import app
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import Session


@pytest.fixture
def jwt_secret(monkeypatch):
    secret = secrets.token_hex(32)
    monkeypatch.setenv("TASKBOARD_JWT_SECRET", secret)
    return secret


@pytest.fixture
def test_engine(tmp_path, monkeypatch):
    database_url = URL.create("sqlite", database=str(tmp_path / "test.db"))
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        hide_parameters=True,
    )
    event.listen(engine, "connect", database.enable_foreign_keys)
    monkeypatch.setattr(database, "engine", engine)

    try:
        database.Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def client(test_engine, jwt_secret):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session(test_engine):
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def registered_user(client):
    response = client.post(
        "/users",
        json={"email": "owner@example.com", "password": "abcde"},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def auth_headers(client, registered_user):
    response = client.post(
        "/users/login",
        json={"email": registered_user["email"], "password": "abcde"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def other_auth_headers(client):
    credentials = {"email": "other@example.com", "password": "abcde"}
    registration = client.post("/users", json=credentials)
    assert registration.status_code == 201, registration.text
    login = client.post("/users/login", json=credentials)
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture
def board(client, auth_headers):
    response = client.post("/boards", json={"name": "Project work"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def task(client, auth_headers, board):
    response = client.post(
        f"/boards/{board['id']}/tasks",
        json={"title": "Write tests"},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()
