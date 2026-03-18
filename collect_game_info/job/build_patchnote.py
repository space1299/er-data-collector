import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from job.diff.fallback import build_fallback_change
from job.diff.list_by_pk import diff_list_by_pk

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_patch_id(now: datetime) -> str:
    return now.isoformat()


def build_patchnote(
    *,
    db_info,
    db_view,
    changes: List[Dict[str, Any]],
    error_keys: Optional[List[str]] = None,
    run_id: Optional[str] = None,
    store_full_rows: bool = True,
) -> Optional[Dict[str, Any]]:
    if not changes:
        return None

    now = _utc_now()
    patch_id = _make_patch_id(now)

    change_docs: List[Dict[str, Any]] = []
    changed_keys: List[str] = []

    for item in changes:
        key = item.get("key")
        before = item.get("before")
        after = item.get("after")
        pk_fields = item.get("pk_fields")

        if isinstance(before, list) and isinstance(after, list) and pk_fields:
            diff = diff_list_by_pk(before, after, pk_fields)
        else:
            diff = build_fallback_change(before, after, store_full_rows=store_full_rows)
            pk_fields = None

        change_docs.append({
            "key": key,
            "pk_fields": pk_fields,
            "added": diff.get("added", []),
            "removed": diff.get("removed", []),
            "modified": diff.get("modified", []),
            "stats": diff.get("stats", {}),
            "snapshot_ref": item.get("snapshot_ref"),
        })
        changed_keys.append(key)

    doc = {
        "patch_id": patch_id,
        "detected_at": now,
        "version_guess": None,
        "changed_keys": changed_keys,
        "changes": change_docs,
        "run_id": run_id or patch_id,
        "error_keys": error_keys or [],
    }

    col_changes = db_info["changes"]
    col_view_changes = db_view["info_changes"]

    col_changes.insert_one(doc)

    # Keep view in sync with the latest 3 full patch docs.
    latest = list(col_changes.find().sort([("detected_at", -1)]).limit(3))
    col_view_changes.delete_many({})
    if latest:
        col_view_changes.insert_many(latest)

    logger.info(
        "patchnote saved: patch_id=%s changes=%d errors=%d",
        patch_id,
        len(change_docs),
        len(error_keys or []),
    )

    return doc
