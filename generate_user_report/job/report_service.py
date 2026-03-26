"""Pipeline for report_jobs -> user_reports (stage 1 only).

Builds normalized UserReportDoc without tier comparisons.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, List, Optional, Tuple

from common.er_api import get_user_game_data, get_user_id, get_user_stats
from common.logger import setup_logger
from common.models.er_api_models import UserGamesResponse, UserStatsResponse, BattleUserResult
from common.models.report_models import (
    ApiCharacterStat,
    CharacterCompareSection,
    CharacterSlice,
    CharacterSlicesSection,
    SeasonSummary,
    UserReportDoc,
    UserReportMeta,
)
from common.db.access import view_db
from .aggregate import (
    aggregate_character_slices,
    parse_start_dtm_utc,
    pick_representative_version,
)

logger = setup_logger("generate_user_report_service")


@dataclass(frozen=True)
class PaginationResult:
    games: List[BattleUserResult]
    cutoff_reason: Optional[str]
    next_game_id: Optional[int]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_report_version(job: Dict[str, Any]) -> str:
    if job.get("reportVersion"):
        return str(job.get("reportVersion"))
    dedupe_key = str(job.get("dedupe_key") or "")
    parts = dedupe_key.split("|")
    if len(parts) >= 4 and parts[-1]:
        return parts[-1]
    if len(parts) >= 3 and parts[-1]:
        return parts[-1]
    return "v1"


def _parse_season_id(job: Dict[str, Any]) -> Optional[int]:
    if job.get("seasonId") is not None:
        try:
            return int(job.get("seasonId"))
        except Exception:
            return None
    dedupe_key = str(job.get("dedupe_key") or "")
    parts = dedupe_key.split("|")
    if len(parts) >= 4:
        try:
            return int(parts[-3])
        except Exception:
            return None
    if len(parts) >= 3:
        try:
            return int(parts[-2])
        except Exception:
            return None
    return None


def _parse_matching_mode(job: Dict[str, Any], default_mode: int) -> int:
    if job.get("matchingMode") is not None:
        try:
            return int(job.get("matchingMode"))
        except Exception:
            return default_mode
    dedupe_key = str(job.get("dedupe_key") or "")
    parts = dedupe_key.split("|")
    if len(parts) >= 4:
        try:
            return int(parts[-2])
        except Exception:
            return default_mode
    return default_mode


def _build_dedupe_key(nickname: str, season_id: int, matching_mode: int, report_version: str) -> str:
    return f"{nickname.casefold()}|{season_id}|{matching_mode}|{report_version}"


def _extract_canonical_nickname(
    input_nickname: str,
    stats_resp: Optional[UserStatsResponse],
    recent_games: PaginationResult,
) -> str:
    """Return the authoritative-case nickname from API responses."""
    if stats_resp and stats_resp.userStats:
        nick = stats_resp.userStats[0].nickname
        if nick:
            return nick
    if recent_games.games:
        nick = recent_games.games[0].nickname
        if nick:
            return nick
    return input_nickname


def _parse_user_stats(user_id: int, season_id: int, matching_mode: int) -> Optional[UserStatsResponse]:
    raw = get_user_stats(user_id, season_id, matching_mode)
    if not isinstance(raw, dict):
        return None
    try:
        return UserStatsResponse.model_validate(raw)
    except Exception:
        return None


def _pick_user_stats_entry(
    resp: Optional[UserStatsResponse],
    season_id: int,
    matching_mode: int,
) -> Optional[Any]:
    if resp is None:
        return None
    entries = resp.userStats or []
    for entry in entries:
        if entry.seasonId == season_id and entry.matchingMode == matching_mode:
            return entry
    return entries[0] if entries else None


def _build_season_summary(
    resp: Optional[UserStatsResponse],
    season_id: int,
    matching_mode: int,
) -> SeasonSummary:
    entry = _pick_user_stats_entry(resp, season_id, matching_mode)
    if entry is None:
        return SeasonSummary()

    api_character_stats: Optional[List[ApiCharacterStat]] = None
    if entry.characterStats:
        api_character_stats = [
            ApiCharacterStat(
                characterCode=s.characterCode,
                totalGames=s.totalGames,
                wins=s.wins,
                top3Rate=s.top3Rate,
                averageRank=s.averageRank,
                maxKillings=s.maxKillings,
            )
            for s in entry.characterStats
        ]

    return SeasonSummary(
        mmr=entry.mmr,
        rank=entry.rank,
        rankSize=entry.rankSize,
        rankPercent=entry.rankPercent,
        totalGames=entry.totalGames,
        totalWins=entry.totalWins,
        averageRank=entry.averageRank,
        top1=entry.top1,
        top2=entry.top2,
        top3=entry.top3,
        top5=entry.top5,
        top7=entry.top7,
        apiCharacterStats=api_character_stats,
    )


def _parse_user_games_response(raw: Dict[str, Any]) -> Optional[UserGamesResponse]:
    try:
        return UserGamesResponse.model_validate(raw)
    except Exception:
        return None


def collect_recent_games_with_pagination(
    *,
    user_id: int,
    season_id: int,
    matching_mode: int,
    window_days: int,
    max_games: int,
) -> PaginationResult:
    games: List[BattleUserResult] = []
    next_game_id: Optional[int] = None
    cutoff_reason: Optional[str] = None
    cutoff_dt = _utc_now() - timedelta(days=window_days)

    while True:
        raw = get_user_game_data(user_id, next_game_id)
        if not isinstance(raw, dict):
            break

        resp = _parse_user_games_response(raw)
        if resp is None:
            break

        for game in resp.userGames:
            if game.matchingMode is not None:
                try:
                    if int(game.matchingMode) != int(matching_mode):
                        continue
                except Exception:
                    continue

            if game.seasonId is not None and game.seasonId != season_id:
                cutoff_reason = "season_mismatch_stop"
                return PaginationResult(games, cutoff_reason, resp.next)

            played_at = parse_start_dtm_utc(game.startDtm)
            if played_at is None:
                # If start time is missing, skip to avoid breaking window logic.
                continue

            if played_at < cutoff_dt:
                cutoff_reason = "window_days"
                return PaginationResult(games, cutoff_reason, resp.next)

            games.append(game)
            if len(games) >= max_games:
                cutoff_reason = "max_games"
                return PaginationResult(games, cutoff_reason, resp.next)

        next_game_id = resp.next
        if not next_game_id:
            break

    return PaginationResult(games, cutoff_reason, None)


def build_user_report_doc(
    *,
    job: Dict[str, Any],
    user_id: int,
    canonical_nickname: str,
    stats_resp: Optional[UserStatsResponse],
    recent_games: PaginationResult,
    representative_major: Optional[int],
    representative_minor: Optional[int],
    version_season: Optional[int],
    report_version: str,
    season_id: int,
    matching_mode: int,
    created_at: datetime,
    window_days: int,
    max_games: int,
) -> UserReportDoc:
    matching_team_mode: Optional[int] = None
    entry = _pick_user_stats_entry(stats_resp, season_id, matching_mode)
    if entry is not None:
        matching_team_mode = entry.matchingTeamMode
    if matching_team_mode is None:
        try:
            matching_team_mode = int(job.get("matchingTeamMode"))
        except Exception:
            matching_team_mode = None

    meta = UserReportMeta(
        reportVersion=report_version,
        nickname=canonical_nickname,
        userId=user_id,
        seasonId=season_id,
        versionSeason=version_season,
        matchingMode=matching_mode,
        matchingTeamMode=matching_team_mode,
        versionMajor=representative_major or 0,
        versionMinor=representative_minor or 0,
        createdAt=created_at,
        sourceWindowDays=window_days,
        recentGameCount=len(recent_games.games),
        cutoffReason=recent_games.cutoff_reason,
    )

    season_summary = _build_season_summary(stats_resp, season_id, matching_mode)

    rep_major, rep_minor = representative_major, representative_minor
    rep_games = [
        g for g in recent_games.games
        if g.versionMajor == rep_major and g.versionMinor == rep_minor
    ]

    slices = aggregate_character_slices(
        games=rep_games,
        version_season=version_season,
        representative_major=rep_major,
        representative_minor=rep_minor,
    )
    slices_section = CharacterSlicesSection(items=slices)

    compare_section = CharacterCompareSection(items=[])

    return UserReportDoc(
        meta=meta,
        seasonSummary=season_summary,
        characterSlices=slices_section,
        characterCompare=compare_section,
    )


def fetch_er_data(
    *,
    job: Dict[str, Any],
    default_matching_mode: int,
    window_days: int,
    max_games: int,
) -> Tuple[int, int, int, str, Optional[UserStatsResponse], PaginationResult, str]:
    nickname = str(job.get("nickname") or "").strip()
    if not nickname:
        raise ValueError("job missing nickname")

    report_version = _parse_report_version(job)
    season_id = _parse_season_id(job)
    if season_id is None:
        raise ValueError("job missing seasonId")

    matching_mode = _parse_matching_mode(job, default_matching_mode)

    user_id = get_user_id(nickname)
    if user_id is None:
        raise ValueError(f"failed to resolve user_id for nickname={nickname!r}")

    stats_resp = _parse_user_stats(user_id, season_id, matching_mode)

    recent_games = collect_recent_games_with_pagination(
        user_id=user_id,
        season_id=season_id,
        matching_mode=matching_mode,
        window_days=window_days,
        max_games=max_games,
    )
    if not recent_games.games:
        raise ValueError("no recent games found")

    canonical_nickname = _extract_canonical_nickname(nickname, stats_resp, recent_games)

    return user_id, season_id, matching_mode, report_version, stats_resp, recent_games, canonical_nickname


def build_report_payload(
    *,
    client,
    job: Dict[str, Any],
    canonical_nickname: str,
    stats_resp: Optional[UserStatsResponse],
    recent_games: PaginationResult,
    report_version: str,
    season_id: int,
    matching_mode: int,
    user_id: int,
    window_days: int,
    max_games: int,
) -> Tuple[UserReportDoc, str]:
    rep_major, rep_minor = pick_representative_version(recent_games.games)
    if rep_major is None or rep_minor is None:
        raise ValueError("representative version not found")

    version_season = resolve_version_season(client, season_id)
    if version_season is None:
        raise ValueError("versionSeason not resolved")

    doc = build_user_report_doc(
        job=job,
        user_id=user_id,
        canonical_nickname=canonical_nickname,
        stats_resp=stats_resp,
        recent_games=recent_games,
        representative_major=rep_major,
        representative_minor=rep_minor,
        version_season=version_season,
        report_version=report_version,
        season_id=season_id,
        matching_mode=matching_mode,
        created_at=_utc_now(),
        window_days=window_days,
        max_games=max_games,
    )

    dedupe_key = _build_dedupe_key(canonical_nickname, season_id, matching_mode, report_version)
    return doc, dedupe_key


def resolve_version_season(client, season_id: int) -> Optional[int]:
    # Prefer view.versions by season_id; fallback to env for now.
    try:
        col_versions = view_db(client)["versions"]
        doc = col_versions.find_one({"season_id": int(season_id)})
        if doc and doc.get("season") is not None:
            return int(doc.get("season"))
    except Exception:
        pass

    default_season = os.environ.get("DEFAULT_VERSION_SEASON")
    if default_season:
        try:
            return int(default_season)
        except Exception:
            return None

    return None
