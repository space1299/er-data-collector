import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return value


def _values_equal(a: Any, b: Any) -> bool:
    return _normalize_value(a) == _normalize_value(b)


def _pk_tuple(row: Dict[str, Any], pk_fields: List[str]) -> Tuple[Any, ...]:
    return tuple(row.get(field) for field in pk_fields)


def _pk_dict(pk_fields: List[str], pk: Tuple[Any, ...]) -> Dict[str, Any]:
    return {field: pk[idx] for idx, field in enumerate(pk_fields)}


def _build_map(
    rows: List[Dict[str, Any]],
    pk_fields: List[str],
    *,
    label: str,
) -> Dict[Tuple[Any, ...], Dict[str, Any]]:
    mapped: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pk = _pk_tuple(row, pk_fields)
        if pk in mapped:
            logger.warning("duplicate pk in %s, last wins: %s", label, pk)
        mapped[pk] = row
    return mapped


def diff_list_by_pk(
    before_list: List[Dict[str, Any]],
    after_list: List[Dict[str, Any]],
    pk_fields: List[str],
) -> Dict[str, Any]:
    """
    Example (BulletCapacity):
      before = [{"itemCode": 101, "capacity": 30}]
      after  = [{"itemCode": 101, "capacity": 40}, {"itemCode": 102, "capacity": 20}]
      pk_fields = ["itemCode"]
    """
    before_map = _build_map(before_list, pk_fields, label="before")
    after_map = _build_map(after_list, pk_fields, label="after")

    before_keys = set(before_map.keys())
    after_keys = set(after_map.keys())

    added_keys = sorted(list(after_keys - before_keys))
    removed_keys = sorted(list(before_keys - after_keys))
    common_keys = sorted(list(before_keys & after_keys))

    added = [
        {"pk": _pk_dict(pk_fields, pk), "after": after_map[pk]}
        for pk in added_keys
    ]
    removed = [
        {"pk": _pk_dict(pk_fields, pk), "before": before_map[pk]}
        for pk in removed_keys
    ]

    modified: List[Dict[str, Any]] = []
    for pk in common_keys:
        before_row = before_map[pk]
        after_row = after_map[pk]
        fields: Dict[str, Dict[str, Any]] = {}

        # Missing keys are treated as None.
        all_fields = set(before_row.keys()) | set(after_row.keys())
        for field in all_fields:
            before_val = before_row.get(field)
            after_val = after_row.get(field)
            if not _values_equal(before_val, after_val):
                fields[field] = {"before": before_val, "after": after_val}

        if fields:
            modified.append({
                "pk": _pk_dict(pk_fields, pk),
                "fields": fields,
                "before": before_row,
                "after": after_row,
            })

    stats = {
        "added": len(added),
        "removed": len(removed),
        "modified": len(modified),
    }

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "stats": stats,
    }
