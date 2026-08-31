"""Persistence for scans and their per-field results.

Two interchangeable backends behind one interface:

  SupabaseStorage  used when SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set
  LocalStorage     SQLite + a local uploads folder, used when they are not

The local backend exists because Supabase credentials arrive later than the rest
of the build, and a scanner that cannot show a history is not demonstrable. Its
tables mirror schema.sql column for column, so moving to Supabase is a matter of
filling in .env — no code change, no data model change.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Protocol

import supabase_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "data", "checkbuddy.db")

HISTORY_LIMIT = 50


class Storage(Protocol):
    name: str

    def upload_image(self, data: bytes, filename: str) -> str: ...
    def save_scan(self, scan: dict, field_results: list[dict]) -> None: ...
    def list_scans(self, limit: int = HISTORY_LIMIT) -> list[dict]: ...
    def get_scan(self, scan_id: str) -> dict | None: ...


# --- local -------------------------------------------------------------------


class LocalStorage:
    """SQLite + on-disk images. Mirrors the Supabase schema exactly."""

    name = "local (SQLite + ./uploads)"

    def __init__(self) -> None:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scans (
                    id             TEXT PRIMARY KEY,
                    barcode        TEXT,
                    image_url      TEXT,
                    ocr_raw_text   TEXT,
                    overall_status TEXT NOT NULL,
                    created_at     TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scan_results (
                    id            TEXT PRIMARY KEY,
                    scan_id       TEXT NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    field_name    TEXT NOT NULL,
                    status        TEXT NOT NULL,
                    matched_text  TEXT,
                    confidence    REAL,
                    note          TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_scan_results_scan_id
                    ON scan_results(scan_id);
                """
            )

    def upload_image(self, data: bytes, filename: str) -> str:
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, "wb") as handle:
            handle.write(data)
        # Served by FastAPI's static mount in main.py.
        return f"/uploads/{filename}"

    def save_scan(self, scan: dict, field_results: list[dict]) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO scans
                       (id, barcode, image_url, ocr_raw_text, overall_status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    scan["id"], scan["barcode"], scan["image_url"],
                    scan["ocr_raw_text"], scan["overall_status"], scan["created_at"],
                ),
            )
            conn.executemany(
                """INSERT INTO scan_results
                       (id, scan_id, field_name, status, matched_text, confidence, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        str(uuid.uuid4()), scan["id"], r["field_name"], r["status"],
                        r.get("matched_text"), r.get("confidence"), r.get("note"),
                    )
                    for r in field_results
                ],
            )

    def list_scans(self, limit: int = HISTORY_LIMIT) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, barcode, overall_status, image_url, created_at
                     FROM scans ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_scan(self, scan_id: str) -> dict | None:
        with self._connect() as conn:
            scan = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
            if scan is None:
                return None
            results = conn.execute(
                """SELECT field_name, status, matched_text, confidence, note
                     FROM scan_results WHERE scan_id = ?""",
                (scan_id,),
            ).fetchall()
        return {**dict(scan), "fields": [dict(r) for r in results]}


# --- supabase ----------------------------------------------------------------


class SupabaseStorage:
    """Postgres tables + the `label-photos` Storage bucket."""

    name = "supabase"

    def __init__(self) -> None:
        self.client = supabase_client.get_client()
        self.bucket = supabase_client.LABEL_BUCKET

    def upload_image(self, data: bytes, filename: str) -> str:
        self.client.storage.from_(self.bucket).upload(
            filename, data, {"content-type": "image/jpeg", "upsert": "true"}
        )
        return self.client.storage.from_(self.bucket).get_public_url(filename)

    def save_scan(self, scan: dict, field_results: list[dict]) -> None:
        self.client.table("scans").insert(scan).execute()
        self.client.table("scan_results").insert(
            [{"scan_id": scan["id"], **r} for r in field_results]
        ).execute()

    def list_scans(self, limit: int = HISTORY_LIMIT) -> list[dict]:
        response = (
            self.client.table("scans")
            .select("id, barcode, overall_status, image_url, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def get_scan(self, scan_id: str) -> dict | None:
        scan = self.client.table("scans").select("*").eq("id", scan_id).execute()
        if not scan.data:
            return None
        results = (
            self.client.table("scan_results")
            .select("field_name, status, matched_text, confidence, note")
            .eq("scan_id", scan_id)
            .execute()
        )
        return {**scan.data[0], "fields": results.data or []}


# --- selection ---------------------------------------------------------------

_storage: Storage | None = None


def get_storage() -> Storage:
    """The active backend, chosen once at first use."""
    global _storage
    if _storage is None:
        if supabase_client.is_configured():
            _storage = SupabaseStorage()
        else:
            _storage = LocalStorage()
    return _storage


def new_scan_row(barcode: str | None, image_url: str, ocr_raw_text: str,
                 overall_status: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "barcode": barcode or None,
        "image_url": image_url,
        "ocr_raw_text": ocr_raw_text,
        "overall_status": overall_status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
