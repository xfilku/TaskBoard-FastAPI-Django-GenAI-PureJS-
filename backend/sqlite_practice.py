import sqlite3

conn = sqlite3.connect("taskboard.db")

cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
    );
""")

names = [
    ("Projekty",),
    ("Finanse",),
    ("Dom",)
]

cursor.executemany("""
    INSERT INTO boards (name)
    VALUES ?;        
    """,
    names)

conn.commit()

name = "Fitness"
board_id = 2
cursor.execute("""
    UPDATE boards 
    SET name = ? 
    WHERE id = ?;
    """, (name, board_id,)
    )

conn.commit()

board_id = 3
cursor.execute("""
    DELETE FROM boards 
    WHERE id = ?;
    """, ( board_id,)
    )

conn.commit()

cursor.execute("""SELECT * FROM boards""")
result = cursor.fetchall()
print(result)

conn.close()