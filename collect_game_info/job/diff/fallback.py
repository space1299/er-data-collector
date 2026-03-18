from typing import Any, Dict, List


def build_fallback_change(
    before: Any,
    after: Any,
    *,
    store_full_rows: bool = True,
) -> Dict[str, Any]:
    if isinstance(before, dict) or isinstance(after, dict):
        before_dict = before if isinstance(before, dict) else {}
        after_dict = after if isinstance(after, dict) else {}
        all_fields = set(before_dict.keys()) | set(after_dict.keys())
        fields: Dict[str, Dict[str, Any]] = {}
        for field in all_fields:
            before_val = before_dict.get(field)
            after_val = after_dict.get(field)
            if before_val != after_val:
                fields[field] = {"before": before_val, "after": after_val}

        modified = []
        if fields:
            entry = {"pk": {}, "fields": fields}
            if store_full_rows:
                entry["before"] = before if isinstance(before, dict) else {}
                entry["after"] = after if isinstance(after, dict) else {}
            modified.append(entry)

        return {
            "added": [],
            "removed": [],
            "modified": modified,
            "stats": {"added": 0, "removed": 0, "modified": len(modified)},
        }

    if isinstance(before, list) or isinstance(after, list):
        before_len = len(before) if isinstance(before, list) else 0
        after_len = len(after) if isinstance(after, list) else 0
        return {
            "added": [],
            "removed": [],
            "modified": [{
                "pk": {},
                "fields": {"list_len": {"before": before_len, "after": after_len}},
            }],
            "stats": {"added": 0, "removed": 0, "modified": 1},
        }

    return {
        "added": [],
        "removed": [],
        "modified": [{
            "pk": {},
            "fields": {"value": {"before": before, "after": after}},
        }],
        "stats": {"added": 0, "removed": 0, "modified": 1},
    }
