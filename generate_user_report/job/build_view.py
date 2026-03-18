"""Build view-friendly user_report_views from in-memory UserReportDoc."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from common.logger import setup_logger
from common.kr_mappings import character_kr, weapon_kr
from common.models.report_models import UserReportDoc

logger = setup_logger("build_user_report_view")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _character_name(character_num: Optional[int]) -> Optional[str]:
    if character_num is None:
        return None
    return character_kr(character_num)


def _weapon_name(
    best_weapon: Optional[int],
) -> Optional[str]:
    if best_weapon is None:
        return None
    return weapon_kr(best_weapon)

def _character_weapon_name(character_num: Optional[int], weapon_name: Optional[str], char_name: Optional[str]) -> Optional[str]:
    if character_num == 27 and char_name:
        return char_name
    if not char_name or not weapon_name:
        return None
    return f"{weapon_name} {char_name}"


def _safe_div(n: float, d: int) -> float:
    if d <= 0:
        d = 1
    return n / d


def _build_character_slices(
    items: List[Any],
) -> Dict[str, Any]:
    out_items = []
    missing = 0
    for item in items:
        char_name = _character_name(item.characterNum)
        if char_name is None and item.characterNum is not None and item.characterNum != 27:
            logger.warning("l10n missing: Character/Name/%s", item.characterNum)
            missing += 1
        weapon_name = _weapon_name(item.bestWeapon)
        if weapon_name is None and item.bestWeapon is not None:
            logger.warning("weapon type l10n missing: %s", item.bestWeapon)
            missing += 1
        cw_name = _character_weapon_name(item.characterNum, weapon_name, char_name)
        pick = item.pickCount or 0
        out_items.append({
            "characterNum": item.characterNum,
            "bestWeapon": item.bestWeapon,
            "characterNameKo": char_name,
            "weaponNameKo": weapon_name,
            "characterWeaponNameKo": cw_name,
            "pickCount": pick,
            "mmrGain_sum": item.mmrGain_sum,
            "gameRank_sum": item.gameRank_sum,
            "top3_count": item.top3_count,
            "victory_count": item.victory_count,
            "damage_sum": item.damage_sum,
            "tk_sum": item.tk_sum,
            "avg_mmrGain": _safe_div(item.mmrGain_sum, pick),
            "avg_gameRank": _safe_div(item.gameRank_sum, pick),
            "top3_rate": _safe_div(item.top3_count, pick),
            "win_rate": _safe_div(item.victory_count, pick),
            "avg_damageToPlayer": _safe_div(item.damage_sum, pick),
            "avg_teamKill": _safe_div(item.tk_sum, pick),
            "versionSeason": item.versionSeason,
            "versionMajor": item.versionMajor,
            "versionMinor": item.versionMinor,
        })

    return {"items": out_items, "count": len(out_items), "l10n_missing": missing}


def _build_compare_items(
    items: List[Any],
) -> Dict[str, Any]:
    out_items = []
    missing = 0
    for item in items:
        key = item.key
        char_name = _character_name(key.characterNum)
        if char_name is None and key.characterNum is not None and key.characterNum != 27:
            logger.warning("l10n missing: Character/Name/%s", item.characterNum)
            missing += 1
        weapon_name = _weapon_name(key.bestWeapon)
        if weapon_name is None and key.bestWeapon is not None:
            logger.warning("weapon type l10n missing: %s", key.bestWeapon)
            missing += 1
        cw_name = _character_weapon_name(key.characterNum, weapon_name, char_name)

        def _with_rates(doc: Optional[Any]) -> Optional[Dict[str, Any]]:
            if doc is None:
                return None
            pick = doc.pickCount or 0
            return {
                "pickCount": pick,
                "mmrGain_sum": doc.mmrGain_sum,
                "gameRank_sum": doc.gameRank_sum,
                "top3_count": doc.top3_count,
                "victory_count": doc.victory_count,
                "damage_sum": doc.damage_sum,
                "tk_sum": doc.tk_sum,
                "avg_mmrGain": _safe_div(doc.mmrGain_sum, pick),
                "avg_gameRank": _safe_div(doc.gameRank_sum, pick),
                "top3_rate": _safe_div(doc.top3_count, pick),
                "win_rate": _safe_div(doc.victory_count, pick),
                "avg_damageToPlayer": _safe_div(doc.damage_sum, pick),
                "avg_teamKill": _safe_div(doc.tk_sum, pick),
            }

        out_items.append({
            "key": {
                "characterNum": key.characterNum,
                "bestWeapon": key.bestWeapon,
                "versionSeason": key.versionSeason,
                "versionMajor": key.versionMajor,
                "versionMinor": key.versionMinor,
                "characterNameKo": char_name,
                "weaponNameKo": weapon_name,
                "characterWeaponNameKo": cw_name,
            },
            "user": _with_rates(item.user),
            "tierAvg": _with_rates(item.tierAvg),
            "diff": item.diff.model_dump() if item.diff else None,
        })

    return {"items": out_items, "count": len(out_items), "l10n_missing": missing}

def _sanitize_view_doc(view_doc: Dict[str, Any]) -> Dict[str, Any]:
    # Stage-2 policy: final view doc must not expose legacy recentGames fields.
    for key in list(view_doc.keys()):
        if key == "recentGames" or key.startswith("recentGames"):
            view_doc.pop(key, None)

    meta = view_doc.get("meta")
    if isinstance(meta, dict):
        meta.pop("mmrRangePolicy", None)
    return view_doc


def write_error_view(
    dedupe_key: str,
    error_message: str,
    *,
    db_view,
) -> Dict[str, Any]:
    """Write an error document to user_report_views so the frontend can detect failures."""
    error_doc = {
        "_id": dedupe_key,
        "dedupe_key": dedupe_key,
        "error": {"message": error_message},
        "generatedAt": _utc_now_iso(),
    }
    col_view = db_view["user_report_views"]
    col_view.replace_one({"_id": dedupe_key}, error_doc, upsert=True)
    logger.info("error view written: dedupe_key=%s", dedupe_key)
    return error_doc


def build_user_report_view(
    report_doc: UserReportDoc,
    dedupe_key: str,
    *,
    db_view,
) -> Dict[str, Any]:
    report = report_doc
    character_slices = _build_character_slices(report.characterSlices.items)
    character_compare = _build_compare_items(report.characterCompare.items)

    season_summary = report.seasonSummary.model_dump()
    api_missing = 0
    if report.seasonSummary.apiCharacterStats:
        out_stats = []
        for s in report.seasonSummary.apiCharacterStats:
            name = _character_name(s.characterCode)
            if name is None:
                logger.warning("l10n missing: Character/Name/%s", s.characterCode)
                api_missing += 1
            out_stats.append({
                "characterCode": s.characterCode,
                "characterNameKo": name,
                "totalGames": s.totalGames,
                "wins": s.wins,
                "top3Rate": s.top3Rate,
                "averageRank": s.averageRank,
                "maxKillings": s.maxKillings,
            })
        season_summary["apiCharacterStats"] = out_stats

    view_doc = {
        "_id": dedupe_key,
        "dedupe_key": dedupe_key,
        "meta": report.meta.model_dump(),
        "seasonSummary": season_summary,
        "characterSlices": character_slices,
        "characterCompare": character_compare,
        "generatedAt": _utc_now_iso(),
    }
    view_doc = _sanitize_view_doc(view_doc)

    col_view = db_view["user_report_views"]
    col_view.replace_one({"_id": dedupe_key}, {**view_doc, "_id": dedupe_key}, upsert=True)

    l10n_missing = (
        character_slices["l10n_missing"]
        + character_compare["l10n_missing"]
        + api_missing
    )
    logger.info(
        "view built: dedupe_key=%s nickname=%s slices=%d compare=%d l10n_missing=%d",
        dedupe_key,
        report.meta.nickname,
        character_slices["count"],
        character_compare["count"],
        l10n_missing,
    )

    return view_doc
