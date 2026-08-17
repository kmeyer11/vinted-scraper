"""SQLite-backed 'seen items' store so runs only report new matches."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Union


class SeenStore:
    def __init__(self, db_path: Union[str, Path] = "vinted_watch.db"):
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_items (
                item_id TEXT PRIMARY KEY,
                watch_name TEXT NOT NULL,
                title TEXT,
                price TEXT,
                url TEXT,
                first_seen TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def is_new(self, item_id: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM seen_items WHERE item_id = ?", (item_id,))
        return cur.fetchone() is None

    def mark_seen(self, item_id: str, watch_name: str, title: str, price: str, url: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_items (item_id, watch_name, title, price, url, first_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, watch_name, title, price, url, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SeenStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
