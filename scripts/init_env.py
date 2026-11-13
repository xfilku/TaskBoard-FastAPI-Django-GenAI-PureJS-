"""Create local development configuration without overwriting existing secrets."""

import secrets
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def initialize_env(destination: Path, example: Path) -> bool:
    """Create a .env file with two independent random keys if it does not exist.

    Args:
        destination: Local configuration file to create exclusively.
        example: Template containing empty TASKBOARD_JWT_SECRET and DJANGO_SECRET_KEY entries.

    Returns:
        True if a new file was written, or False if the destination already existed.
    """
    content = example.read_text(encoding="utf-8")
    for name in ("TASKBOARD_JWT_SECRET", "DJANGO_SECRET_KEY"):
        content = content.replace(f"{name}=\n", f"{name}={secrets.token_urlsafe(48)}\n", 1)
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as env_file:
            env_file.write(content)
    except FileExistsError:
        return False
    return True


def main() -> None:
    """Initialize the root .env file and report its status without printing secrets."""
    if initialize_env(PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.example"):
        print("Created .env with two independent local development secrets.")
    else:
        print("Existing .env preserved.")


if __name__ == "__main__":
    main()
