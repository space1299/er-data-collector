from __future__ import annotations

from pymongo import MongoClient

from .schema import DB_NAMES, RAW_DB_PREFIX


def info_db(client: MongoClient):
    return client[DB_NAMES["info"]]


def view_db(client: MongoClient):
    return client[DB_NAMES["view"]]


def report_db(client: MongoClient):
    return client[DB_NAMES["report"]]


def raw_db(client: MongoClient, version_str: str):
    suffix = (version_str or "").replace(".", "_")
    return client[f"{RAW_DB_PREFIX}{suffix}"]
