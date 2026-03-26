"""Fill characterCompare items for a user_report document (in-memory)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from common.db.access import raw_db
from common.models.report_models import (
    CharacterCompareDiff,
    CharacterCompareItem,
    CharacterCompareKey,
    CharacterSlice,
    TierCharacterWeaponStat,
    UserReportDoc,
)
from common.kr_mappings import tier_en_by_mmr_rank, tier_to_stat_mmr_range
from common.logger import setup_logger

logger = setup_logger("fill_report_compare")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_version_season(report: UserReportDoc) -> Optional[int]:
    if report.meta.versionSeason is not None:
        return report.meta.versionSeason
    default_season = os.environ.get("DEFAULT_VERSION_SEASON")
    if default_season:
        try:
            return int(default_season)
        except Exception:
            return None
    return None


def _build_db_name(version_season: int, major: int, minor: int) -> str:
    return f"er_game_data_v{version_season}_{major}_{minor}"


def _compute_diff(user: CharacterSlice, tier: TierCharacterWeaponStat) -> CharacterCompareDiff:
    def safe_div(n: int, d: int) -> Optional[float]:
        if d <= 0:
            return None
        return n / d

    user_pick = user.pickCount
    tier_pick = tier.pickCount

    user_win = safe_div(user.victory_count, user_pick)
    tier_win = safe_div(tier.victory_count, tier_pick)
    user_top3 = safe_div(user.top3_count, user_pick)
    tier_top3 = safe_div(tier.top3_count, tier_pick)
    user_avg_rank = safe_div(user.gameRank_sum, user_pick)
    tier_avg_rank = safe_div(tier.gameRank_sum, tier_pick)
    user_dmg = safe_div(user.damage_sum, user_pick)
    tier_dmg = safe_div(tier.damage_sum, tier_pick)
    user_tk = safe_div(user.tk_sum, user_pick)
    tier_tk = safe_div(tier.tk_sum, tier_pick)
    user_mmr_gain = safe_div(user.mmrGain_sum, user_pick)
    tier_mmr_gain = safe_div(tier.mmrGain_sum, tier_pick)

    def delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None:
            return None
        return round(a - b, 6)

    return CharacterCompareDiff(
        win_rate_delta=delta(user_win, tier_win),
        top3_rate_delta=delta(user_top3, tier_top3),
        avg_rank_delta=delta(user_avg_rank, tier_avg_rank),
        avg_damage_delta=delta(user_dmg, tier_dmg),
        avg_tk_delta=delta(user_tk, tier_tk),
        mmrGain_avg_delta=delta(user_mmr_gain, tier_mmr_gain),
    )


def _fetch_tier_stat(
    col_stats,
    *,
    version_season: int,
    version_major: int,
    version_minor: int,
    character_num: int,
    best_weapon: int,
    mmr_range: str,
) -> Optional[Dict[str, Any]]:
    return col_stats.find_one(
        {
            "versionSeason": version_season,
            "versionMajor": version_major,
            "versionMinor": version_minor,
            "characterNum": character_num,
            "bestWeapon": best_weapon,
            "mmrRange": mmr_range,
        }
    )

def fill_compare_for_report(
    report_doc: UserReportDoc,
    *,
    client,
) -> Tuple[UserReportDoc, Dict[str, Any]]:
    report = report_doc

    version_season = _resolve_version_season(report)
    if version_season is None:
        raise RuntimeError("versionSeason not resolved; set DEFAULT_VERSION_SEASON")

    version_major = report.meta.versionMajor
    version_minor = report.meta.versionMinor
    db_name = _build_db_name(version_season, version_major, version_minor)
    col_stats = raw_db(
        client,
        f"{version_season}.{version_major}.{version_minor}",
    )["character_statistics"]

    # seasonSummary에서 MMR/rank로 티어 판정 → mmrRange 결정
    user_mmr = report.seasonSummary.mmr
    user_rank = report.seasonSummary.rank
    user_tier = tier_en_by_mmr_rank(mmr=user_mmr, rank=user_rank)
    stat_mmr_range = tier_to_stat_mmr_range(user_tier)
    logger.info(
        "tier resolved: mmr=%s rank=%s tier=%s mmrRange=%s",
        user_mmr, user_rank, user_tier, stat_mmr_range,
    )

    compare_items: List[CharacterCompareItem] = []
    missing_count = 0
    filled_count = 0

    updated_slices: List[CharacterSlice] = []
    for slice_item in report.characterSlices.items:
        slice_item.versionSeason = version_season
        slice_item.versionMajor = version_major
        slice_item.versionMinor = version_minor
        updated_slices.append(slice_item)

        tier_doc = _fetch_tier_stat(
            col_stats,
            version_season=version_season,
            version_major=version_major,
            version_minor=version_minor,
            character_num=slice_item.characterNum,
            best_weapon=slice_item.bestWeapon,
            mmr_range=stat_mmr_range,
        )

        key = CharacterCompareKey(
            characterNum=slice_item.characterNum,
            bestWeapon=slice_item.bestWeapon,
            mmrRange=stat_mmr_range,
            versionSeason=version_season,
            versionMajor=version_major,
            versionMinor=version_minor,
        )

        if not tier_doc:
            compare_items.append(
                CharacterCompareItem(
                    key=key,
                    user=slice_item,
                    tierAvg=None,
                    diff=None,
                )
            )
            missing_count += 1
            continue

        tier = TierCharacterWeaponStat(
            pickCount=int(tier_doc.get("pickCount", 0)),
            mmrGain_sum=int(tier_doc.get("mmrGain_sum", 0)),
            gameRank_sum=int(tier_doc.get("gameRank_sum", 0)),
            top3_count=int(tier_doc.get("top3_count", 0)),
            victory_count=int(tier_doc.get("victory_count", 0)),
            damage_sum=int(tier_doc.get("damage_sum", 0)),
            tk_sum=int(tier_doc.get("tk_sum", 0)),
            characterNum=int(tier_doc.get("characterNum", slice_item.characterNum)),
            bestWeapon=int(tier_doc.get("bestWeapon", slice_item.bestWeapon)),
            mmrRange=tier_doc.get("mmrRange"),
            versionMajor=int(tier_doc.get("versionMajor", version_major)),
            versionMinor=int(tier_doc.get("versionMinor", version_minor)),
        )
        diff = _compute_diff(slice_item, tier)
        compare_items.append(
            CharacterCompareItem(
                key=key,
                user=slice_item,
                tierAvg=tier,
                diff=diff,
            )
        )
        filled_count += 1

    # Update in-memory doc
    report.meta.versionSeason = version_season
    report.characterSlices.items = updated_slices
    report.characterCompare.items = compare_items

    stats = {
        "slice_count": len(updated_slices),
        "filled_count": filled_count,
        "missing_count": missing_count,
        "db_name": db_name,
    }

    return report, stats
