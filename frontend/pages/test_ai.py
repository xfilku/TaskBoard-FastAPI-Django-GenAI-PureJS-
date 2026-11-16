"""Test planning forms, ownership feedback, review selection and batch-save failures."""

from datetime import date
from unittest.mock import patch

import httpx
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from pages import api_client
from pages.forms import PlanPreviewForm, TaskSuggestionsFormSet


def api_error(status):
    request = httpx.Request("POST", "http://api.test/ai/boards/1/plan-preview")
    return httpx.HTTPStatusError(
        "private upstream details",
        request=request,
        response=httpx.Response(status, request=request),
    )


def suggestion_data(titles=None, skipped=()):
    titles = titles if titles is not None else ["First suggested task", "Second suggested task"]
    data = {
        "form-TOTAL_FORMS": str(len(titles)),
        "form-INITIAL_FORMS": str(len(titles)),
        "goal": "Prepare a portfolio website",
        "min_elements": "1",
        "max_elements": "10",
        "plan_provider": "ollama",
    }
    for index, title in enumerate(titles):
        data[f"form-{index}-title"] = title
        if index in skipped:
            data[f"form-{index}-DELETE"] = "on"
    return data


class AIPlanningViewTests(TestCase):
    def setUp(self):
        session = self.client.session
        session["access_token"] = "test-token"
        session.save()
        self.board = {"id": 1, "name": "Portfolio board"}
        self.board_patch = patch("pages.views.get_board", return_value=self.board)
        self.board_api = self.board_patch.start()
        self.addCleanup(self.board_patch.stop)
        self.preview_url = reverse("plan_preview", args=[1])
        self.save_url = reverse("save_plan", args=[1])
        self.goal_data = {
            "goal": "Prepare a portfolio website",
            "min_elements": 1,
            "max_elements": 5,
        }

    def test_planner_requires_session_before_any_api_call(self):
        self.client.session.flush()
        for url in (self.preview_url, self.save_url):
            with (
                self.subTest(url=url),
                patch("pages.views.preview_plan") as generate,
                patch("pages.views.create_tasks_batch") as save,
            ):
                response = self.client.post(url, self.goal_data)
            self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
            generate.assert_not_called()
            save.assert_not_called()
        self.board_api.assert_not_called()

    def test_save_is_post_only_and_preview_rejects_put(self):
        self.assertEqual(self.client.get(self.save_url).status_code, 405)
        self.assertEqual(self.client.put(self.preview_url).status_code, 405)

    def test_csrf_protects_ai_generation_and_saving(self):
        client = Client(enforce_csrf_checks=True)
        for url in (self.preview_url, self.save_url):
            with self.subTest(url=url):
                self.assertEqual(client.post(url, {}).status_code, 403)
        self.board_api.assert_not_called()

    def test_get_renders_board_and_initial_empty_state(self):
        with patch("pages.views.preview_plan") as generate:
            response = self.client.get(self.preview_url)
        self.assertContains(response, "Portfolio board")
        self.assertContains(response, "Tu pojawi się Twój plan.")
        self.assertContains(response, "data-ai-generate")
        self.assertNotContains(response, "data-ai-review")
        generate.assert_not_called()

    def test_generation_shows_editable_proposals_without_saving(self):
        result = {
            "tasks": [{"title": "First generated task"}, {"title": "Second generated task"}],
            "provider": "ollama",
        }
        with (
            patch("pages.views.preview_plan", return_value=result) as generate,
            patch("pages.views.create_tasks_batch") as save,
        ):
            response = self.client.post(self.preview_url, self.goal_data)
        self.assertContains(response, "First generated task")
        self.assertContains(response, "data-ai-review")
        self.assertEqual(response.context["selected_count"], 2)
        self.assertContains(response, "Prepare a portfolio website")
        generate.assert_called_once_with(
            board_id=1,
            goal=self.goal_data["goal"],
            min_elements=1,
            max_elements=5,
            access_token="test-token",
        )
        save.assert_not_called()

    def test_demo_output_is_identified_honestly(self):
        with patch(
            "pages.views.preview_plan",
            return_value={"tasks": [{"title": "Demo suggested task"}], "provider": "demo"},
        ):
            response = self.client.post(self.preview_url, self.goal_data)
        self.assertContains(response, "Tryb demonstracyjny.")
        self.assertContains(response, "bez użycia modelu AI")

    def test_invalid_goal_or_range_does_not_trigger_generation(self):
        for changes in (
            {"goal": "   "},
            {"min_elements": 9, "max_elements": 3},
            {"max_elements": 51},
        ):
            with self.subTest(changes=changes), patch("pages.views.preview_plan") as generate:
                response = self.client.post(self.preview_url, self.goal_data | changes)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["plan_preview_form"].errors)
            generate.assert_not_called()

    def test_expired_generation_session_is_cleared(self):
        with patch("pages.views.preview_plan", side_effect=api_error(401)):
            response = self.client.post(self.preview_url, self.goal_data)
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("access_token", self.client.session)

    def test_generation_errors_keep_goal_and_range(self):
        for status in (403, 404, 502, 503, 504):
            with (
                self.subTest(status=status),
                patch("pages.views.preview_plan", side_effect=api_error(status)),
            ):
                response = self.client.post(self.preview_url, self.goal_data)
            self.assertContains(response, self.goal_data["goal"], status_code=status)
            self.assertEqual(
                str(response.context["plan_preview_form"]["max_elements"].value()), "5"
            )
            self.assertNotContains(response, "private upstream details", status_code=status)
            self.assertTrue(response.context["plan_preview_form"].non_field_errors())

    def test_transport_timeout_and_connection_failure_are_distinguished(self):
        for error, status in [
            (httpx.ReadTimeout("Timeout"), 504),
            (httpx.ConnectError("Offline"), 503),
        ]:
            with self.subTest(status=status), patch("pages.views.preview_plan", side_effect=error):
                response = self.client.post(self.preview_url, self.goal_data)
            self.assertEqual(response.status_code, status)
            self.assertTrue(response.context["plan_preview_form"].is_bound)

    def test_forbidden_or_missing_boards_never_generate(self):
        for status in (403, 404):
            self.board_api.side_effect = api_error(status)
            with self.subTest(status=status), patch("pages.views.preview_plan") as generate:
                response = self.client.post(self.preview_url, self.goal_data)
            self.assertEqual(response.status_code, status)
            self.assertTrue(response.context["error_message"])
            generate.assert_not_called()

    def test_generated_html_and_user_goal_are_escaped(self):
        title = '<script>alert("unsafe")</script>'
        with patch(
            "pages.views.preview_plan",
            return_value={"tasks": [{"title": title}], "provider": "ollama"},
        ):
            response = self.client.post(self.preview_url, self.goal_data | {"goal": title})
        self.assertNotContains(response, title)
        self.assertContains(response, "&lt;script&gt;")

    def test_only_reviewed_selected_tasks_are_saved_with_optional_deadlines(self):
        data = suggestion_data(
            ["  Edited first task  ", "Skipped second task", "Task without deadline"], skipped=(1,)
        )
        data["form-0-deadline"] = "2026-11-30"
        data["form-1-deadline"] = "2026-12-01"
        with patch("pages.views.create_tasks_batch", return_value=[{"id": 1}]) as save:
            response = self.client.post(self.save_url, data)
        self.assertRedirects(
            response, reverse("board_detail", args=[1]), fetch_redirect_response=False
        )
        save.assert_called_once_with(
            board_id=1,
            tasks=[
                {"title": "Edited first task", "deadline": date(2026, 11, 30)},
                {"title": "Task without deadline", "deadline": None},
            ],
            access_token="test-token",
        )

    def test_all_skipped_or_empty_selection_never_saves(self):
        for data in (suggestion_data(skipped=(0, 1)), suggestion_data([])):
            with self.subTest(data=data), patch("pages.views.create_tasks_batch") as save:
                response = self.client.post(self.save_url, data)
            self.assertContains(response, "Pozostaw co najmniej jedno zadanie")
            save.assert_not_called()

    def test_invalid_edited_titles_are_preserved_and_not_saved(self):
        with patch("pages.views.create_tasks_batch") as save:
            response = self.client.post(
                self.save_url, suggestion_data(["tiny", "Valid second task"])
            )
        self.assertContains(response, "tiny")
        self.assertTrue(response.context["task_suggestion_formset"].errors)
        save.assert_not_called()

    def test_duplicate_edits_are_rejected_locally(self):
        with patch("pages.views.create_tasks_batch") as save:
            response = self.client.post(
                self.save_url, suggestion_data(["Repeated task", "  REPEATED TASK  "])
            )
        self.assertTrue(response.context["task_suggestion_formset"].non_form_errors())
        save.assert_not_called()

    def test_missing_management_data_is_visible_and_never_saves(self):
        with patch("pages.views.create_tasks_batch") as save:
            response = self.client.post(self.save_url, {"goal": "Goal for this board"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["task_suggestion_formset"].non_form_errors())
        self.assertContains(response, 'role="alert"')
        save.assert_not_called()

    def test_forged_form_count_is_bounded_before_rendering(self):
        data = suggestion_data()
        data["form-TOTAL_FORMS"] = "100000"
        with patch("pages.views.create_tasks_batch") as save:
            response = self.client.post(self.save_url, data)
        self.assertLessEqual(len(response.context["task_suggestion_formset"].forms), 50)
        self.assertTrue(response.context["task_suggestion_formset"].non_form_errors())
        save.assert_not_called()

    def test_failed_save_retains_edits_selection_and_original_goal(self):
        with patch("pages.views.create_tasks_batch", side_effect=httpx.ConnectError("Offline")):
            response = self.client.post(self.save_url, suggestion_data(skipped=(1,)))
        self.assertContains(response, "First suggested task", status_code=503)
        self.assertContains(response, "Prepare a portfolio website", status_code=503)
        self.assertEqual(response.context["selected_count"], 1)
        self.assertTrue(response.context["task_suggestion_formset"][1]["DELETE"].value())
        self.assertContains(response, "Sprawdź tablicę przed kolejną próbą", status_code=503)

    def test_expired_save_session_is_cleared(self):
        with patch("pages.views.create_tasks_batch", side_effect=api_error(401)):
            response = self.client.post(self.save_url, suggestion_data())
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("access_token", self.client.session)

    def test_failed_board_lookup_preserves_the_review_after_save(self):
        self.board_api.side_effect = httpx.ConnectError("Offline")
        with patch("pages.views.create_tasks_batch") as save:
            response = self.client.post(self.save_url, suggestion_data())
        self.assertContains(response, "First suggested task", status_code=503)
        save.assert_not_called()


class AIFormTests(SimpleTestCase):
    def test_goal_and_title_limits_match_the_api(self):
        self.assertTrue(
            PlanPreviewForm({"goal": "x" * 1000, "min_elements": 1, "max_elements": 50}).is_valid()
        )
        self.assertFalse(
            PlanPreviewForm({"goal": "x" * 1001, "min_elements": 1, "max_elements": 50}).is_valid()
        )
        self.assertFalse(TaskSuggestionsFormSet(suggestion_data(["x" * 301])).is_valid())

    def test_deleted_invalid_title_does_not_block_valid_selected_task(self):
        formset = TaskSuggestionsFormSet(
            suggestion_data(["Valid selected title", "x"], skipped=(1,))
        )
        self.assertTrue(formset.is_valid())

    def test_formset_rejects_more_than_fifty_tasks(self):
        formset = TaskSuggestionsFormSet(
            suggestion_data([f"Valid task number {index}" for index in range(51)])
        )
        self.assertFalse(formset.is_valid())
        self.assertLessEqual(len(formset.forms), 50)


class AIClientTests(SimpleTestCase):
    def test_preview_uses_inference_timeout_and_correct_payload(self):
        response = httpx.Response(
            200, request=httpx.Request("POST", "http://api.test/plan"), json={"tasks": []}
        )
        with (
            patch.dict("os.environ", {"TASKBOARD_AI_TIMEOUT": "120"}),
            patch("pages.api_client.httpx.request", return_value=response) as request,
        ):
            api_client.preview_plan(7, "Portfolio goal", 2, 6, "token")
        self.assertEqual(request.call_args.kwargs["timeout"], 135)
        self.assertEqual(
            request.call_args.kwargs["json"],
            {"goal": "Portfolio goal", "min_elements": 2, "max_elements": 6},
        )
        self.assertIn("ai/boards/7/plan-preview", request.call_args.args[1])

    def test_bad_timeout_configuration_does_not_crash_the_frontend(self):
        for value in ("invalid", "nan", "inf"):
            with (
                self.subTest(value=value),
                patch.dict("os.environ", {"TASKBOARD_AI_TIMEOUT": value}),
            ):
                self.assertEqual(api_client._planning_timeout(), 75)

    def test_batch_uses_regular_timeout_and_selected_task_payload(self):
        response = httpx.Response(
            201, request=httpx.Request("POST", "http://api.test/batch"), json=[{"id": 3}]
        )
        with patch("pages.api_client.httpx.request", return_value=response) as request:
            result = api_client.create_tasks_batch(
                7, [{"title": "Chosen task title", "deadline": date(2026, 11, 30)}], "token"
            )
        self.assertEqual(result, [{"id": 3}])
        self.assertEqual(request.call_args.kwargs["timeout"], 5)
        self.assertEqual(
            request.call_args.kwargs["json"],
            {"tasks": [{"title": "Chosen task title", "deadline": "2026-11-30"}]},
        )
