"""Check safe local configuration generation and import-time behavior."""

import importlib
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from main import app

from scripts.init_env import initialize_env


def test_env_initialization_creates_distinct_keys_without_overwriting(tmp_path):
    example = Path(__file__).resolve().parents[2] / ".env.example"
    destination = tmp_path / ".env"
    assert initialize_env(destination, example) is True
    initial = destination.read_bytes()
    values = dotenv_values(destination)
    assert len(values["TASKBOARD_JWT_SECRET"]) >= 64
    assert len(values["DJANGO_SECRET_KEY"]) >= 64
    assert values["TASKBOARD_JWT_SECRET"] != values["DJANGO_SECRET_KEY"]
    assert initialize_env(destination, example) is False
    assert destination.read_bytes() == initial


def test_importing_table_setup_does_not_write_to_the_database(monkeypatch):
    import database

    def unexpected_write(*args, **kwargs):
        raise AssertionError("Importing table setup must not execute DDL")

    monkeypatch.setattr(database.Base.metadata, "create_all", unexpected_write)
    importlib.reload(importlib.import_module("create_tables"))


def test_api_startup_requires_a_signing_key(monkeypatch):
    monkeypatch.delenv("TASKBOARD_JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="Set TASKBOARD_JWT_SECRET"), TestClient(app):
        pass
