"""Start development servers against disposable databases for browser tests."""

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    """Require an explicit test directory and launch the requested isolated service."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=("api", "frontend"))
    service = parser.parse_args().service
    work = Path(os.environ["TASKBOARD_E2E_DIR"]).resolve()
    if not work.is_dir():
        parser.error("TASKBOARD_E2E_DIR must identify an existing temporary directory.")
    project = Path(__file__).resolve().parent.parent
    if service == "api":
        sys.path.insert(0, str(project / "backend"))
        os.environ["TASKBOARD_DATABASE_URL"] = "sqlite:///" + (work / "api.db").as_posix()
        from create_tables import main as create_tables

        create_tables()
        import uvicorn

        uvicorn.run("main:app", host="127.0.0.1", port=18180, log_level="warning")
    else:
        sys.path.insert(0, str(project / "frontend"))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        from django.conf import settings

        settings.DATABASES["default"]["NAME"] = work / "django.sqlite3"
        settings.SECURE_SSL_REDIRECT = False
        settings.SESSION_COOKIE_SECURE = False
        settings.CSRF_COOKIE_SECURE = False
        import django

        django.setup()
        from django.core.management import call_command

        call_command("migrate", interactive=False, verbosity=0)
        call_command("runserver", "127.0.0.1:18100", use_reloader=False)


if __name__ == "__main__":
    main()
