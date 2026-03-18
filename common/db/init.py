from __future__ import annotations

from typing import Iterable, Optional

from pymongo import MongoClient

from .access import info_db, raw_db, report_db, view_db
from .schema import INDEXES, raw_db_name

_APPLIED: set[tuple[str, str, str]] = set()


def _ensure_collection_index(col, keys, options: dict, db_name: str, col_name: str) -> None:
    name = options.get("name") or str(keys)
    key = (db_name, col_name, name)
    if key in _APPLIED:
        return
    col.create_index(keys, **options)
    _APPLIED.add(key)


def ensure_indexes(client: MongoClient, *, raw_versions: Optional[Iterable[str]] = None) -> None:
    raw_versions = list(raw_versions or [])

    for db_key, col_name, keys, options in INDEXES:
        if db_key == "view":
            col = view_db(client)[col_name]
            _ensure_collection_index(col, keys, options, "view", col_name)
        elif db_key == "info":
            col = info_db(client)[col_name]
            _ensure_collection_index(col, keys, options, "info", col_name)
        elif db_key == "report":
            col = report_db(client)[col_name]
            _ensure_collection_index(col, keys, options, "report", col_name)
        elif db_key == "raw":
            if not raw_versions:
                continue
            for version_str in raw_versions:
                db_name = raw_db_name(version_str)
                col = raw_db(client, version_str)[col_name]
                _ensure_collection_index(col, keys, options, db_name, col_name)
