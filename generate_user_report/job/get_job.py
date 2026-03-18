from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pymongo import ReturnDocument

from common.logger import setup_logger

logger = setup_logger("generate_user_report_job_repo")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_job_indexes(report_db) -> None:
    col_jobs = report_db["report_jobs"]
    col_jobs.create_index("dedupe_key", unique=True, name="uq_dedupe_key")
    col_jobs.create_index([("status", 1), ("updatedAt", 1)], name="idx_status_updated")
    col_jobs.create_index("expiresAt", expireAfterSeconds=0, name="ttl_expiresAt")


def claim_next_job(
    report_db, worker_id: str, lease_sec: int, max_retry: int = 3,
) -> Optional[Dict[str, Any]]:
    col_jobs = report_db["report_jobs"]
    now = _utc_now()
    lease_cutoff = now - timedelta(seconds=lease_sec)

    # --- Phase 1: queued 또는 lease 만료된 running 잡 우선 처리 ---
    queued_query = {
        "status": {"$in": ["queued", "running"]},
        "$and": [
            {
                "$or": [
                    {"lockedAt": None},
                    {"lockedAt": {"$lte": lease_cutoff}},
                ]
            },
            {
                "$or": [
                    {"expiresAt": {"$exists": False}},
                    {"expiresAt": None},
                    {"expiresAt": {"$lte": now}},
                ]
            },
        ],
    }

    result = col_jobs.find_one_and_update(
        queued_query,
        {
            "$set": {
                "status": "running",
                "lockedAt": now,
                "lockedBy": worker_id,
                "updatedAt": now,
            }
        },
        sort=[("updatedAt", 1)],
        return_document=ReturnDocument.AFTER,
    )
    if result:
        return result

    # --- Phase 2: error 잡 재시도 (attempts < max_retry) ---
    # attempts 필드가 없는 기존 문서도 재시도 대상에 포함한다.
    error_query = {
        "status": "error",
        "$or": [
            {"attempts": {"$exists": False}},
            {"attempts": {"$lt": max_retry}},
        ],
    }

    return col_jobs.find_one_and_update(
        error_query,
        {
            "$set": {
                "status": "running",
                "lockedAt": now,
                "lockedBy": worker_id,
                "updatedAt": now,
            },
            # error → running 전환 시에만 attempts 증가 (재시도 횟수 추적)
            "$inc": {"attempts": 1},
        },
        sort=[("updatedAt", 1)],
        return_document=ReturnDocument.AFTER,
    )


def complete_job(report_db, job_id, result_ref: Optional[str], ttl_hours: int = 24) -> None:
    col_jobs = report_db["report_jobs"]
    now = _utc_now()
    col_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "done",
                "result_ref": result_ref,
                "updatedAt": now,
                "expiresAt": now + timedelta(hours=ttl_hours),
                "lockedAt": None,
                "lockedBy": None,
            }
        },
    )


def fail_job(
    report_db, job_id, message: str, detail: Optional[str] = None,
    ttl_hours: int = 24,
) -> None:
    col_jobs = report_db["report_jobs"]
    now = _utc_now()
    error_doc = {"message": message}
    if detail:
        error_doc["detail"] = detail
    # expiresAt을 설정하여 TTL 인덱스로 자동 정리되도록 한다.
    # complete_job과 동일한 TTL 정책(기본 24h)을 적용한다.
    col_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "error",
                "error": error_doc,
                "updatedAt": now,
                "expiresAt": now + timedelta(hours=ttl_hours),
                "lockedAt": None,
                "lockedBy": None,
            }
        },
    )
