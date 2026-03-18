from datetime import datetime, timezone
import re
from typing import Optional, Dict, Any, List

from pymongo import MongoClient

from common.er_api import get_user_game_data, get_user_id, get_game_data_raw
from common.db.access import info_db, raw_db, view_db
from common.mongo_db import insert_data
from common.logger import setup_logger
from common.er_version import (
    format_version_str,
    get_version_doc_by_season_id,
    season_name_from_info_current,
    SeasonNameResolutionError,
)

import pytz

logger = setup_logger("collect_data_raw")


# ===== version probe =====
def _extract_last_number(value: str) -> Optional[int]:
    if not isinstance(value, str):
        return None
    numbers = re.findall(r"(\d+)", value)
    if not numbers:
        return None
    try:
        return int(numbers[-1])
    except Exception:
        return None


def _resolve_season_number(client: MongoClient, season_id: int) -> Optional[int]:
    col_versions = view_db(client)["versions"]
    doc = get_version_doc_by_season_id(col_versions, season_id)
    if doc and doc.get("season") is not None:
        try:
            return int(doc.get("season"))
        except Exception:
            pass

    try:
        col_info_current = info_db(client)["current"]
    except Exception:
        return None

    try:
        season_name = season_name_from_info_current(col_info_current, season_id)
    except SeasonNameResolutionError:
        return None

    return _extract_last_number(season_name)


def get_one_game_with_version(client: MongoClient, user_id: int) -> Optional[Dict[str, Any]]:
    data = get_user_game_data(user_id, next_game_id=None)

    user_games = data.get("userGames", [])
    if not user_games:
        logger.info(f"[version_probe] user_id={user_id} 에 대해 userGames 없음")
        return None

    for game in user_games:
        matchingmode = int(game.get("matchingMode", 0))
        if matchingmode != 3:
            continue

        game_id = game.get("gameId")
        season_id = int(game.get("seasonId", 0))
        ver_major = int(game.get("versionMajor", 0))
        ver_minor = int(game.get("versionMinor", 0))

        display_season = _resolve_season_number(client, season_id)
        version_str = None
        if display_season is not None:
            version_str = format_version_str(display_season, ver_major, ver_minor)

        result = {
            "gameId": game_id,
            "seasonId": season_id,
            "displaySeason": display_season,
            "versionMajor": ver_major,
            "versionMinor": ver_minor,
            "versionStr": version_str,
            "raw": game,
        }

        logger.info(
            f"[version_probe] user_id={user_id}, gameId={game_id}, "
            f"seasonId={season_id}, displaySeason={display_season}, "
            f"version={version_str}"
        )
        return result

    logger.info(f"[version_probe] user_id={user_id} 에 대해 matchingMode=3 게임이 없습니다.")
    return None


def _build_new_version_doc(client: MongoClient, game: dict) -> dict:
    game_season_id = int(game.get("seasonId", 0))
    ver_major = int(game.get("versionMajor", 0))
    ver_minor = int(game.get("versionMinor", 0))

    display_season = _resolve_season_number(client, game_season_id)
    now = datetime.now(timezone.utc)

    doc = {
        "version_str": format_version_str(display_season, ver_major, ver_minor),  # "9.4.0"
        "season": display_season,
        "season_id": game_season_id,
        "major": ver_major,
        "minor": ver_minor,
        "first_seen_at": now,
        "last_seen_at": now,
        "source": {
            "sample_nickname": game.get("nickname"),
            "sample_gameId": game.get("gameId"),
        },
    }
    return doc


def upsert_version_from_game(client: MongoClient, game: dict) -> None:
    doc = _build_new_version_doc(client, game)
    col_versions = view_db(client)["versions"]

    now = doc["last_seen_at"]
    doc_insert = {k: v for k, v in doc.items() if k != "last_seen_at"}

    col_versions.update_one(
        {"version_str": doc["version_str"]},
        {"$setOnInsert": doc_insert, "$set": {"last_seen_at": now}},
        upsert=True,
    )

    logger.info(
        f"[versions] 버전 upsert: {doc['version_str']} "
        f"(season_id={doc['season_id']}, gameId={doc['source']['sample_gameId']})"
    )


# ===== pagination: userGames -> gameId list for target version =====
def get_all_user_game_data(
    client: MongoClient,
    user_id: int,
    season_id: int,
    major: int,
    minor: int,
) -> List[Any]:
    game_ids: List[Any] = []
    next_game_id = None

    season_id = int(season_id)
    version_major = int(major)
    version_minor = int(minor)

    while True:
        data = get_user_game_data(user_id, next_game_id)

        if not data:
            logger.warning(f"[collect_raw] userGames 조회 실패로 중단: user_id={user_id}, next={next_game_id}")
            return game_ids

        user_games = data.get("userGames", [])

        for game in user_games:
            matchingmode = int(game.get("matchingMode", 0))
            if matchingmode != 3:
                continue

            game_season_id = int(game.get("seasonId", 0))
            ver_major = int(game.get("versionMajor", 0))
            ver_minor = int(game.get("versionMinor", 0))

            target = (season_id, version_major, version_minor)
            current = (game_season_id, ver_major, ver_minor)

            if current == target:
                game_ids.append(game.get("gameId"))

            elif current < target:
                logger.info(f"조회 할 gameid 개수: {len(game_ids)}")
                return game_ids

            else:
                # 더 최신 버전을 만났으면 versions 갱신 + 해당 gameId는 수집 포함 후 종료
                upsert_version_from_game(client, game)
                game_ids.append(game.get("gameId"))
                logger.info(f"조회 할 gameid 개수: {len(game_ids)}")
                return game_ids

        next_game_id = data.get("next")
        if not next_game_id:
            break

    logger.info(f"조회 할 gameid 개수: {len(game_ids)}")
    return game_ids


# ===== user_checks =====
def _insert_user_checks(col_game_data_raw, col_user_checks) -> None:
    try:
        nicknames = col_game_data_raw.distinct("nickname")
        nicknames = [n for n in nicknames if n]

        if not nicknames:
            logger.info("[user_checks] game_data_raw에 nickname이 없습니다.")
            return

        existing_nicks = set(col_user_checks.distinct("nickname"))
        new_nicks = [n for n in nicknames if n not in existing_nicks]

        logger.info(f"[user_checks] 새로 추가할 nickname 수: {len(new_nicks)}")

        if not new_nicks:
            logger.info("[user_checks] 추가할 nickname 없음. 종료합니다.")
            return

        new_docs = [{"nickname": n, "lastChecked": None} for n in new_nicks]
        insert_data(new_docs, col_user_checks)

    except Exception as e:
        logger.exception(f"[user_checks] nickname 저장 중 오류: {e}")


def _get_next_users_for_check(col_user_checks, col_game_data_raw, batch_size: int = 10) -> List[str]:
    try:
        results = list(
            col_user_checks.find({}, {"_id": 0, "nickname": 1, "lastChecked": 1})
            .sort([("lastChecked", 1)])
            .limit(batch_size)
        )

        if not results:
            return []

        # 이미 한번이라도 돌았으면(= lastChecked가 모두 None이 아님) 최신 nickname을 보강
        if results[0].get("lastChecked") is not None:
            _insert_user_checks(col_game_data_raw, col_user_checks)

        now_kst = datetime.now(pytz.timezone("Asia/Seoul"))
        nicknames = [doc["nickname"] for doc in results if doc.get("nickname")]

        if not nicknames:
            return []

        col_user_checks.update_many(
            {"nickname": {"$in": nicknames}},
            {"$set": {"lastChecked": now_kst}},
        )

        return nicknames

    except Exception as e:
        logger.error(f"[user_checks] get_next_users_for_check 에러: {e}")
        return []


# ===== versions -> doc =====
def _resolve_version_doc(client: MongoClient, version_str: str) -> Optional[dict]:
    col_versions = view_db(client)["versions"]
    doc = col_versions.find_one({"version_str": version_str})
    if not doc:
        logger.error(f"[collect_raw] versions 컬렉션에 version={version_str!r} 문서가 없습니다.")
        return None
    return doc


def _list_versions_desc(client: MongoClient) -> List[dict]:
    col_versions = view_db(client)["versions"]
    return list(
        col_versions.find({}, {"version_str": 1, "season": 1, "major": 1, "minor": 1})
        .sort([("season", -1), ("major", -1), ("minor", -1)])
    )


def _get_previous_version_str(client: MongoClient, current_version: str) -> Optional[str]:
    versions = _list_versions_desc(client)
    for i, doc in enumerate(versions):
        if doc.get("version_str") == current_version:
            if i + 1 < len(versions):
                return versions[i + 1].get("version_str")
            return None
    return None


def _user_checks_has_any(col_user_checks) -> bool:
    return col_user_checks.find_one({}, {"_id": 1}) is not None


def _copy_user_checks(
    src_col,
    dst_col,
    batch_size: int = 1000,
) -> int:
    inserted = 0
    batch: List[dict] = []

    for doc in src_col.find({}):
        if "_id" in doc:
            del doc["_id"]
        batch.append(doc)
        if len(batch) >= batch_size:
            dst_col.insert_many(batch, ordered=False)
            inserted += len(batch)
            batch = []

    if batch:
        dst_col.insert_many(batch, ordered=False)
        inserted += len(batch)

    return inserted


def ensure_user_checks_seeded(
    client: MongoClient,
    version_str: str,
    init_nickname: Optional[str] = None,
) -> bool:
    raw = raw_db(client, version_str)
    col_user_checks = raw["user_checks"]

    if _user_checks_has_any(col_user_checks):
        return True

    prev_version = _get_previous_version_str(client, version_str)
    if prev_version:
        try:
            prev_raw = raw_db(client, prev_version)
            src_col = prev_raw["user_checks"]
            if _user_checks_has_any(src_col):
                inserted = _copy_user_checks(src_col, col_user_checks)
                if inserted > 0:
                    logger.info(
                        f"[seed] user_checks copied: {prev_version} -> {version_str}, "
                        f"inserted={inserted}"
                    )
                    return True
        except Exception as e:
            logger.exception(f"[seed] user_checks copy failed: {e}")

    if init_nickname:
        try:
            init_data_once(client, init_nickname)
            if _user_checks_has_any(col_user_checks):
                logger.info(f"[seed] user_checks initialized by init_nickname={init_nickname!r}")
                return True
        except Exception as e:
            logger.exception(f"[seed] init_data_once failed: {e}")

    return False


# ===== worker entrypoints (logic only) =====
def collect_raw_once(client: MongoClient, version: str, batch_size: int = 10) -> None:
    ver_doc = _resolve_version_doc(client, version)
    if not ver_doc:
        return

    try:
        season_id = int(ver_doc["season_id"])
        major = int(ver_doc["major"])
        minor = int(ver_doc["minor"])
    except Exception as e:
        logger.error(f"[collect_raw] 버전 문서 파싱 실패: {e}, doc={ver_doc}")
        return

    raw = raw_db(client, version)
    col_game_data_raw = raw["game_data_raw"]
    col_user_checks = raw["user_checks"]

    nicknames: List[str] = _get_next_users_for_check(
        col_user_checks,
        col_game_data_raw,
        batch_size=batch_size,
    )
    if not nicknames:
        logger.info("[collect_raw] 조회할 nickname 이 없습니다.")
        return

    logger.info(f"[collect_raw] 다음 조회 nickname: {nicknames}")

    for nickname in nicknames:
        user_id = get_user_id(nickname)
        if user_id is None:
            logger.warning(f"[collect_raw] nickname={nickname!r} → user_id 조회 실패(응답 user 없음/에러). 스킵")
            continue

        game_ids = get_all_user_game_data(
            client=client,
            user_id=user_id,
            season_id=season_id,
            major=major,
            minor=minor,
        )
        logger.info(
            f"[collect_raw] nickname={nickname!r}, user_id={user_id}, "
            f"대상 gameId 수={len(game_ids)}"
        )

        for game_id in game_ids:
            game_data = get_game_data_raw(game_id)
            if not isinstance(game_data, dict) or "error" in game_data:
                logger.warning(
                    f"[collect_raw] gameId={game_id} 조회 실패. "
                    f"status={getattr(game_data, 'get', lambda _: '?')('status_code')}"
                )
                continue

            user_games = game_data.get("userGames") or []
            if not user_games:
                logger.warning(f"[collect_raw] gameId={game_id} 응답에 userGames 없음/빈값")
                continue

            insert_data(game_data.get("userGames"), col_game_data_raw)

        logger.info(
            f"[collect_raw] nickname={nickname!r}, user_id={user_id} 에 대해 "
            f"{len(game_ids)}개의 game data 처리 완료"
        )


def init_data_once(client: MongoClient, nickname: str) -> Optional[str]:
    logger.info(f"[init] 초기화 시작: nickname={nickname!r}")

    user_id = get_user_id(nickname)
    if user_id is None:
        logger.warning(f"[collect_raw] nickname={nickname!r} → user_id 조회 실패(응답 user 없음/에러). 스킵")
        return None

    logger.info(f"[init] nickname={nickname!r} → user_id={user_id}")

    probe = get_one_game_with_version(client, user_id)
    if not probe:
        logger.error(f"[init] user_id={user_id} 에 대해 matchingMode=3 게임을 찾지 못함")
        return None

    game_id_probe = probe["gameId"]
    season_id = probe["seasonId"]
    version_season = probe["displaySeason"]
    major = probe["versionMajor"]
    minor = probe["versionMinor"]

    if version_season is None:
        logger.error(
            f"[init] 시즌 번호(displaySeason)를 계산하지 못했습니다. "
            f"seasonId={season_id}, raw={probe['raw']}"
        )
        return None

    version_str = format_version_str(version_season, major, minor)
    logger.info(
        f"[init] 현재 버전 판정: version={version_str} "
        f"(seasonId={season_id}, gameId={game_id_probe})"
    )

    raw = raw_db(client, version_str)
    col_game_data_raw = raw["game_data_raw"]
    col_user_checks = raw["user_checks"]

    upsert_version_from_game(client, probe["raw"])

    game_ids = get_all_user_game_data(
        client=client,
        user_id=user_id,
        season_id=season_id,
        major=major,
        minor=minor,
    )

    logger.info(f"[init] 수집 대상 gameId 수: {len(game_ids)}")

    for gid in game_ids:
        logger.info(f"[init] 게임 조회: gameId={gid}")
        game_data = get_game_data_raw(gid)
        insert_data(game_data.get("userGames"), col_game_data_raw)

    logger.info(f"[init] {len(game_ids)}개의 game data 처리 완료")

    _insert_user_checks(col_game_data_raw, col_user_checks)
    logger.info("[init] user_checks 초기화 완료")

    return version_str
