from typing import Any, Dict, List

from pymongo import UpdateOne

from common.logger import setup_logger

logger = setup_logger("sync_view:upserter")


def _build_upsert(filter_doc: Dict[str, Any], doc: Dict[str, Any]) -> UpdateOne:
    return UpdateOne(filter_doc, {"$set": doc}, upsert=True)


def upsert_batch(out_db, collection: str, docs: List[Dict[str, Any]], source: str) -> Dict[str, int]:
    if not docs:
        return {"received": 0, "upserted": 0, "modified": 0, "matched": 0}

    ops: List[UpdateOne] = []
    for doc in docs:
        doc_to_set = dict(doc)
        if "_id" in doc_to_set:
            del doc_to_set["_id"]

        if collection == "character_statistics":
            version_str = doc_to_set.get("versionStr")
            mmr_range = doc_to_set.get("mmrRange")
            if version_str is None or mmr_range is None:
                continue
            upsert_filter = {"versionStr": version_str, "mmrRange": mmr_range}
            ops.append(_build_upsert(upsert_filter, doc_to_set))
            continue
        if collection == "versions":
            version_str = doc_to_set.get("version_str")
            if version_str is None:
                continue
            upsert_filter = {"version_str": version_str}
            ops.append(_build_upsert(upsert_filter, doc_to_set))
            continue

        doc_id = doc.get("_id")
        if doc_id is None:
            continue
        upsert_filter = {"_id": doc_id}
        ops.append(_build_upsert(upsert_filter, doc_to_set))

    if not ops:
        return {"received": len(docs), "upserted": 0, "modified": 0, "matched": 0}

    col = out_db[collection]
    try:
        result = col.bulk_write(ops, ordered=False)
    except Exception as e:
        logger.exception("bulk_write failed: collection=%s err=%s", collection, e)
        raise

    return {
        "received": len(docs),
        "upserted": int(result.upserted_count or 0),
        "modified": int(result.modified_count or 0),
        "matched": int(result.matched_count or 0),
    }
