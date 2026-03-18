from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from common.models.er_api_models import BattleUserResult
from common.models.report_models import CharacterSlice


def parse_start_dtm_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def pick_representative_version(
    games: Iterable[BattleUserResult],
) -> Tuple[Optional[int], Optional[int]]:
    counts: Dict[Tuple[int, int], int] = {}
    for g in games:
        if g.versionMajor is None or g.versionMinor is None:
            continue
        key = (g.versionMajor, g.versionMinor)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None, None
    rep = max(counts.items(), key=lambda kv: (kv[1], kv[0][0], kv[0][1]))[0]
    return rep[0], rep[1]


def aggregate_character_slices(
    *,
    games: Iterable[BattleUserResult],
    version_season: Optional[int],
    representative_major: Optional[int],
    representative_minor: Optional[int],
) -> List[CharacterSlice]:
    buckets: Dict[Tuple[int, int], Dict[str, float]] = defaultdict(
        lambda: {
            "pickCount": 0,
            "mmrGain_sum": 0,
            "gameRank_sum": 0,
            "top3_count": 0,
            "victory_count": 0,
            "damage_sum": 0,
            "tk_sum": 0,
        }
    )

    for g in games:
        if representative_major is not None and g.versionMajor != representative_major:
            continue
        if representative_minor is not None and g.versionMinor != representative_minor:
            continue

        if g.characterNum is None or g.bestWeapon is None:
            continue

        key = (g.characterNum, g.bestWeapon)
        bucket = buckets[key]
        bucket["pickCount"] += 1
        bucket["mmrGain_sum"] += int(g.mmrGain or 0)
        bucket["gameRank_sum"] += int(g.gameRank or 0)
        if g.gameRank is not None and g.gameRank <= 3:
            bucket["top3_count"] += 1
        if g.victory == 1 or (g.victory is None and g.gameRank == 1):
            bucket["victory_count"] += 1
        bucket["damage_sum"] += int(g.damageToPlayer or 0)
        bucket["tk_sum"] += int(g.teamKill or 0)

    slices: List[CharacterSlice] = []
    for (char_num, best_weapon), agg in buckets.items():
        slices.append(
            CharacterSlice(
                characterNum=char_num,
                bestWeapon=best_weapon,
                versionSeason=version_season,
                versionMajor=representative_major,
                versionMinor=representative_minor,
                pickCount=int(agg["pickCount"]),
                mmrGain_sum=int(agg["mmrGain_sum"]),
                gameRank_sum=int(agg["gameRank_sum"]),
                top3_count=int(agg["top3_count"]),
                victory_count=int(agg["victory_count"]),
                damage_sum=int(agg["damage_sum"]),
                tk_sum=int(agg["tk_sum"]),
            )
        )

    return slices
