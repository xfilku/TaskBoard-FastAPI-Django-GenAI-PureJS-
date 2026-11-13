"""Render the TaskBoard interface and translate API failures into useful feedback."""

import os

import httpx
from django.contrib import messages
from django.forms import BaseFormSet
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from pages.api_client import (
    create_board,
    create_task,
    create_tasks_batch,
    delete_board,
    delete_task,
    get_board,
    get_board_tasks,
    get_boards,
    get_task,
    login_user,
    patch_task,
    preview_plan,
    register_user,
)
from pages.decorators import session_required
from pages.forms import (
    BoardCreateForm,
    CreateTaskForm,
    LoginForm,
    PlanPreviewForm,
    RegisterForm,
    TaskSuggestionsFormSet,
)

CONNECTION_ERROR = "Nie udało się połączyć z serwerem. Spróbuj ponownie później."
SERVER_ERROR = "Nie udało się wykonać operacji. Spróbuj ponownie później."


def _expired_session(request: HttpRequest) -> HttpResponseRedirect:
    """Remove an expired API token and return the visitor to the login form."""
    request.session.flush()
    messages.info(request, "Sesja wygasła. Zaloguj się ponownie.")
    return redirect("login")


def _resource_message(status_code: int, resource: str) -> str:
    """Translate API ownership and missing-resource errors into Polish copy."""
    if status_code == 403:
        return f"Nie masz dostępu do {resource}."
    if status_code == 404:
        return "Nie znaleziono tablicy lub zadania."
    if status_code == 409:
        return "Najpierw usuń zadania przypisane do tej tablicy."
    return SERVER_ERROR


def _mutation_error(
    request: HttpRequest, exc: httpx.HTTPStatusError, resource: str
) -> HttpResponseRedirect | None:
    """Expire invalid sessions or queue feedback after a failed write."""
    if exc.response.status_code == 401:
        return _expired_session(request)
    messages.error(request, _resource_message(exc.response.status_code, resource))
    return None


@require_GET
@session_required
def home(request: HttpRequest) -> HttpResponse:
    """Display the current account's boards, including an API outage message."""
    boards = []
    error_message = None
    status = 200
    try:
        boards = get_boards(request.session["access_token"])
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return _expired_session(request)
        error_message = "Nie udało się pobrać tablic. Spróbuj ponownie później."
        status = 502
    except httpx.RequestError:
        error_message = CONNECTION_ERROR
        status = 503
    return render(
        request,
        "pages/home.html",
        {"boards": boards, "error_message": error_message},
        status=status,
    )


@require_http_methods(["GET", "POST"])
@never_cache
@sensitive_post_parameters("password")
def login_page(request: HttpRequest) -> HttpResponse:
    """Validate credentials and rotate the Django session after a successful login."""
    form = LoginForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            token_data = login_user(form.cleaned_data["email"], form.cleaned_data["password"])
        except httpx.HTTPStatusError as exc:
            message = (
                "Wprowadzono niepoprawny e-mail lub hasło."
                if exc.response.status_code in {401, 422}
                else SERVER_ERROR
            )
            form.add_error(None, message)
        except httpx.RequestError:
            form.add_error(None, CONNECTION_ERROR)
        else:
            request.session.cycle_key()
            request.session["access_token"] = token_data["access_token"]
            return redirect("home")
    return render(request, "pages/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
@never_cache
@sensitive_post_parameters("password")
def register_page(request: HttpRequest) -> HttpResponse:
    """Create an API account while keeping validation errors attached to the form."""
    form = RegisterForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            register_user(form.cleaned_data["email"], form.cleaned_data["password"])
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 409:
                form.add_error("email", "Konto z tym adresem e-mail już istnieje. Zaloguj się.")
            elif status == 422:
                form.add_error(
                    None, "Sprawdź e-mail i hasło. Hasło musi mieć co najmniej 5 znaków."
                )
            else:
                form.add_error(None, SERVER_ERROR)
        except httpx.RequestError:
            form.add_error(None, CONNECTION_ERROR)
        else:
            messages.success(request, "Konto zostało utworzone. Możesz się zalogować.")
            return redirect("login")
    return render(request, "pages/register.html", {"form": form})


@require_POST
def logout_user(request: HttpRequest) -> HttpResponse:
    """Clear the server-side session after a CSRF-protected POST."""
    request.session.flush()
    return redirect("login")


@require_http_methods(["GET", "POST"])
@session_required
def create_board_page(request: HttpRequest) -> HttpResponse:
    """Create a board or redisplay the bound form when the API rejects it."""
    form = BoardCreateForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            create_board(form.cleaned_data["name"], request.session["access_token"])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return _expired_session(request)
            form.add_error(None, SERVER_ERROR)
        except httpx.RequestError:
            form.add_error(None, CONNECTION_ERROR)
        else:
            return redirect("home")
    return render(request, "pages/board_create.html", {"form": form})


@require_http_methods(["GET", "POST"])
@session_required
def board_detail_page(request: HttpRequest, board_id: int) -> HttpResponse:
    """Show a board and its tasks, and handle creation of a task on that board."""
    token = request.session["access_token"]
    form = CreateTaskForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            create_task(board_id, form.cleaned_data["title"], token)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return _expired_session(request)
            form.add_error(None, _resource_message(exc.response.status_code, "tej tablicy"))
        except httpx.RequestError:
            form.add_error(None, CONNECTION_ERROR)
        else:
            return redirect("board_detail", board_id=board_id)

    board = None
    tasks = []
    error_message = None
    status = 200
    try:
        board = get_board(board_id, token)
        tasks = get_board_tasks(board_id, token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return _expired_session(request)
        error_message = _resource_message(exc.response.status_code, "tej tablicy")
        status = exc.response.status_code if exc.response.status_code in {403, 404} else 502
    except httpx.RequestError:
        error_message = CONNECTION_ERROR
        status = 503
    return render(
        request,
        "pages/board_detail.html",
        {"board": board, "tasks": tasks, "task_form": form, "error_message": error_message},
        status=status,
    )


@require_POST
@session_required
def update_task(request: HttpRequest, board_id: int, task_id: int) -> HttpResponse:
    """Toggle task completion, accepting only explicit true or false form values."""
    raw_is_done = request.POST.get("is_done")
    if raw_is_done not in {"true", "false"}:
        return HttpResponseBadRequest("Wybierz prawidłowy status zadania.")
    try:
        patch_task(
            board_id, task_id, {"is_done": raw_is_done == "true"}, request.session["access_token"]
        )
    except httpx.HTTPStatusError as exc:
        response = _mutation_error(request, exc, "tego zadania")
        if response is not None:
            return response
    except httpx.RequestError:
        messages.error(request, CONNECTION_ERROR)
    return redirect("board_detail", board_id=board_id)


@require_POST
@session_required
def delete_board_page(request: HttpRequest, board_id: int) -> HttpResponse:
    """Delete an empty board and handle API outages without returning a server error."""
    try:
        delete_board(board_id=board_id, access_token=request.session["access_token"])
    except httpx.HTTPStatusError as exc:
        response = _mutation_error(request, exc, "tej tablicy")
        if response is not None:
            return response
        if exc.response.status_code == 404:
            return redirect("home")
    except httpx.RequestError:
        messages.error(request, CONNECTION_ERROR)
    else:
        messages.success(request, "Tablica została usunięta.")
        return redirect("home")
    return redirect("board_detail", board_id=board_id)


@require_POST
@session_required
def delete_task_page(request: HttpRequest, board_id: int, task_id: int) -> HttpResponse:
    """Delete one task after checking the session and surface recoverable API errors."""
    try:
        delete_task(
            board_id=board_id, task_id=task_id, access_token=request.session["access_token"]
        )
    except httpx.HTTPStatusError as exc:
        response = _mutation_error(request, exc, "tego zadania")
        if response is not None:
            return response
    except httpx.RequestError:
        messages.error(request, CONNECTION_ERROR)
    return redirect("board_detail", board_id=board_id)


@require_http_methods(["GET", "POST"])
@session_required
def edit_task_page(request: HttpRequest, board_id: int, task_id: int) -> HttpResponse:
    """Edit a task title while preserving submitted text after a recoverable API failure."""
    token = request.session["access_token"]
    status = 200
    if request.method == "POST":
        form = CreateTaskForm(request.POST)
        if form.is_valid():
            try:
                patch_task(board_id, task_id, {"title": form.cleaned_data["title"]}, token)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    return _expired_session(request)
                status = exc.response.status_code if exc.response.status_code in {403, 404} else 502
                form.add_error(None, _resource_message(exc.response.status_code, "tego zadania"))
            except httpx.RequestError:
                status = 503
                form.add_error(None, CONNECTION_ERROR)
            else:
                return redirect("board_detail", board_id=board_id)
    else:
        try:
            task = get_task(board_id=board_id, task_id=task_id, access_token=token)
        except httpx.HTTPStatusError as exc:
            response = _mutation_error(request, exc, "tego zadania")
            if response is not None:
                return response
            return redirect("board_detail", board_id=board_id)
        except httpx.RequestError:
            messages.error(request, CONNECTION_ERROR)
            return redirect("board_detail", board_id=board_id)
        form = CreateTaskForm(initial={"title": task["title"]})
    return render(request, "pages/edit_task.html", {"edit_task_form": form}, status=status)


def _plan_error_message(status_code: int) -> str:
    """Translate AI and ownership failures without exposing upstream response content."""
    if status_code in {403, 404}:
        return _resource_message(status_code, "tej tablicy")
    if status_code == 504:
        return "AI potrzebuje więcej czasu. Spróbuj ponownie lub poproś o mniej zadań."
    if status_code == 503:
        return "AI jest teraz niedostępne. Spróbuj ponownie za chwilę."
    if status_code == 422:
        return "Sprawdź cel, zakres planu i treść wybranych zadań."
    return "AI nie zwróciło poprawnego planu. Spróbuj wygenerować go ponownie."


def _render_plan_page(
    request: HttpRequest,
    board_id: int,
    board: dict | None,
    plan_form: PlanPreviewForm,
    suggestions: BaseFormSet,
    *,
    provider: str = "",
    save_error: str | None = None,
    error_message: str | None = None,
    status: int = 200,
) -> HttpResponse:
    """Share planner context while retaining bound forms after generation or save errors."""
    selected_count = sum(not form["DELETE"].value() for form in suggestions.forms)
    return render(
        request,
        "pages/plan_preview.html",
        {
            "board": board,
            "board_id": board_id,
            "plan_preview_form": plan_form,
            "task_suggestion_formset": suggestions,
            "selected_count": selected_count,
            "provider": provider or os.getenv("TASKBOARD_AI_PROVIDER", "demo").strip().lower(),
            "save_error": save_error,
            "error_message": error_message,
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
@session_required
def plan_preview_page(request: HttpRequest, board_id: int) -> HttpResponse:
    """Generate editable task proposals for an owned board without writing any tasks."""
    token = request.session["access_token"]
    form = PlanPreviewForm(request.POST if request.method == "POST" else None)
    suggestions = TaskSuggestionsFormSet()
    board = None
    try:
        board = get_board(board_id, token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return _expired_session(request)
        status = exc.response.status_code if exc.response.status_code in {403, 404} else 502
        return _render_plan_page(
            request,
            board_id,
            board,
            form,
            suggestions,
            error_message=_plan_error_message(exc.response.status_code),
            status=status,
        )
    except httpx.RequestError:
        return _render_plan_page(
            request,
            board_id,
            board,
            form,
            suggestions,
            error_message=CONNECTION_ERROR,
            status=503,
        )

    status = 200
    provider = ""
    if request.method == "POST" and form.is_valid():
        try:
            result = preview_plan(
                board_id=board_id,
                goal=form.cleaned_data["goal"],
                min_elements=form.cleaned_data["min_elements"],
                max_elements=form.cleaned_data["max_elements"],
                access_token=token,
            )
            suggestions = TaskSuggestionsFormSet(initial=result["tasks"])
            provider = result.get("provider", "")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return _expired_session(request)
            status = (
                exc.response.status_code
                if exc.response.status_code in {403, 404, 503, 504}
                else 502
            )
            form.add_error(None, _plan_error_message(exc.response.status_code))
        except httpx.TimeoutException:
            status = 504
            form.add_error(None, _plan_error_message(504))
        except httpx.RequestError:
            status = 503
            form.add_error(None, _plan_error_message(503))
    return _render_plan_page(
        request, board_id, board, form, suggestions, provider=provider, status=status
    )


@require_POST
@session_required
def save_plan_page(request: HttpRequest, board_id: int) -> HttpResponse:
    """Validate edited suggestions and save only included titles in one atomic API request."""
    token = request.session["access_token"]
    plan_form = PlanPreviewForm(request.POST)
    suggestions = TaskSuggestionsFormSet(request.POST)
    provider = request.POST.get("plan_provider", "")
    if provider not in {"demo", "ollama"}:
        provider = ""
    board = None
    try:
        board = get_board(board_id, token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return _expired_session(request)
        status = exc.response.status_code if exc.response.status_code in {403, 404} else 502
        return _render_plan_page(
            request,
            board_id,
            board,
            plan_form,
            suggestions,
            error_message=_plan_error_message(exc.response.status_code),
            status=status,
        )
    except httpx.RequestError:
        return _render_plan_page(
            request,
            board_id,
            board,
            plan_form,
            suggestions,
            save_error=CONNECTION_ERROR,
            provider=provider,
            status=503,
        )

    save_error = None
    status = 200
    if suggestions.is_valid():
        tasks = [
            {"title": row["title"]}
            for row in suggestions.cleaned_data
            if row and not row.get("DELETE")
        ]
        try:
            create_tasks_batch(board_id=board_id, tasks=tasks, access_token=token)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return _expired_session(request)
            status = (
                exc.response.status_code
                if exc.response.status_code in {403, 404, 503, 504}
                else 502
            )
            save_error = _resource_message(exc.response.status_code, "tej tablicy")
        except httpx.TimeoutException:
            status = 504
            save_error = (
                "Nie otrzymaliśmy potwierdzenia zapisu. Sprawdź tablicę przed kolejną próbą."
            )
        except httpx.RequestError:
            status = 503
            save_error = (
                "Nie otrzymaliśmy potwierdzenia zapisu. Sprawdź tablicę przed kolejną próbą."
            )
        else:
            messages.success(request, f"Dodano zadania do tablicy: {len(tasks)}.")
            return redirect("board_detail", board_id=board_id)
    return _render_plan_page(
        request,
        board_id,
        board,
        plan_form,
        suggestions,
        provider=provider,
        save_error=save_error,
        status=status,
    )
