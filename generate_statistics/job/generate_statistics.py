import re

from pymongo import MongoClient

from common.db.access import raw_db, view_db
from common.kr_mappings import character_kr, weapon_kr
from common.logger import setup_logger

logger = setup_logger("generate_statistics")


def parse_version(version_str: str) -> tuple[int, int, int]:
    s = (version_str or "").strip()
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", s)
    if not m:
        raise ValueError(f"unsupported version_str format (e.g. 9.4.0): {version_str!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


# raw.game_data_raw -> raw.character_statistics (current version only)
def aggregate_character_stats(raw_ns, season:int , major: int, minor: int) -> int:
    col_raw = raw_ns["game_data_raw"]
    col_out = raw_ns["character_statistics"]

    match_stage = {
        "matchingMode": 3,
        "matchingTeamMode": 3,
        "versionSeason": season,
        "versionMajor": major,
        "versionMinor": minor,
    }

    pipeline = [
        {"$match": match_stage},
        {"$project": {
            "characterNum": 1, "bestWeapon": 1, "mmrAvg": 1,
            "mmrGain": {"$ifNull": ["$mmrGain", 0]},
            "gameRank": {"$ifNull": ["$gameRank", 0]},
            "victory": {"$ifNull": ["$victory", 0]},
            "damageToPlayer": {"$ifNull": ["$damageToPlayer", 0]},
            "teamKill": {"$ifNull": ["$teamKill", 0]},
        }},
        {"$addFields": {
            "mmrRange": {
                "$switch": {
                    "branches": [
                        {"case": {"$lt": ["$mmrAvg", 3600]}, "then": "Gold"},
                        {"case": {"$lt": ["$mmrAvg", 5000]}, "then": "Platinum"},
                        {"case": {"$lt": ["$mmrAvg", 6400]}, "then": "Diamond"},
                        {"case": {"$lt": ["$mmrAvg", 7200]}, "then": "Meteor"},
                    ],
                    "default": "MythrilPlus"
                }
            }
        }},
        {"$group": {
            "_id": {"characterNum": "$characterNum", "bestWeapon": "$bestWeapon", "mmrRange": "$mmrRange"},
            "pickCount": {"$sum": 1},
            "mmrGain_sum": {"$sum": "$mmrGain"},
            "gameRank_sum": {"$sum": "$gameRank"},
            "top3_count": {"$sum": {"$cond": [{"$lte": ["$gameRank", 3]}, 1, 0]}},
            "victory_count": {"$sum": "$victory"},
            "damage_sum": {"$sum": "$damageToPlayer"},
            "tk_sum": {"$sum": "$teamKill"},
        }},
        {"$project": {
            "_id": 0,
            "characterNum": "$_id.characterNum",
            "bestWeapon": "$_id.bestWeapon",
            "mmrRange": "$_id.mmrRange",
            "pickCount": 1, "mmrGain_sum": 1, "gameRank_sum": 1,
            "top3_count": 1, "victory_count": 1, "damage_sum": 1, "tk_sum": 1,
        }},
    ]

    logger.info("[aggregate] start")
    docs = list(col_raw.aggregate(pipeline, allowDiskUse=True))
    logger.info(f"[aggregate] aggregated {len(docs)} docs")

    col_out.delete_many({"versionSeason": season, "versionMajor": major, "versionMinor": minor})
    if docs:
        for d in docs:
            d["versionSeason"] = season
            d["versionMajor"] = major
            d["versionMinor"] = minor
        col_out.insert_many(docs)

    return len(docs)


# raw.character_statistics -> view.character_statistics (current version only)
def build_frontend_stats(raw_ns, view_ns, version_str: str, season: int, major: int, minor: int) -> int:
    from collections import defaultdict

    col_src = raw_ns["character_statistics"]
    col_dst = view_ns["character_statistics"]

    weapon_agnostic_characters = {27}  # weapon-agnostic characters
    raw_docs = list(col_src.find({"versionSeason": season, "versionMajor": major, "versionMinor": minor}))
    logger.info(f"[frontend] raw stats loaded: {len(raw_docs)} docs (v={major}.{minor})")

    grouped = defaultdict(list)
    total_pick_by_mmr = defaultdict(int)

    for d in raw_docs:
        mmr = d["mmrRange"]
        grouped[mmr].append(d)
        total_pick_by_mmr[mmr] += d.get("pickCount", 0)

    plus_defs = {
        "PlatinumPlus": ["Platinum", "Diamond", "Meteor", "MythrilPlus"],
        "DiamondPlus": ["Diamond", "Meteor", "MythrilPlus"],
        "MeteorPlus": ["Meteor", "MythrilPlus"],
        "MythrilPlus": ["MythrilPlus"],
    }
    for plus_key, bases in plus_defs.items():
        combined_docs = []
        for base_mmr in bases:
            combined_docs.extend(grouped.get(base_mmr, []))
            total_pick_by_mmr[plus_key] += total_pick_by_mmr.get(base_mmr, 0)

        grouped[plus_key] = combined_docs

    result_docs = []
    for mmrRange, entries in grouped.items():
        total_pick = max(total_pick_by_mmr[mmrRange], 1)

        merged = {}
        for e in entries:
            pc = e.get("pickCount", 0)
            if pc == 0:
                continue

            c = e["characterNum"]
            w = e["bestWeapon"]
            key = (c, None if c in weapon_agnostic_characters else w)

            m = merged.setdefault(key, {
                "characterNum": c,
                "bestWeapon": w,
                "mmrGain_sum": 0,
                "gameRank_sum": 0,
                "top3_count": 0,
                "victory_count": 0,
                "damage_sum": 0,
                "tk_sum": 0,
                "pickCount": 0
            })

            m["mmrGain_sum"] += e["mmrGain_sum"]
            m["gameRank_sum"] += e["gameRank_sum"]
            m["top3_count"] += e["top3_count"]
            m["victory_count"] += e["victory_count"]
            m["damage_sum"] += e["damage_sum"]
            m["tk_sum"] += e["tk_sum"]
            m["pickCount"] += pc

        formatted = []
        for (_c, _w), data in merged.items():
            pc = max(data["pickCount"], 1)
            c = data["characterNum"]
            w = data["bestWeapon"]
            if c in weapon_agnostic_characters:
                char_name = character_kr(c)
                if not char_name:
                    logger.warning(f"[frontend] missing character name: {c}")
                    continue
                full_name = char_name
            else:
                char_name = character_kr(c)
                if not char_name:
                    logger.warning(f"[frontend] missing character name: {c}")
                    continue

                weapon_name = weapon_kr(w)
                if not weapon_name:
                    logger.warning(f"[frontend] missing weapon name: {w}")
                    continue
                full_name = f"{weapon_name} {char_name}"
            formatted.append({
                "characterName_inkorean": full_name,
                "avg_mmrGain": round(data["mmrGain_sum"] / pc, 2),
                "avg_gameRank": round(data["gameRank_sum"] / pc, 2),
                "top3_rate": round(data["top3_count"] / pc, 4),
                "win_rate": round(data["victory_count"] / pc, 4),
                "avg_damageToPlayer": round(data["damage_sum"] / pc, 2),
                "avg_teamKill": round(data["tk_sum"] / pc, 2),
                "pickrate": round(data["pickCount"] / total_pick, 4),
                "pickCount": data["pickCount"],
            })

        result_docs.append({
            "versionStr": version_str,
            "versionMajor": major,
            "versionMinor": minor,
            "mmrRange": mmrRange,
            "data": formatted,
        })

    col_dst.delete_many({"versionMajor": major, "versionMinor": minor})
    if result_docs:
        col_dst.insert_many(result_docs)

    logger.info(f"[frontend] stats built: {len(result_docs)} mmrRange (v={major}.{minor})")
    return len(result_docs)


def generate_statistics_once(client: MongoClient, version_str: str):
    season, major, minor = parse_version(version_str)

    logger.info(f"[once] version_str={version_str!r} -> season={season}, major={major}, minor={minor}")

    raw_ns = raw_db(client, version_str)
    view_ns = view_db(client)

    n1 = aggregate_character_stats(raw_ns, season, major, minor)
    logger.info(f"[once] raw stats updated: {n1} docs")

    n2 = build_frontend_stats(raw_ns, view_ns, version_str, season, major, minor)
    logger.info(f"[once] view stats updated: {n2} mmrRange")





