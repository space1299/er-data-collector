from __future__ import annotations

from typing import Optional

from pymongo import MongoClient

_CLIENTS: dict[str, MongoClient] = {}


def get_client(*, db_url: Optional[str] = None) -> MongoClient:
    if not db_url:
        raise RuntimeError("DB_URL is required but not configured")
    url = db_url
    client = _CLIENTS.get(url)
    if client is None:
        client = MongoClient(url)
        _CLIENTS[url] = client
    return client
