import os
from typing import Set

# log 관련 설정
LOG_FILE = os.environ.get("LOG_FILE", "./log/sync_view.log")

# MongoDB settings
DB_URL = os.environ["MONGO_INTERNAL_URI"]
OUT_DB_URL = os.environ["MONGO_EXTERNAL_URI"]
# Only "er_game_view" DB is allowed to sync from this agent.
OUT_DB_NAMES = "er_game_view"

def _parse_csv_env(name: str, default: str = "") -> Set[str]:
    raw = os.getenv(name, default)
    items = [x.strip() for x in raw.split(",")]
    return {x for x in items if x}

SYNC_ALLOWED_COLLECTIONS: Set[str] = _parse_csv_env(
    "SYNC_ALLOWED_COLLECTIONS",
    "versions,character_statistics",
)

SYNC_ALLOWED_REPORT_COLLECTIONS: Set[str] = set()
