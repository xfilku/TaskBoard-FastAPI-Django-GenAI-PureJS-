"""Demonstrate parameterized SQLite CRUD without changing data during import."""

import sqlite3
from contextlib import closing
from pathlib import Path

DEFAULT_DATABASE = Path(__file__).resolve().with_name("taskboard.db")


def main(database_path: Path = DEFAULT_DATABASE) -> None:
    """Create a sample board table, insert rows, update one and delete another.

    Args:
        database_path: SQLite file used only by this standalone learning example.
    """
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS boards (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        names = ["Projekty", "Finanse", "Dom"]
        ids = []
        for name in names:
            cursor = connection.execute("INSERT INTO boards (name) VALUES (?)", (name,))
            ids.append(cursor.lastrowid)
        connection.execute("UPDATE boards SET name = ? WHERE id = ?", ("Fitness", ids[1]))
        connection.execute("DELETE FROM boards WHERE id = ?", (ids[2],))
        print(connection.execute("SELECT id, name FROM boards ORDER BY id").fetchall())


if __name__ == "__main__":
    main()
