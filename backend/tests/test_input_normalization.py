"""Protect database fields from blank names and preserve PATCH semantics."""

import pytest


@pytest.mark.parametrize("name", ["   ", "\t\n ", "  ab  "])
def test_board_creation_rejects_names_too_short_after_trimming(client, auth_headers, name):
    response = client.post("/boards", json={"name": name}, headers=auth_headers)
    assert response.status_code == 422


def test_board_creation_trims_outer_whitespace(client, auth_headers):
    response = client.post("/boards", json={"name": "  Project work  "}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Project work"


@pytest.mark.parametrize("title", ["     ", "\t\n   ", "  todo  "])
def test_task_creation_rejects_titles_too_short_after_trimming(client, auth_headers, board, title):
    response = client.post(
        f"/boards/{board['id']}/tasks", json={"title": title}, headers=auth_headers
    )
    assert response.status_code == 422


def test_task_patch_trims_title_without_resetting_completion(client, auth_headers, board, task):
    path = f"/boards/{board['id']}/tasks/{task['id']}"
    response = client.patch(path, json={"is_done": True}, headers=auth_headers)
    assert response.status_code == 200
    response = client.patch(path, json={"title": "  Updated task title  "}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated task title"
    assert response.json()["is_done"] is True
