"""Register the server-rendered TaskBoard interface with Django."""

from django.apps import AppConfig


class PagesConfig(AppConfig):
    """Configure the pages application and its default primary-key type."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "pages"
