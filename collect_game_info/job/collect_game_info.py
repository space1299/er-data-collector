import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pymongo import MongoClient

from common.db.access import info_db, view_db
from common.er_api import get_game_info
from common.logger import setup_logger
from job.build_patchnote import build_patchnote
from job.diff.registry import PK_FIELDS_BY_KEY

logger = setup_logger("collect_game_info")

ID_FIELD_BY_KEY = {
    "ActionCost": "code",
    "Area": "code",
    "BattleZoneReward": "code",
    "BulletCapacity": "code",
    "Character": "code",
    "CharacterAttributes": "code",
    "CharacterExp": "code",
    "CharacterLevelUpStat": "code",
    "CharacterMastery": "code",
    "CharacterModeModifier": "code",
    "CharacterSkin": "code",
    "Collectible": "code",
    "DropGroup": "code",
    "GainExp": "code",
    "GainScore": "code",
    "GameTip": "code",
    "InfusionProduct": "code",
    "ItemArmor": "code",
    "ItemConsumable": "code",
    "ItemMisc": "code",
    "ItemSearchOptionV2": "code",
    "ItemSpawn": "code",
    "ItemSpecial": "code",
    "ItemWeapon": "code",
    "Level": "code",
    "LoadingTip": "code",
    "MasteryExp": "code",
    "MasteryLevel": "code",
    "MasteryStat": "code",
    "Monster": "code",
    "MonsterDropGroup": "code",
    "MonsterLevelUpStat": "code",
    "MonsterSpawnLevel": "code",
    "NaviCollectAndHunt": "code",
    "NearByArea": "code",
    "RandomEquipment": "code",
    "RecommendedList": "code",
    "Season": "code",
    "SummonObjectStat": "code",
    "TacticalSkillSet": "code",
    "TacticalSkillSetGroup": "code",
    "Trait": "code",
    "VFCredit": "code",
    "WeaponTypeInfo": "code",
}

CANDIDATE_ID_KEYS = (
    "code", "id", "key",
    "characterCode", "itemCode", "monsterCode", "areaCode",
    "groupCode", "groupId",
    "seasonId", "seasonID",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_for_hash(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: normalize_for_hash(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [normalize_for_hash(x) for x in obj]
    return obj


def calc_hash(data: Any) -> str:
    norm = normalize_for_hash(data)
    s = json.dumps(norm, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def guess_id_field(data: Any) -> Optional[str]:
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    sample = data[0]
    for k in CANDIDATE_ID_KEYS:
        if k in sample:
            return k
    return None


def diff_data(key: str, old: Any, new: Any) -> Dict[str, Any]:
    if old is None:
        return {"type": "initial", "summary": "initial insert"}

    if isinstance(old, dict) and isinstance(new, dict):
        old_keys = set(old.keys())
        new_keys = set(new.keys())
        added = sorted(list(new_keys - old_keys))
        removed = sorted(list(old_keys - new_keys))
        changed = sorted([k for k in (old_keys & new_keys) if old.get(k) != new.get(k)])
        return {"type": "dict", "added_keys": added, "removed_keys": removed, "changed_keys": changed,
                "summary": f"+{len(added)} -{len(removed)} ~{len(changed)}"}

    if isinstance(old, list) and isinstance(new, list):
        id_field = ID_FIELD_BY_KEY.get(key) or guess_id_field(new) or guess_id_field(old)
        if id_field and all(isinstance(x, dict) and id_field in x for x in old) and all(
            isinstance(x, dict) and id_field in x for x in new
        ):
            old_map = {x[id_field]: x for x in old}
            new_map = {x[id_field]: x for x in new}
            old_ids = set(old_map.keys())
            new_ids = set(new_map.keys())
            added = sorted(list(new_ids - old_ids))
            removed = sorted(list(old_ids - new_ids))
            updated = sorted([i for i in (old_ids & new_ids) if old_map[i] != new_map[i]])
            return {"type": "list_by_id", "id_field": id_field,
                    "added_ids": added, "removed_ids": removed, "updated_ids": updated,
                    "summary": f"+{len(added)} -{len(removed)} ~{len(updated)}"}

        return {"type": "list", "old_len": len(old), "new_len": len(new), "summary": f"len {len(old)} -> {len(new)}"}

    same = (old == new)
    return {"type": "value", "same": same, "old_type": type(old).__name__, "new_type": type(new).__name__,
            "summary": "same" if same else "changed"}


def sync_game_info_once(client: MongoClient) -> List[Dict[str, Any]]:
    hash_data = fetch_hash_map(client)
    if not hash_data:
        return []
    keys = list(hash_data.keys())
    changed_docs, _failed = sync_game_info_keys(client, keys, hash_data)
    return changed_docs

def _update_hash_map_doc(col_current, hash_data: Dict[str, Any], now: datetime) -> None:
    col_current.replace_one(
        {"_id": "hash_map"},
        {"_id": "hash_map", "key": "hash_map", "fetchedAt": now, "changedAt": now, "data": hash_data},
        upsert=True,
    )


def fetch_hash_map(client: MongoClient) -> Optional[Dict[str, Any]]:
    now = utc_now()
    col_current = info_db(client)["current"]

    hash_resp = get_game_info("hash")
    if hash_resp.get("code") != 200:
        logger.warning(f"hash ?办澊??攵堧煬?り赴 ?ろ尐: code={hash_resp.get('code')} message={hash_resp.get('message')}")
        return None

    hash_data = hash_resp.get("data")
    if not isinstance(hash_data, dict) or not hash_data:
        logger.info("hash ?办澊?瓣? 牍勳柎?堦卑??None?呺媹?? ?ろ偟")
        return None

    _update_hash_map_doc(col_current, hash_data, now)
    return hash_data


def find_changed_hash_keys(
    old_hash_map: Optional[Dict[str, Any]],
    new_hash_map: Dict[str, Any],
) -> List[str]:
    if not old_hash_map:
        return []
    return [
        key for key, api_hash in new_hash_map.items()
        if old_hash_map.get(key) != api_hash
    ]


def sync_game_info_keys(
    client: MongoClient,
    keys: List[str],
    hash_map: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    now = utc_now()

    col_current = info_db(client)["current"]
    col_snapshots = info_db(client)["snapshots"]

    changed_docs: List[Dict[str, Any]] = []
    failed_keys: List[str] = []
    change_items: List[Dict[str, Any]] = []

    for key in keys:
        logger.info(f"{key}: start")

        cur_doc = col_current.find_one({"_id": key})
        old_api_hash = cur_doc.get("apiHash") if cur_doc else None
        old_calc_hash = cur_doc.get("calcHash") if cur_doc else None
        old_data = cur_doc.get("data") if cur_doc else None

        api_hash = hash_map.get(key) if hash_map else None

        raw_resp = get_game_info(key)
        if raw_resp.get("code") != 200:
            logger.warning(f"{key} ?办澊??攵堧煬?り赴 ?ろ尐: code={raw_resp.get('code')} message={raw_resp.get('message')}")
            failed_keys.append(key)
            continue

        new_data = raw_resp.get("data")
        if not isinstance(new_data, (list, dict)):
            logger.warning(f"?????嗠姅 ?办澊???€?? {key}, ?€???ろ偟")
            failed_keys.append(key)
            continue

        new_calc_hash = calc_hash(new_data)

        is_new = cur_doc is None
        api_changed = (api_hash is not None and old_api_hash is not None and old_api_hash != api_hash)
        calc_changed = (old_calc_hash is not None and old_calc_hash != new_calc_hash)
        changed = is_new or api_changed or calc_changed

        if not changed:
            col_current.update_one({"_id": key}, {"$set": {"fetchedAt": now}}, upsert=True)
            logger.info(
                f"{key}: PASS apiHash=same calcHash=same (fetchedAt updated)"
            )
            continue

        diff = diff_data(key, old_data, new_data)

        logger.info(
            f"{key}: UPDATED "
            f"reason={'NEW' if is_new else 'API_HASH' if api_changed else 'CALC_HASH'} "
            f"summary={diff.get('summary', '')}"
        )

        before_snapshot_id = None
        if old_data is not None:
            before_res = col_snapshots.insert_one({
                "key": key, "kind": "before",
                "apiHash": old_api_hash, "calcHash": old_calc_hash,
                "fetchedAt": cur_doc.get("fetchedAt") if cur_doc else None,
                "savedAt": now, "data": old_data,
            })
            before_snapshot_id = before_res.inserted_id

        after_res = col_snapshots.insert_one({
            "key": key, "kind": "after",
            "apiHash": api_hash, "calcHash": new_calc_hash,
            "fetchedAt": now, "savedAt": now, "data": new_data,
        })
        after_snapshot_id = after_res.inserted_id

        col_current.replace_one(
            {"_id": key},
            {
                "_id": key, "key": key,
                "apiHash": api_hash, "calcHash": new_calc_hash,
                "fetchedAt": now, "changedAt": now,
                "data": new_data,
            },
            upsert=True,
        )

        change_doc = {
            "type": "game_info",
            "key": key,
            "detectedAt": now,
            "oldApiHash": old_api_hash,
            "newApiHash": api_hash,
            "oldCalcHash": old_calc_hash,
            "newCalcHash": new_calc_hash,
            "diff": diff,
        }
        changed_docs.append(change_doc)

        change_items.append({
            "key": key,
            "pk_fields": PK_FIELDS_BY_KEY.get(key),
            "before": old_data,
            "after": new_data,
            "snapshot_ref": after_snapshot_id,
            "before_snapshot_ref": before_snapshot_id,
        })

    if change_items:
        build_patchnote(
            db_info=info_db(client),
            db_view=view_db(client),
            changes=change_items,
            error_keys=failed_keys,
        )

    return changed_docs, failed_keys
