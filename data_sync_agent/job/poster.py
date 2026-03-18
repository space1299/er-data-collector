import requests
from typing import List, Dict, Any
from common.logger import setup_logger

logger = setup_logger("sync_view:poster")

def upsert(api_base, api_key, collection: str, docs: List[Dict[str, Any]], timeout_sec = 10) -> None:
    if not api_base:
        raise RuntimeError("API_BASE is not configured")
    if not api_key:
        raise RuntimeError("INGEST_API_KEY is not configured")
    if not docs:
        return

    url = f"{api_base}/ingest/upsert"
    payload = {
        "collection": collection,
        "docs": [
            {
                "key": {"_id": d["_id"]},
                "doc": d,
            }
            for d in docs
            if "_id" in d
        ],
        "source": "sync_view_worker",
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }

    resp = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=timeout_sec,
    )

    if resp.status_code != 200:
        logger.error(
            f"[POST FAIL] collection={collection} "
            f"status={resp.status_code} body={resp.text}"
        )
        raise RuntimeError(f"POST failed: {resp.status_code}")

    logger.info(
        f"[POST OK] collection={collection} docs={len(payload['docs'])}"
    )
