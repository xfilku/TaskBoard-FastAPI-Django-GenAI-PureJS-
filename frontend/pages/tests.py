"""Exercise session protection, API failures, forms and safe HTML rendering."""

from unittest.mock import patch

import httpx
from django.contrib.messages import get_messages
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from pages import api_client
from pages.forms import BoardCreateForm, CreateTaskForm, LoginForm, RegisterForm


def status_error(status):
    request = httpx.Request("GET", "http://api.test/boards")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("API rejected request", request=request, response=response)


class ProtectedViewTests(TestCase):
    def setUp(self):
        session = self.client.session
        session["access_token"] = "test-session-token"
        session.save()

    def test_anonymous_requests_never_contact_the_api(self):
        self.client.session.flush()
        routes = [
            ("home", {}, "get", "get_boards"),
            ("board_create", {}, "post", "create_board"),
            ("board_detail", {"board_id": 1}, "post", "create_task"),
            ("update_task", {"board_id": 1, "task_id": 2}, "post", "patch_task"),
            ("delete_task", {"board_id": 1, "task_id": 2}, "post", "delete_task"),
            ("delete_board", {"board_id": 1}, "post", "delete_board"),
            ("edit_task", {"board_id": 1, "task_id": 2}, "get", "get_task"),
            ("edit_task", {"board_id": 1, "task_id": 2}, "post", "patch_task"),
        ]
        for route, kwargs, method, api_method in routes:
            with (
                self.subTest(route=route, method=method),
                patch(f"pages.views.{api_method}") as api,
            ):
                response = getattr(self.client, method)(reverse(route, kwargs=kwargs))
                self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
                api.assert_not_called()

    def test_mutation_routes_reject_get_requests(self):
        routes = [
            ("logout", {}),
            ("delete_board", {"board_id": 1}),
            ("delete_task", {"board_id": 1, "task_id": 2}),
            ("update_task", {"board_id": 1, "task_id": 2}),
        ]
        for route, kwargs in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route, kwargs=kwargs)).status_code, 405)

    def test_csrf_protects_mutations(self):
        client = Client(enforce_csrf_checks=True)
        with patch("pages.views.delete_board") as api:
            response = client.post(reverse("delete_board", args=[1]))
        self.assertEqual(response.status_code, 403)
        api.assert_not_called()

    def test_expired_token_clears_session(self):
        with patch("pages.views.get_boards", side_effect=status_error(401)):
            response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("access_token", self.client.session)

    def test_private_pages_cannot_be_cached(self):
        with patch("pages.views.get_boards", return_value=[]):
            response = self.client.get(reverse("home"))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])

    def test_board_deletion_handles_connection_failure(self):
        with patch("pages.views.delete_board", side_effect=httpx.ConnectError("Offline")):
            response = self.client.post(reverse("delete_board", args=[1]))
        self.assertRedirects(
            response, reverse("board_detail", args=[1]), fetch_redirect_response=False
        )
        self.assertTrue(list(get_messages(response.wsgi_request)))

    def test_nonempty_board_has_actionable_feedback(self):
        with patch("pages.views.delete_board", side_effect=status_error(409)):
            response = self.client.post(reverse("delete_board", args=[1]))
        feedback = " ".join(str(message) for message in get_messages(response.wsgi_request))
        self.assertIn("Najpierw usuń zadania", feedback)

    def test_missing_board_deletion_returns_to_home(self):
        with patch("pages.views.delete_board", side_effect=status_error(404)):
            response = self.client.post(reverse("delete_board", args=[1]))
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_failed_task_edit_keeps_submitted_text(self):
        for error, status in [(httpx.ConnectError("Offline"), 503), (status_error(500), 502)]:
            with self.subTest(status=status), patch("pages.views.patch_task", side_effect=error):
                response = self.client.post(
                    reverse("edit_task", args=[1, 2]), {"title": "Keep this unsaved task title"}
                )
            self.assertContains(response, "Keep this unsaved task title", status_code=status)
            self.assertTrue(response.context["edit_task_form"].is_bound)
            self.assertTrue(response.context["edit_task_form"].non_field_errors())

    def test_invalid_completion_value_never_reaches_api(self):
        with patch("pages.views.patch_task") as api:
            response = self.client.post(reverse("update_task", args=[1, 2]), {"is_done": "maybe"})
        self.assertEqual(response.status_code, 400)
        api.assert_not_called()

    def test_task_completion_sends_a_boolean(self):
        for raw, expected in [("true", True), ("false", False)]:
            with self.subTest(raw=raw), patch("pages.views.patch_task") as api:
                response = self.client.post(reverse("update_task", args=[1, 2]), {"is_done": raw})
            self.assertEqual(response.status_code, 302)
            api.assert_called_once_with(1, 2, {"is_done": expected}, "test-session-token")

    def test_task_edit_serializes_optional_deadline(self):
        response = httpx.Response(
            200, json={"id": 2}, request=httpx.Request("PATCH", "http://api.test/boards/1/tasks/2")
        )
        url = reverse("edit_task", args=[1, 2])
        for posted_date, expected in (
            ({"deadline": "2026-11-30"}, {"deadline": "2026-11-30"}),
            ({"deadline": ""}, {"deadline": None}),
            ({}, {}),
        ):
            with self.subTest(posted_date=posted_date):
                with patch("pages.api_client.httpx.request", return_value=response) as request:
                    result = self.client.post(url, {"title": "Updated task title", **posted_date})

                self.assertEqual(result.status_code, 302)
                self.assertEqual(
                    request.call_args.kwargs["json"], {"title": "Updated task title", **expected}
                )

    def test_invalid_task_form_never_calls_api_write(self):
        with (
            patch("pages.views.create_task") as api,
            patch("pages.views.get_board", return_value={"id": 1, "name": "Project"}),
            patch("pages.views.get_board_tasks", return_value=[]),
        ):
            response = self.client.post(reverse("board_detail", args=[1]), {"title": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["task_form"].errors)
        api.assert_not_called()

    def test_home_outage_renders_a_useful_error_page(self):
        with patch("pages.views.get_boards", side_effect=httpx.ConnectError("Offline")):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.context["error_message"])

    def test_board_access_status_is_preserved(self):
        for status in (403, 404):
            with (
                self.subTest(status=status),
                patch("pages.views.get_board", side_effect=status_error(status)),
            ):
                response = self.client.get(reverse("board_detail", args=[1]))
            self.assertEqual(response.status_code, status)

    def test_board_and_task_names_are_html_escaped(self):
        malicious = '<script>alert("unsafe")</script>'
        with patch("pages.views.get_boards", return_value=[{"id": 1, "name": malicious}]):
            response = self.client.get(reverse("home"))
        self.assertNotContains(response, malicious)
        self.assertContains(response, "&lt;script&gt;")
        with (
            patch("pages.views.get_board", return_value={"id": 1, "name": malicious}),
            patch(
                "pages.views.get_board_tasks",
                return_value=[{"id": 2, "title": malicious, "board_id": 1, "is_done": False}],
            ),
        ):
            response = self.client.get(reverse("board_detail", args=[1]))
        self.assertNotContains(response, malicious)
        self.assertContains(response, "&lt;script&gt;")


class AuthenticationViewTests(TestCase):
    def test_successful_login_rotates_session_and_stores_token(self):
        session = self.client.session
        session["existing"] = "value"
        session.save()
        previous_key = session.session_key
        with patch("pages.views.login_user", return_value={"access_token": "new-token"}):
            response = self.client.post(
                reverse("login"), {"email": "owner@example.com", "password": "abcde"}
            )
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertNotEqual(self.client.session.session_key, previous_key)
        self.assertEqual(self.client.session["access_token"], "new-token")

    def test_failed_login_does_not_render_password(self):
        password = "NeverRenderThisPassword"
        with patch("pages.views.login_user", side_effect=status_error(401)):
            response = self.client.post(
                reverse("login"), {"email": "owner@example.com", "password": password}
            )
        self.assertContains(response, "owner@example.com")
        self.assertNotContains(response, password)
        self.assertNotIn("access_token", self.client.session)

    def test_short_registration_password_is_rejected_locally(self):
        with patch("pages.views.register_user") as api:
            response = self.client.post(
                reverse("register"), {"email": "owner@example.com", "password": "abcd"}
            )
        self.assertTrue(response.context["form"].errors["password"])
        api.assert_not_called()

    def test_duplicate_email_is_attached_to_email_field(self):
        with patch("pages.views.register_user", side_effect=status_error(409)):
            response = self.client.post(
                reverse("register"), {"email": "owner@example.com", "password": "abcde"}
            )
        self.assertTrue(response.context["form"].errors["email"])

    def test_logout_removes_token(self):
        session = self.client.session
        session["access_token"] = "old-token"
        session.save()
        self.client.post(reverse("logout"))
        self.assertNotIn("access_token", self.client.session)


class FormTests(SimpleTestCase):
    def test_titles_and_names_reject_whitespace_only_input(self):
        self.assertFalse(BoardCreateForm({"name": "   "}).is_valid())
        self.assertFalse(CreateTaskForm({"title": "     "}).is_valid())

    def test_password_whitespace_is_preserved(self):
        for form_class in (LoginForm, RegisterForm):
            with self.subTest(form=form_class):
                form = form_class({"email": "owner@example.com", "password": " abcde "})
                self.assertTrue(form.is_valid())
                self.assertEqual(form.cleaned_data["password"], " abcde ")


class APIClientTests(SimpleTestCase):
    def test_authenticated_request_has_timeout_and_bearer_header(self):
        response = httpx.Response(
            200, json=[], request=httpx.Request("GET", "http://api.test/boards")
        )
        with patch("pages.api_client.httpx.request", return_value=response) as request:
            self.assertEqual(api_client.get_boards("token"), [])
        self.assertEqual(request.call_args.kwargs["headers"], {"Authorization": "Bearer token"})
        self.assertEqual(request.call_args.kwargs["timeout"], 5.0)

    def test_delete_accepts_empty_204_response(self):
        response = httpx.Response(204, request=httpx.Request("DELETE", "http://api.test/boards/1"))
        with patch("pages.api_client.httpx.request", return_value=response):
            self.assertIsNone(api_client.delete_board(1, "token"))

    def test_http_errors_propagate_to_views(self):
        response = httpx.Response(403, request=httpx.Request("GET", "http://api.test/boards"))
        with (
            patch("pages.api_client.httpx.request", return_value=response),
            self.assertRaises(httpx.HTTPStatusError),
        ):
            api_client.get_boards("token")
