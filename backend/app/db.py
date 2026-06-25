from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from app.models import DuplicateItem, DuplicateVersion, MediaItem
from app.services.duplicate_analysis import build_versions, find_deletable


SCHEMA = """
CREATE TABLE IF NOT EXISTS media_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plex_rating_key TEXT NOT NULL UNIQUE,
    library TEXT NOT NULL,
    media_type TEXT NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    added_at TEXT NOT NULL,
    play_count INTEGER NOT NULL DEFAULT 0,
    last_played TEXT,
    watched_by_json TEXT NOT NULL DEFAULT '[]',
    requested_by TEXT,
    request_date TEXT,
    manager_kind TEXT NOT NULL DEFAULT 'none',
    manager_id INTEGER,
    available INTEGER NOT NULL DEFAULT 1,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    file_paths_json TEXT NOT NULL DEFAULT '[]',
    file_versions_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_media_item_library_added
    ON media_item(library, added_at);
"""

SCHEMA_MIGRATIONS = [
    "ALTER TABLE media_item ADD COLUMN file_paths_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE media_item ADD COLUMN file_versions_json TEXT NOT NULL DEFAULT '[]'",
]


DEMO_ITEMS = (
    {
        "plex_rating_key": "1001",
        "library": "Movies",
        "media_type": "movie",
        "title": "Arrival",
        "year": 2016,
        "added_at": "2023-01-18T09:15:00+00:00",
        "play_count": 4,
        "last_played": "2025-10-05T19:30:00+00:00",
        "watched_by": ["Kyle", "Sam"],
        "requested_by": "Sam",
        "request_date": "2023-01-12T10:00:00+00:00",
        "manager_kind": "radarr",
        "manager_id": 41,
        "available": True,
        "file_size_bytes": 8_734_003_200,
    },
    {
        "plex_rating_key": "1002",
        "library": "Movies",
        "media_type": "movie",
        "title": "The Vast of Night",
        "year": 2019,
        "added_at": "2023-02-02T12:20:00+00:00",
        "play_count": 0,
        "last_played": None,
        "watched_by": [],
        "requested_by": "Alex",
        "request_date": "2023-01-27T08:00:00+00:00",
        "manager_kind": "radarr",
        "manager_id": 88,
        "available": True,
        "file_size_bytes": 5_368_709_120,
    },
    {
        "plex_rating_key": "2001",
        "library": "TV Shows",
        "media_type": "show",
        "title": "The Expanse",
        "year": 2015,
        "added_at": "2022-11-01T21:12:00+00:00",
        "play_count": 26,
        "last_played": "2026-02-20T06:45:00+00:00",
        "watched_by": ["Kyle"],
        "requested_by": "Kyle",
        "request_date": "2022-10-28T16:25:00+00:00",
        "manager_kind": "sonarr",
        "manager_id": 12,
        "available": True,
        "file_size_bytes": 192_414_534_656,
    },
    {
        "plex_rating_key": "2002",
        "library": "TV Shows",
        "media_type": "show",
        "title": "Counterpart",
        "year": 2017,
        "added_at": "2023-05-28T04:18:00+00:00",
        "play_count": 0,
        "last_played": None,
        "watched_by": [],
        "requested_by": None,
        "request_date": None,
        "manager_kind": "sonarr",
        "manager_id": 59,
        "available": False,
        "file_size_bytes": 64_424_509_440,
    },
)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _run_migrations(conn)
    conn.commit()


def _run_migrations(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_MIGRATIONS:
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass  # column already exists


def seed_demo_data(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS count FROM media_item").fetchone()["count"]
    if existing:
        return
    upsert_media_items(conn, DEMO_ITEMS)


def upsert_media_items(conn: sqlite3.Connection, items: Iterable[dict]) -> None:
    for item in items:
        conn.execute(
            """
            INSERT INTO media_item (
                plex_rating_key, library, media_type, title, year, added_at, play_count,
                last_played, watched_by_json, requested_by, request_date, manager_kind,
                manager_id, available, file_size_bytes, file_paths_json, file_versions_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plex_rating_key) DO UPDATE SET
                library=excluded.library,
                media_type=excluded.media_type,
                title=excluded.title,
                year=excluded.year,
                added_at=excluded.added_at,
                play_count=excluded.play_count,
                last_played=excluded.last_played,
                watched_by_json=excluded.watched_by_json,
                requested_by=excluded.requested_by,
                request_date=excluded.request_date,
                manager_kind=excluded.manager_kind,
                manager_id=excluded.manager_id,
                available=excluded.available,
                file_size_bytes=excluded.file_size_bytes,
                file_paths_json=excluded.file_paths_json,
                file_versions_json=excluded.file_versions_json
            """,
            (
                item["plex_rating_key"],
                item["library"],
                item["media_type"],
                item["title"],
                item.get("year"),
                item["added_at"],
                item.get("play_count", 0),
                item.get("last_played"),
                json.dumps(item.get("watched_by", [])),
                item.get("requested_by"),
                item.get("request_date"),
                item.get("manager_kind", "none"),
                item.get("manager_id"),
                1 if item.get("available", True) else 0,
                item.get("file_size_bytes", 0),
                json.dumps([v.get("path", "") for v in item.get("file_versions", [])]),
                json.dumps(item.get("file_versions", [])),
            ),
        )
    conn.commit()


def list_media(conn: sqlite3.Connection, library: str | None = None) -> list[MediaItem]:
    sql = "SELECT * FROM media_item"
    params: tuple[str, ...] = ()
    if library:
        sql += " WHERE library = ?"
        params = (library,)
    sql += " ORDER BY added_at ASC, title ASC"

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_media_item(row) for row in rows]


def get_media_by_ids(conn: sqlite3.Connection, ids: list[int]) -> list[MediaItem]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT * FROM media_item WHERE id IN ({placeholders}) ORDER BY added_at ASC",
        tuple(ids),
    ).fetchall()
    return [_row_to_media_item(row) for row in rows]


def list_duplicates(
    conn: sqlite3.Connection,
    local_prefixes: tuple[str, ...],
    protected_prefixes: tuple[str, ...],
    library: str | None = None,
) -> list[DuplicateItem]:
    if not local_prefixes or not protected_prefixes:
        return []  # duplicate detection disabled until paths configured

    sql = "SELECT * FROM media_item WHERE file_versions_json != '[]' AND file_versions_json IS NOT NULL"
    params: tuple[str, ...] = ()
    if library:
        sql += " AND library = ?"
        params = (library,)
    sql += " ORDER BY title ASC"
    rows = conn.execute(sql, params).fetchall()

    results: list[DuplicateItem] = []
    for row in rows:
        file_versions: list[dict] = json.loads(row["file_versions_json"] or "[]")
        versions = build_versions(file_versions, row["media_type"], local_prefixes, protected_prefixes)
        deletable = find_deletable(versions, row["media_type"])
        if not deletable:
            continue
        item = _row_to_media_item(row)
        results.append(DuplicateItem(
            **item.model_dump(),
            local_paths=[d.local_path for d in deletable],
            nas_paths=sorted({d.protected_path for d in deletable}),
            duplicate_versions=[
                DuplicateVersion(
                    identity=d.identity,
                    local_path=d.local_path,
                    local_size_bytes=d.local_size,
                    local_quality=d.local_quality,
                    nas_path=d.protected_path,
                    nas_quality=d.protected_quality,
                )
                for d in deletable
            ],
            reclaimable_bytes=sum(d.local_size for d in deletable),
        ))
    return results


def mark_media_unavailable(conn: sqlite3.Connection, ids: list[int]) -> None:
    if not ids:
        return
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE media_item SET available = 0 WHERE id IN ({placeholders})",
        tuple(ids),
    )
    conn.commit()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _row_to_media_item(row: sqlite3.Row) -> MediaItem:
    return MediaItem(
        id=row["id"],
        plex_rating_key=row["plex_rating_key"],
        library=row["library"],
        media_type=row["media_type"],
        title=row["title"],
        year=row["year"],
        added_at=_parse_datetime(row["added_at"]) or datetime.now(UTC),
        play_count=row["play_count"],
        last_played=_parse_datetime(row["last_played"]),
        watched_by=json.loads(row["watched_by_json"]),
        requested_by=row["requested_by"],
        request_date=_parse_datetime(row["request_date"]),
        manager_kind=row["manager_kind"],
        manager_id=row["manager_id"],
        available=bool(row["available"]),
        file_size_bytes=row["file_size_bytes"],
        file_paths=json.loads(row["file_paths_json"] or "[]"),
    )
