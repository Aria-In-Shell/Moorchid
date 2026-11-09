"""SQLite persistence layer for the Moorchid journal application."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Sequence, TypedDict, cast

from passlib.context import CryptContext

from config import get_config
from memory_schema import (
    MemoryRecord,
    canonicalize_emotion,
    intensity_for_emotion,
    valence_for_emotion,
)

# ── Constants ────────────────────────────────────────────────────────────────────

_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_MIN_PASSWORD_LENGTH = 6

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _validate_user_id(user_id: str) -> str:
    if not isinstance(user_id, str) or not _USER_ID_PATTERN.match(user_id):
        raise ValueError("user_id must match ^[A-Za-z0-9_-]{1,64}$")
    return user_id


def _validate_username(username: str) -> str:
    if not isinstance(username, str) or not _USERNAME_PATTERN.match(username):
        raise ValueError("username must match ^[A-Za-z0-9_-]{3,32}$")
    return username


def _resolve_database_path() -> Path:
    config = get_config()
    path = config.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


DB_PATH: Path = _resolve_database_path()
DEFAULT_ENTRY_LIMIT = 50
MAX_ENTRY_LIMIT = 1_000


class JournalEntry(TypedDict):
    """A journal entry returned by :func:`get_user_entries`."""

    id: int
    user_id: str
    content: str
    emotion: str
    tags: list[str]
    created_at: str
    valence: float
    intensity: float
    analysis_json: str | None


class PoetryReport(TypedDict):
    """A poetry report returned by :func:`get_latest_poetry_report`."""

    id: int
    user_id: str
    title: str
    poetry_content: str
    emotion_distribution: str
    blessing: str
    created_at: str


class ChatMessageRecord(TypedDict):
    """A chat message returned by :func:`get_user_chat_history`."""

    id: int
    user_id: str
    role: str
    content: str
    created_at: str


class SoulJournalDatabaseError(RuntimeError):
    """Raised when a Moorchid database operation fails."""


@contextmanager
def _get_connection() -> Iterator[sqlite3.Connection]:
    """Open a configured connection with WAL mode and busy timeout."""
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(DB_PATH, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA busy_timeout=5000;")
        connection.execute("PRAGMA foreign_keys=ON;")
        yield connection
    finally:
        if connection is not None:
            connection.close()


def _require_non_empty(value: str, field_name: str) -> str:
    """Validate a required text value without altering its contents."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _serialize_tags(tags: Sequence[str]) -> str:
    """Validate tags and serialize them as a JSON array."""
    if isinstance(tags, (str, bytes)) or not isinstance(tags, Sequence):
        raise TypeError("tags must be a sequence of strings")

    normalized_tags = list(tags)
    if any(not isinstance(tag, str) for tag in normalized_tags):
        raise TypeError("every tag must be a string")

    try:
        return json.dumps(normalized_tags, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("tags could not be serialized as JSON") from exc


def _deserialize_json_list(raw: str | None, field_name: str, record_id: str) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SoulJournalDatabaseError(
            f"{field_name} on {record_id} contains invalid JSON"
        ) from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise SoulJournalDatabaseError(
            f"{field_name} on {record_id} must be a JSON array of strings"
        )
    return cast(list[str], parsed)


def _entry_from_row(row: sqlite3.Row) -> JournalEntry:
    emotion = row["emotion"]
    valence_raw = row["valence"] if "valence" in row.keys() else None
    intensity_raw = row["intensity"] if "intensity" in row.keys() else None
    analysis_json = None
    if "analysis_json" in row.keys() and row["analysis_json"]:
        analysis_json = str(row["analysis_json"])
    return JournalEntry(
        id=row["id"],
        user_id=row["user_id"],
        content=row["content"],
        emotion=emotion,
        tags=_deserialize_tags(row["tags"], row["id"]),
        created_at=str(row["created_at"]),
        valence=valence_for_emotion(emotion, valence_raw),
        intensity=intensity_for_emotion(intensity_raw),
        analysis_json=analysis_json,
    )


def _deserialize_tags(raw_tags: str | None, entry_id: int) -> list[str]:
    """Parse and validate a stored JSON tag array."""
    if raw_tags is None:
        return []

    try:
        parsed = json.loads(raw_tags)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SoulJournalDatabaseError(
            f"journal entry {entry_id} contains invalid tag JSON"
        ) from exc

    if not isinstance(parsed, list) or any(not isinstance(tag, str) for tag in parsed):
        raise SoulJournalDatabaseError(
            f"journal entry {entry_id} tags must be a JSON array of strings"
        )
    return cast(list[str], parsed)


def init_db() -> None:
    """Create all tables when they do not exist."""
    try:
        with _get_connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    username   TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT  NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    content TEXT,
                    emotion TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS poetry_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    title TEXT,
                    poetry_content TEXT,
                    emotion_distribution TEXT,
                    blessing TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_journal_entries_user_created
                    ON journal_entries (user_id, created_at DESC, id DESC);

                CREATE INDEX IF NOT EXISTS idx_poetry_reports_user_created
                    ON poetry_reports (user_id, created_at DESC, id DESC);

                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username
                    ON users (username COLLATE NOCASE);

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    conversation_id TEXT NOT NULL DEFAULT 'default',
                    role    TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT    NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created
                    ON chat_messages (user_id, created_at ASC, id ASC);

                CREATE TABLE IF NOT EXISTS conversations (
                    id         TEXT PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    title      TEXT NOT NULL DEFAULT '新对话',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                    ON conversations (user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    emotion TEXT,
                    valence REAL,
                    intensity REAL,
                    tags TEXT,
                    themes TEXT,
                    source TEXT NOT NULL,
                    statement_kind TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    entry_id INTEGER,
                    conversation_id TEXT,
                    parent_id TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_memories_user_layer
                    ON memories (user_id, layer, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_entry
                    ON memories (entry_id);
                """
            )
            connection.commit()
            # Backwards-compat migrations
            row = connection.execute("PRAGMA table_info(journal_entries);").fetchall()
            column_names = [col[1] for col in row]
            if "modified_at" not in column_names:
                connection.execute(
                    "ALTER TABLE journal_entries ADD COLUMN "
                    "modified_at TIMESTAMP;"
                )
                connection.execute(
                    "UPDATE journal_entries SET modified_at = created_at;"
                )
                connection.commit()

            chat_cols = [col[1] for col in connection.execute(
                "PRAGMA table_info(chat_messages);"
            ).fetchall()]
            if "conversation_id" not in chat_cols:
                connection.execute(
                    "ALTER TABLE chat_messages ADD COLUMN conversation_id TEXT NOT NULL DEFAULT 'default';"
                )
                connection.commit()

            # Index may already exist from a fresh install; only create when column is present.
            if "conversation_id" in [col[1] for col in connection.execute(
                "PRAGMA table_info(chat_messages);"
            ).fetchall()]:
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation "
                    "ON chat_messages (conversation_id, created_at ASC, id ASC);"
                )
                connection.commit()

            journal_cols = [col[1] for col in connection.execute(
                "PRAGMA table_info(journal_entries);"
            ).fetchall()]
            for column, ddl in (
                ("valence", "ALTER TABLE journal_entries ADD COLUMN valence REAL"),
                ("intensity", "ALTER TABLE journal_entries ADD COLUMN intensity REAL"),
                ("analysis_json", "ALTER TABLE journal_entries ADD COLUMN analysis_json TEXT"),
            ):
                if column not in journal_cols:
                    connection.execute(ddl)
                    connection.commit()

            conv_cols = [col[1] for col in connection.execute(
                "PRAGMA table_info(conversations);"
            ).fetchall()]
            if "anchor_entry_id" not in conv_cols:
                connection.execute(
                    "ALTER TABLE conversations ADD COLUMN anchor_entry_id INTEGER"
                )
                connection.commit()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to initialize the database") from exc


# ── User management ───────────────────────────────────────────────────────────────

class User(TypedDict):
    id: int
    username: str
    password_hash: str
    created_at: str


def create_user(username: str, password: str) -> User:
    """Hash the password and insert a new user. Raises if the username is taken."""
    validated_username = _validate_username(username)
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters")
    password_hash = _pwd_context.hash(password)

    local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
                """,
                (validated_username, password_hash, local_now),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise SoulJournalDatabaseError("failed to retrieve new user id")
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Username '{validated_username}' is already taken") from exc
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to create user") from exc

    return User(
        id=user_id,
        username=validated_username,
        password_hash=password_hash,
        created_at=local_now,
    )


def verify_user(username: str, password: str) -> User | None:
    """Look up a user and verify the password. Returns None on mismatch."""
    try:
        validated_username = _validate_username(username)
    except ValueError:
        return None

    try:
        with _get_connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
                (validated_username,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to look up user") from exc

    if row is None:
        # Slow-path even on miss so timing attacks don't distinguish "no user" from "bad password"
        _pwd_context.hash(password)
        return None

    if not _pwd_context.verify(password, row["password_hash"]):
        return None

    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        created_at=str(row["created_at"]),
    )


def get_user_by_username(username: str) -> User | None:
    """Return a user by username, or None if not found."""
    try:
        validated_username = _validate_username(username)
    except ValueError:
        return None

    try:
        with _get_connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
                (validated_username,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to look up user") from exc

    if row is None:
        return None

    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        created_at=str(row["created_at"]),
    )


def add_entry(
    user_id: str,
    content: str,
    emotion: str,
    tags: Sequence[str],
    valence: float | None = None,
    intensity: float | None = None,
    analysis_json: str | None = None,
) -> int:
    """Insert a journal entry and return its generated identifier."""
    validated_user_id = _validate_user_id(user_id)
    validated_content = _require_non_empty(content, "content")
    validated_emotion = canonicalize_emotion(emotion) if emotion else "Neutral"
    serialized_tags = _serialize_tags(tags)
    stored_valence = valence_for_emotion(validated_emotion, valence)
    stored_intensity = intensity_for_emotion(intensity)

    # Use local time (not UTC) so the date portion matches what the user sees.
    # SQLite's CURRENT_TIMESTAMP is always UTC, which causes off-by-one-day
    # entries for users east of UTC around midnight.
    local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO journal_entries
                    (user_id, content, emotion, tags, created_at, valence, intensity, analysis_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validated_user_id,
                    validated_content,
                    validated_emotion,
                    serialized_tags,
                    local_now,
                    stored_valence,
                    stored_intensity,
                    analysis_json,
                ),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise SoulJournalDatabaseError(
                    "database did not return an identifier for the journal entry"
                )
            return cursor.lastrowid
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to add the journal entry") from exc


def get_user_entries(user_id: str, limit: int = DEFAULT_ENTRY_LIMIT, offset: int = 0) -> list[JournalEntry]:
    """Return a user's newest journal entries with decoded tag lists."""
    validated_user_id = _validate_user_id(user_id)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an integer")
    if not 1 <= limit <= MAX_ENTRY_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_ENTRY_LIMIT}")

    try:
        with _get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, content, emotion, tags, created_at,
                       valence, intensity, analysis_json
                FROM journal_entries
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (validated_user_id, limit, offset),
            ).fetchall()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to retrieve journal entries") from exc

    return [_entry_from_row(row) for row in rows]


def journal_window(user_id: str, start: str, end: str) -> tuple[list[JournalEntry], bool]:
    user_id = _validate_user_id(user_id)
    with _get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM journal_entries WHERE user_id = ? AND created_at >= ? "
            "AND created_at < ? ORDER BY created_at DESC, id DESC",
            (user_id, start, end),
        ).fetchall()
        earlier = connection.execute(
            "SELECT 1 FROM journal_entries WHERE user_id = ? AND created_at < ? LIMIT 1",
            (user_id, start),
        ).fetchone()
    return [_entry_from_row(row) for row in rows], earlier is not None


def save_poetry_report(
    user_id: str,
    title: str,
    poetry_content: str,
    emotion_distribution: str,
    blessing: str,
) -> int:
    """Save a poetry report and return its generated identifier."""
    values = (
        _require_non_empty(user_id, "user_id"),
        _require_non_empty(title, "title"),
        _require_non_empty(poetry_content, "poetry_content"),
        _require_non_empty(emotion_distribution, "emotion_distribution"),
        _require_non_empty(blessing, "blessing"),
    )

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO poetry_reports (
                    user_id,
                    title,
                    poetry_content,
                    emotion_distribution,
                    blessing
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                values,
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise SoulJournalDatabaseError(
                    "database did not return an identifier for the poetry report"
                )
            return cursor.lastrowid
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to save the poetry report") from exc


def get_latest_poetry_report(user_id: str) -> PoetryReport | None:
    """Return a user's latest poetry report, or ``None`` when none exists."""
    validated_user_id = _validate_user_id(user_id)

    try:
        with _get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    title,
                    poetry_content,
                    emotion_distribution,
                    blessing,
                    created_at
                FROM poetry_reports
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (validated_user_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError(
            "failed to retrieve the latest poetry report"
        ) from exc

    if row is None:
        return None

    return PoetryReport(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        poetry_content=row["poetry_content"],
        emotion_distribution=row["emotion_distribution"],
        blessing=row["blessing"],
        created_at=str(row["created_at"]),
    )


def delete_entry(entry_id: int) -> bool:
    """Delete a journal entry by ID. Returns True if a row was deleted."""
    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM journal_entries WHERE id = ?",
                (int(entry_id),),
            )
            connection.execute(
                "DELETE FROM memories WHERE entry_id = ?",
                (int(entry_id),),
            )
            connection.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to delete the journal entry") from exc


def update_entry(
    entry_id: int,
    content: str,
    emotion: str,
    tags: Sequence[str],
) -> bool:
    """Update an existing journal entry. Returns True if a row was updated."""
    validated_content = _require_non_empty(content, "content")
    validated_emotion = _require_non_empty(emotion, "emotion")
    serialized_tags = _serialize_tags(tags)
    local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE journal_entries
                SET content = ?, emotion = ?, tags = ?, modified_at = ?
                WHERE id = ?
                """,
                (
                    validated_content,
                    validated_emotion,
                    serialized_tags,
                    local_now,
                    int(entry_id),
                ),
            )
            connection.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to update the journal entry") from exc


def get_entry_by_id(entry_id: int) -> JournalEntry | None:
    """Return a single journal entry by its ID, or None if not found."""
    try:
        with _get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, content, emotion, tags, created_at,
                       valence, intensity, analysis_json
                FROM journal_entries
                WHERE id = ?
                """,
                (int(entry_id),),
            ).fetchone()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to retrieve the journal entry") from exc

    if row is None:
        return None

    return _entry_from_row(row)


def get_poetry_reports(user_id: str, limit: int = 10) -> list[PoetryReport]:
    """Return a user's poetry reports, newest first."""
    validated_user_id = _validate_user_id(user_id)

    try:
        with _get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, title, poetry_content, emotion_distribution, blessing, created_at
                FROM poetry_reports
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (validated_user_id, max(1, min(limit, 100))),
            ).fetchall()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to retrieve poetry reports") from exc

    return [
        PoetryReport(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            poetry_content=row["poetry_content"],
            emotion_distribution=row["emotion_distribution"],
            blessing=row["blessing"],
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


# ── Chat message persistence ─────────────────────────────────────────────────────

def add_chat_message(user_id: str, role: str, content: str) -> int:
    """Insert a chat message and return its generated identifier."""
    validated_user_id = _validate_user_id(user_id)
    if role not in ("user", "assistant"):
        raise ValueError("role must be 'user' or 'assistant'")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")

    local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_messages (user_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (validated_user_id, role, content.strip(), local_now),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise SoulJournalDatabaseError(
                    "database did not return an identifier for the chat message"
                )
            return cursor.lastrowid
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to add the chat message") from exc


def get_user_chat_history(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[ChatMessageRecord]:
    """Return a user's chat messages in chronological order (oldest first)."""
    validated_user_id = _validate_user_id(user_id)
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if offset < 0:
        raise ValueError("offset must be non-negative")

    try:
        with _get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, role, content, created_at
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT ? OFFSET ?
                """,
                (validated_user_id, limit, offset),
            ).fetchall()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to retrieve chat history") from exc

    return [
        ChatMessageRecord(
            id=row["id"],
            user_id=row["user_id"],
            role=row["role"],
            content=row["content"],
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


def clear_user_chat_history(user_id: str) -> int:
    """Delete all chat messages for a user. Returns the number of rows deleted."""
    validated_user_id = _validate_user_id(user_id)

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM chat_messages WHERE user_id = ?",
                (validated_user_id,),
            )
            connection.commit()
            return cursor.rowcount
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to clear chat history") from exc


# ── Conversation / per-chat-thread persistence ───────────────────────────────

class Conversation(TypedDict):
    """A chat thread belonging to a user, returned to the API."""

    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    anchor_entry_id: int | None


CONVERSATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _validate_conversation_id(conversation_id: str) -> str:
    if not isinstance(conversation_id, str) or not CONVERSATION_ID_PATTERN.match(conversation_id):
        raise ValueError("conversation_id must match ^[A-Za-z0-9_-]{1,64}$")
    return conversation_id


def _conversation_from_row(row: sqlite3.Row) -> Conversation:
    anchor = None
    keys = row.keys()
    if "anchor_entry_id" in keys and row["anchor_entry_id"] is not None:
        anchor = int(row["anchor_entry_id"])
    return Conversation(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        anchor_entry_id=anchor,
    )


def create_conversation(
    user_id: str,
    title: str = "新对话",
    anchor_entry_id: int | None = None,
) -> Conversation:
    """Create a new conversation owned by ``user_id`` and return it."""
    validated_user_id = _validate_user_id(user_id)
    validated_title = title.strip() or "新对话"
    conversation_id = uuid.uuid4().hex
    local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with _get_connection() as connection:
            connection.execute(
                """
                INSERT INTO conversations
                    (id, user_id, title, created_at, updated_at, anchor_entry_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    validated_user_id,
                    validated_title,
                    local_now,
                    local_now,
                    anchor_entry_id,
                ),
            )
            connection.commit()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to create conversation") from exc

    return Conversation(
        id=conversation_id,
        user_id=validated_user_id,
        title=validated_title,
        created_at=local_now,
        updated_at=local_now,
        anchor_entry_id=anchor_entry_id,
    )


def get_conversation(conversation_id: str) -> Conversation | None:
    """Fetch a conversation by id, regardless of owner."""
    try:
        validated_id = _validate_conversation_id(conversation_id)
    except ValueError:
        return None

    try:
        with _get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, title, created_at, updated_at, anchor_entry_id
                FROM conversations WHERE id = ?
                """,
                (validated_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to read conversation") from exc

    if row is None:
        return None
    return _conversation_from_row(row)


def get_user_conversations(
    user_id: str,
    page: int = 1,
    page_size: int = 30,
) -> list[Conversation]:
    """Return a user's conversations newest-updated first."""
    validated_user_id = _validate_user_id(user_id)
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 200))
    offset = (page - 1) * page_size

    try:
        with _get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, title, created_at, updated_at, anchor_entry_id
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (validated_user_id, page_size, offset),
            ).fetchall()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to list conversations") from exc

    return [_conversation_from_row(row) for row in rows]


def update_conversation_title(conversation_id: str, title: str) -> bool:
    """Rename a conversation. Returns True if updated."""
    try:
        validated_id = _validate_conversation_id(conversation_id)
    except ValueError:
        return False
    new_title = title.strip() or "新对话"
    local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_title, local_now, validated_id),
            )
            connection.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to rename conversation") from exc


def touch_conversation(conversation_id: str) -> bool:
    """Bump ``updated_at`` to ``now``. Returns True if any row was updated."""
    try:
        validated_id = _validate_conversation_id(conversation_id)
    except ValueError:
        return False
    local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (local_now, validated_id),
            )
            connection.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to touch conversation") from exc


def delete_conversation(conversation_id: str) -> bool:
    """Hard-delete a conversation (and its messages via FK cascade). Returns True if deleted."""
    try:
        validated_id = _validate_conversation_id(conversation_id)
    except ValueError:
        return False

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE id = ?",
                (validated_id,),
            )
            connection.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to delete conversation") from exc


def add_conversation_message(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
) -> int:
    """Insert a chat message tied to a specific conversation."""
    validated_user_id = _validate_user_id(user_id)
    validated_conv_id = _validate_conversation_id(conversation_id)
    if role not in ("user", "assistant"):
        raise ValueError("role must be 'user' or 'assistant'")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")

    local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_messages
                    (user_id, conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (validated_user_id, validated_conv_id, role, content.strip(), local_now),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (local_now, validated_conv_id),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise SoulJournalDatabaseError(
                    "database did not return an identifier for the chat message"
                )
            return cursor.lastrowid
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to add the chat message") from exc


def get_conversation_messages(
    conversation_id: str,
    limit: int = 200,
    offset: int = 0,
) -> list[ChatMessageRecord]:
    """Return messages belonging to a conversation in chronological order."""
    try:
        validated_id = _validate_conversation_id(conversation_id)
    except ValueError:
        return []
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if offset < 0:
        raise ValueError("offset must be non-negative")

    try:
        with _get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, role, content, created_at
                FROM chat_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT ? OFFSET ?
                """,
                (validated_id, limit, offset),
            ).fetchall()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to retrieve conversation messages") from exc

    return [
        ChatMessageRecord(
            id=row["id"],
            user_id=row["user_id"],
            role=row["role"],
            content=row["content"],
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


def count_user_conversations(user_id: str) -> int:
    """Return how many conversations the user owns (for pagination metadata)."""
    validated_user_id = _validate_user_id(user_id)
    try:
        with _get_connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM conversations WHERE user_id = ?",
                (validated_user_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to count conversations") from exc
    return int(row["n"]) if row else 0


def ensure_default_conversation(user_id: str) -> Conversation:
    """Find-or-create the user's 'default' conversation.

    Older DBs may contain chat messages tagged with the literal
    ``conversation_id='default'`` that have no matching row in
    ``conversations``. We synthesise one on demand so legacy history
    keeps showing up cleanly.
    """
    validated_user_id = _validate_user_id(user_id)
    try:
        with _get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, title, created_at, updated_at, anchor_entry_id
                FROM conversations WHERE id = 'default' AND user_id = ?
                """,
                (validated_user_id,),
            ).fetchone()
            if row is not None:
                return _conversation_from_row(row)

            local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            connection.execute(
                """
                INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES ('default', ?, ?, ?, ?)
                """,
                (validated_user_id, "历史对话", local_now, local_now),
            )
            connection.commit()
            return Conversation(
                id="default",
                user_id=validated_user_id,
                title="历史对话",
                created_at=local_now,
                updated_at=local_now,
                anchor_entry_id=None,
            )
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to ensure default conversation") from exc


# ── Layered memory persistence ───────────────────────────────────────────────

def _memory_from_row(row: sqlite3.Row) -> MemoryRecord:
    from memory_schema import Provenance

    metadata_raw = row["metadata"]
    metadata: dict = {}
    if metadata_raw:
        try:
            parsed = json.loads(metadata_raw)
            if isinstance(parsed, dict):
                metadata = parsed
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    return MemoryRecord(
        id=row["id"],
        user_id=row["user_id"],
        layer=row["layer"],
        content=row["content"],
        summary=row["summary"],
        emotion=row["emotion"],
        valence=row["valence"],
        intensity=row["intensity"],
        tags=_deserialize_json_list(row["tags"], "tags", row["id"]),
        themes=_deserialize_json_list(row["themes"], "themes", row["id"]),
        provenance=Provenance(
            source=row["source"],
            statement_kind=row["statement_kind"],
            confidence=float(row["confidence"] or 0),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]) if row["updated_at"] else None,
            agent=metadata.get("agent"),
        ),
        entry_id=int(row["entry_id"]) if row["entry_id"] is not None else None,
        conversation_id=row["conversation_id"],
        parent_id=row["parent_id"],
        metadata=metadata,
    )


def save_memory(record: MemoryRecord) -> str:
    """Insert or replace a layered memory record."""
    meta = dict(record.get("metadata") or {})
    agent = record["provenance"].get("agent")
    if agent:
        meta["agent"] = agent
    try:
        with _get_connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, user_id, layer, content, summary, emotion, valence, intensity,
                    tags, themes, source, statement_kind, confidence, entry_id,
                    conversation_id, parent_id, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record["user_id"],
                    record["layer"],
                    record["content"],
                    record.get("summary"),
                    record.get("emotion"),
                    record.get("valence"),
                    record.get("intensity"),
                    json.dumps(record.get("tags") or [], ensure_ascii=False),
                    json.dumps(record.get("themes") or [], ensure_ascii=False),
                    record["provenance"]["source"],
                    record["provenance"]["statement_kind"],
                    record["provenance"]["confidence"],
                    record.get("entry_id"),
                    record.get("conversation_id"),
                    record.get("parent_id"),
                    json.dumps(meta, ensure_ascii=False),
                    record["provenance"]["created_at"],
                    record["provenance"].get("updated_at"),
                ),
            )
            connection.commit()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to save memory") from exc
    return record["id"]


def save_memories(records: Sequence[MemoryRecord]) -> list[str]:
    return [save_memory(record) for record in records]


def get_user_memories(
    user_id: str,
    layer: str | None = None,
    limit: int = 50,
    entry_id: int | None = None,
) -> list[MemoryRecord]:
    validated_user_id = _validate_user_id(user_id)
    limit = max(1, min(int(limit), 500))
    clauses = ["user_id = ?"]
    params: list = [validated_user_id]
    if layer:
        clauses.append("layer = ?")
        params.append(layer)
    if entry_id is not None:
        clauses.append("entry_id = ?")
        params.append(int(entry_id))
    where = " AND ".join(clauses)
    try:
        with _get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM memories
                WHERE {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
    except sqlite3.Error as exc:
        raise SoulJournalDatabaseError("failed to list memories") from exc
    return [_memory_from_row(row) for row in rows]


def get_long_term_themes(user_id: str) -> list[str]:
    records = get_user_memories(user_id, layer="long_term", limit=100)
    themes: list[str] = []
    for record in records:
        for theme in record.get("themes") or []:
            if theme not in themes:
                themes.append(theme)
        if record.get("summary") and record["summary"] not in themes:
            themes.append(record["summary"])
    return themes


if __name__ == "__main__":
    init_db()
