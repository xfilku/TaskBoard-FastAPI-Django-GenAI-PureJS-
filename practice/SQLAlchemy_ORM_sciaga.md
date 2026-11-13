# SQLAlchemy ORM 2.x — ściąga CRUD (SQLite)

> **Cel:** szybkie przypomnienie, jak stworzyć model i tabelę oraz wykonać **INSERT, SELECT, UPDATE i DELETE** przez ORM, bez ręcznego pisania SQL.
>
> Przykłady używają składni SQLAlchemy **2.x** i bazy SQLite.

## 1. Kompletny przykład — kod do uruchomienia

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session


# Bazowa klasa dla modeli ORM
class Base(DeclarativeBase):
    pass


# Model Pythonowy odwzorowujący tabelę "notes"
class Note(Base):
    __tablename__ = "notes"  # nazwa tabeli w bazie

    id: Mapped[int] = mapped_column(primary_key=True)  # klucz główny
    title: Mapped[str] = mapped_column(nullable=False)  # pole wymagane (NOT NULL)


# Silnik połączenia z lokalnym plikiem SQLite
engine = create_engine("sqlite:///orm_practice.db", echo=True)

# Utwórz brakujące tabele na podstawie modeli
Base.metadata.create_all(engine)


# Sesja zarządza obiektami ORM i transakcjami
with Session(engine) as session:
    # ---------- INSERT ----------
    new_note = Note(title="Moja pierwsza notatka")  # obiekt Pythona
    session.add(new_note)  # dodanie do sesji
    session.commit()  # zatwierdzenie INSERT
    session.refresh(new_note)  # odczyt stanu z bazy

    print(f"Dodano: ID={new_note.id}, TITLE={new_note.title}")

    # ---------- SELECT (wszystkie rekordy) ----------
    statement = select(Note)  # budowanie zapytania SELECT
    notes = session.scalars(statement).all()  # wykonanie i pobranie obiektów Note

    for note in notes:
        print(f"ID={note.id}, TITLE={note.title}")

    # ---------- SELECT (jeden rekord po PK) ----------
    note_id = new_note.id  # ID rekordu dodanego powyżej
    found_note = session.get(Note, note_id)

    if found_note is None:
        print(f"Nie znaleziono notatki o ID={note_id}")
    else:
        print(f"Znaleziono: {found_note.title}")

    # ---------- UPDATE ----------
    note_to_update = session.get(Note, note_id)
    if note_to_update is None:
        print(f"Nie znaleziono notatki o ID={note_id}")
    else:
        note_to_update.title = "SQLAlchemy jest super"  # zmiana atrybutu
        session.commit()  # zapis UPDATE
        session.refresh(note_to_update)  # opcjonalne odświeżenie
        print(f"Zmieniono: {note_to_update.title}")

    # ---------- DELETE ----------
    note_to_delete = session.get(Note, note_id)
    if note_to_delete is None:
        print(f"Nie znaleziono notatki o ID={note_id}")
    else:
        session.delete(note_to_delete)  # oznaczenie do usunięcia
        session.commit()  # zatwierdzenie DELETE
        print(f"Usunięto notatkę ID={note_id}")

    # ---------- SPRAWDZENIE DELETE ----------
    check_note = session.get(Note, note_id)
    if check_note is None:
        print(f"Potwierdzono: brak notatki ID={note_id}")
```

**Uwaga:** ten przykład tworzy i usuwa *ten sam* nowy rekord. W Twojej pierwotnej wersji `session.get(Note, 1)` zawsze dotyczyło ID `1`, a nowo dodany rekord może mieć inne ID. Dlatego tutaj używamy `new_note.id`.

---

## 2. Wyjaśnienie — od konfiguracji do tabeli

| Fragment | Co robi? |
|---|---|
| `create_engine("sqlite:///orm_practice.db")` | Konfiguruje silnik SQLAlchemy dla pliku `orm_practice.db`. |
| `echo=True` | Wypisuje w konsoli wykonywane zapytania SQL (przydatne do nauki/debugowania). |
| `class Base(DeclarativeBase)` | Tworzy bazę, po której dziedziczą modele ORM. |
| `class Note(Base)` | Definiuje mapowanie między klasą `Note` a tabelą bazy danych. |
| `__tablename__ = "notes"` | Ustala nazwę tabeli. |
| `Mapped[int]`, `Mapped[str]` | Typowane deklaracje mapowanych pól ORM. |
| `mapped_column(primary_key=True)` | Oznacza kolumnę jako klucz główny. W tym przypadku SQLite może generować jej wartości automatycznie. |
| `mapped_column(nullable=False)` | Zabrania `NULL` w tej kolumnie. Nie zabrania pustego tekstu `""`. |
| `Base.metadata.create_all(engine)` | Tworzy **brakujące** tabele; nie aktualizuje automatycznie struktury już istniejącej tabeli. |
| `with Session(engine) as session:` | Otwiera sesję i zamyka ją po wyjściu z bloku. Samo wyjście **nie zastępuje** `commit()`. |

### Ważne: model ORM a rekord

```python
class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)


note = Note(title="Zakupy")  # na tym etapie tylko obiekt w Pythonie
```

- `Note` to **klasa** opisująca tabelę.
- `note` to **obiekt** reprezentujący jeden rekord.
- `note.title` to dostęp do wartości kolumny przez atrybut obiektu.
- Samo `Note(...)` **nie wykonuje INSERT**.

---

## 3. INSERT — dodawanie rekordu

```python
new_note = Note(title="Notatka testowa")
session.add(new_note)
session.commit()
session.refresh(new_note)
print(new_note.id)
```

1. `Note(...)` — tworzy nowy obiekt.
2. `session.add(...)` — umieszcza obiekt w sesji jako oczekujący na zapis.
3. `session.commit()` — zatwierdza transakcję; SQLAlchemy wcześniej wysyła wymagany `INSERT` do bazy.
4. `session.refresh(...)` — ponownie pobiera stan obiektu z bazy. **Nie jest zawsze konieczne** do uzyskania `id`.

Przybliżony SQL:

```sql
INSERT INTO notes (title) VALUES ('Notatka testowa');
```

## 4. SELECT — pobieranie danych

### Wszystkie notatki

```python
statement = select(Note)
notes = session.scalars(statement).all()

for note in notes:
    print(note.id, note.title)
```

- `select(Note)` — konstruuje zapytanie; **jeszcze go nie wykonuje**.
- `session.scalars(statement)` — wykonuje zapytanie i udostępnia wyniki jako obiekty `Note`, nie wiersze opakowujące obiekt.
- `.all()` — pobiera wszystkie wyniki do listy.

Przybliżony SQL:

```sql
SELECT notes.id, notes.title FROM notes;
```

### Jeden rekord po kluczu głównym

```python
note = session.get(Note, 1)
if note is None:
    print("Brak rekordu")
else:
    print(note.title)
```

`session.get(Note, 1)` wyszukuje po **kluczu głównym** i zwraca obiekt albo `None` (może korzystać z pamięci podręcznej sesji).

### Filtrowanie po innym polu

```python
statement = select(Note).where(Note.title == "Zakupy")
notes = session.scalars(statement).all()
```

### Tylko pierwszy pasujący wynik (lub `None`)

```python
statement = select(Note).where(Note.title == "Zakupy")
note = session.scalars(statement).first()
```

> `first()` zwraca pierwszy obiekt lub `None`. Jeśli potrzebujesz gwarancji unikalności wyniku, zapoznaj się z `one_or_none()`.

---

## 5. UPDATE — zmiana rekordu

```python
note = session.get(Note, 1)

if note is not None:
    note.title = "Nowy tytuł"
    session.commit()
    session.refresh(note)  # opcjonalne
```

1. Pobierasz istniejący obiekt ORM.
2. Zmieniasz jego atrybut: `note.title = ...`.
3. SQLAlchemy śledzi zmianę obiektu.
4. `session.commit()` zatwierdza zmianę (w razie potrzeby wykonuje `UPDATE`).

Przybliżony SQL:

```sql
UPDATE notes SET title = 'Nowy tytuł' WHERE id = 1;
```

## 6. DELETE — usuwanie rekordu

```python
note = session.get(Note, 1)

if note is not None:
    session.delete(note)
    session.commit()
```

- `session.delete(note)` — oznacza obiekt do usunięcia.
- `session.commit()` — powoduje wykonanie i zatwierdzenie usunięcia.

Przybliżony SQL:

```sql
DELETE FROM notes WHERE id = 1;
```

Sprawdzenie:

```python
if session.get(Note, 1) is None:
    print("Rekord nie istnieje")
```

---

## 7. Ściąga metod — jedno spojrzenie

| Zadanie | SQLAlchemy ORM 2.x |
|---|---|
| Dodaj obiekt do sesji | `session.add(note)` |
| Zapisz / zatwierdź zmiany | `session.commit()` |
| Odśwież obiekt z bazy | `session.refresh(note)` |
| Pobierz po kluczu głównym | `session.get(Note, 1)` |
| Zbuduj SELECT | `select(Note)` |
| Pobierz wszystkie obiekty | `session.scalars(select(Note)).all()` |
| Pobierz pierwszy lub `None` | `session.scalars(select(Note)).first()` |
| Filtruj po tytule | `select(Note).where(Note.title == "X")` |
| Zmień wartość | `note.title = "Nowy"` + `session.commit()` |
| Usuń obiekt | `session.delete(note)` + `session.commit()` |
| Wycofaj niezapisane zmiany transakcji | `session.rollback()` |
| Zakończ sesję | `session.close()` albo `with Session(...)` |

## 8. Najczęstsze pułapki

1. **`session.add()` to jeszcze nie trwały zapis.** Zmiany mogą zostać wysłane do bazy przed `commit()`, ale dopiero zatwierdzenie transakcji utrwala je.
2. **`session.refresh()` ≠ `session.commit()`.** `refresh()` odczytuje aktualny stan z bazy, nie zapisuje zmian.
3. **`select(Note)` tylko tworzy zapytanie.** Do wykonania użyj np. `session.scalars(...)` lub `session.execute(...)`.
4. **`session.get(Note, 1)` działa według klucza głównego, nie dowolnej kolumny.**
5. **Nie zakładaj, że nowa notatka zawsze ma ID 1.** Używaj `new_note.id`.
6. **`create_all()` nie migruje istniejących tabel.** Do zmian schematu w większych projektach używa się migracji, np. Alembic.
7. **Przy błędzie zapisu może być potrzebne `session.rollback()`.** Szczególnie jeśli chcesz dalej używać tej samej sesji po nieudanej transakcji.
8. **`echo=True` tylko do nauki/debugowania.** Logi SQL mogą ujawniać wartości parametrów; w produkcji zwykle jest wyłączone.
9. **SQLite to plik.** `sqlite:///orm_practice.db` używa ścieżki względnej wobec katalogu roboczego uruchamianego procesu.

## 9. Mini-schemat do zapamiętania

```text
Model Note (klasa Pythona)  ───►  Tabela notes (SQLite)

INSERT:  Note(...) ─► add() ─► commit() ─► refresh() [opcjonalnie]
SELECT:  select(Note) ─► session.scalars(...) ─► all()/first()
GET PK:  session.get(Note, id) ─► Note lub None
UPDATE:  get() ─► zmiana atrybutu ─► commit()
DELETE:  get() ─► delete() ─► commit()
```

**Najważniejsze:** model opisuje tabelę, obiekt opisuje rekord, a sesja zarządza ich odczytem i zapisem w transakcjach.
