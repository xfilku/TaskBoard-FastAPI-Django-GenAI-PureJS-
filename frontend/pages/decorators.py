"""Protect views that use an API token stored in the Django session."""

from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache


def session_required(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """Redirect anonymous visitors before a view can contact the API.

    Django's admin authentication is independent of the API account. This
    decorator checks the API session and prevents caching of private pages;
    the API remains responsible for validating the token and ownership.
    """

    @never_cache
    @wraps(view)
    def wrapped(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        """Run the protected view only when an API session token is present."""
        if not request.session.get("access_token"):
            return redirect("login")
        return view(request, *args, **kwargs)

    return wrapped
