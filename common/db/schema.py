from typing import Iterable

DB_NAMES = {
    "info": "er_game_info",
    "view": "er_game_view",
    "report": "er_user_report",
}

RAW_DB_PREFIX = "er_game_data_v"

VIEW_COLLECTIONS: tuple[str, ...] = (
    "versions",
    "info_changes",
    "character_statistics",
)

INFO_COLLECTIONS: tuple[str, ...] = (
    "l10n_info",
    "current",
    "snapshots",
    "changes",
)

RAW_COLLECTIONS: tuple[str, ...] = (
    "game_data_raw",
    "user_checks",
    "character_statistics",
)

REPORT_COLLECTIONS: tuple[str, ...] = (
    "report_jobs",
)


def raw_db_name(version_str: str) -> str:
    suffix = (version_str or "").replace(".", "_")
    return f"{RAW_DB_PREFIX}{suffix}"


INDEXES: tuple[tuple[str, str, Iterable, dict], ...] = (
    # -----------------------
    # view DB
    # -----------------------
    # view.versions
    ("view", "versions", [("version_str", 1)], {"name": "uq_version_str", "unique": True}),
    ("view", "versions", [("season", -1), ("major", -1), ("minor", -1)], {"name": "idx_version_sort"}),
    ("view", "versions", [("last_seen_at", -1)], {"name": "last_seen_at_-1"}),

    # view.character_statistics (1 doc per versionStr + mmrRange)
    ("view", "character_statistics", [("versionStr", 1), ("mmrRange", 1)], {"name": "uq_versionStr_mmrRange", "unique": True}),
    ("view", "character_statistics", [("versionMajor", 1), ("versionMinor", 1)], {"name": "idx_version_parts"}),

    # view.info_changes (UI/조회용: 최신 변경부터)
    ("view", "info_changes", [("detected_at", -1)], {"name": "idx_detected_at"}),

    # -----------------------
    # info DB
    # -----------------------
    # info.current: _id==key 형태. (정렬/조회 보조 인덱스만)
    ("info", "current", [("changedAt", -1)], {"name": "idx_changedAt"}),
    ("info", "current", [("fetchedAt", -1)], {"name": "idx_fetchedAt"}),

    # info.l10n_info: _id==locale 형태. (최근 fetch 정렬용)
    ("info", "l10n_info", [("fetchedAt", -1)], {"name": "idx_fetchedAt"}),

    # info.snapshots: 스냅샷 이력 (key + savedAt 기준으로 최신 스냅샷 조회)
    ("info", "snapshots", [("key", 1), ("savedAt", -1)], {"name": "idx_key_savedAt"}),

    # info.changes: 변경 이력 (최신부터)
    ("info", "changes", [("detected_at", -1)], {"name": "idx_detected_at"}),

    # -----------------------
    # raw DB
    # -----------------------
    # raw.user_checks: 작업 큐 성격 (nickname 유일 + lastChecked 정렬)
    ("raw", "user_checks", [("nickname", 1)], {"name": "uq_nickname", "unique": True}),
    ("raw", "user_checks", [("lastChecked", 1)], {"name": "idx_lastChecked"}),

    # raw.game_data_raw: (nickname, gameId) 1건 보장 + nickname 기반 최근 조회
    ("raw", "game_data_raw", [("nickname", 1), ("gameId", 1)], {"name": "uq_nickname_gameId", "unique": True}),
    ("raw", "game_data_raw", [("nickname", 1), ("startDtm", -1)], {"name": "idx_nickname_startDtm"}),  # startDtm이 항상 있으면 추천
    ("raw", "game_data_raw", [("gameId", 1)], {"name": "idx_gameId"}),

    # raw.character_statistics: 집계 raw 결과 (버전+티어+캐릭터+무기 유일)
    ("raw", "character_statistics",
     [("versionSeason", 1), ("versionMajor", 1), ("versionMinor", 1), ("mmrRange", 1), ("characterNum", 1), ("bestWeapon", 1)],
     {"name": "uq_version_mmr_character_weapon", "unique": True}),
    ("raw", "character_statistics",
     [("versionSeason", 1), ("versionMajor", 1), ("versionMinor", 1), ("mmrRange", 1)],
     {"name": "idx_version_mmr"}),

    # -----------------------
    # report DB
    # -----------------------
    # report.report_jobs: 큐 (dedupe + 상태조회 + TTL)
    ("report", "report_jobs", [("dedupe_key", 1)], {"name": "uq_dedupe_key", "unique": True}),
    ("report", "report_jobs", [("status", 1), ("updatedAt", 1)], {"name": "idx_status_updated"}),
    ("report", "report_jobs", [("expiresAt", 1)], {"name": "ttl_expiresAt", "expireAfterSeconds": 0}),
)
