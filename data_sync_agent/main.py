import time

from pymongo import MongoClient

from common.db.access import view_db
from common.db.client import get_client
from common.db.init import ensure_indexes
from common.db.schema import VIEW_COLLECTIONS, DB_NAMES
from common.logger import setup_logger

from job.mongo_exporter import export_batches
from job.mongo_upserter import upsert_batch
from config import (
    DB_URL,
    OUT_DB_URL,
    OUT_DB_NAMES,
    SYNC_ALLOWED_COLLECTIONS,
)

logger = setup_logger("sync_view:main")
SYNC_INTERVAL_SEC = 60

def _parse_out_db_names(value: str):
    return [x.strip() for x in (value or "").split(",") if x.strip()]

def list_collections(client):
    db = view_db(client)
    allowed = set(VIEW_COLLECTIONS) & set(SYNC_ALLOWED_COLLECTIONS)
    return [
        name for name in db.list_collection_names()
        if name in allowed and not name.startswith("system.")
    ]

def main_loop():
    logger.info("[START] sync_view worker")

    if not OUT_DB_URL:
        raise RuntimeError("OUT_DB_URL is not configured")

    out_db_names = _parse_out_db_names(OUT_DB_NAMES)
    if not out_db_names:
        raise RuntimeError("OUT_DB_NAMES is not configured")

    expected_view_name = DB_NAMES["view"]
    if any(name != expected_view_name for name in out_db_names):
        logger.warning("[WARN] non-view db names ignored: %s", out_db_names)
        out_db_names = [expected_view_name]

    client = None
    out_client = None

    try:
        while True:
            if client is None or out_client is None:
                try:
                    client = get_client(db_url=DB_URL)
                    ensure_indexes(client)
                    out_client = MongoClient(OUT_DB_URL)
                    ensure_indexes(out_client)
                except Exception as e:
                    logger.exception("[START] DB 연결 실패: %s", e)
                    time.sleep(5)
                    continue

            targets = []
            if expected_view_name in out_db_names:
                targets.append((expected_view_name, view_db(client), list_collections(client)))

            if not targets:
                raise RuntimeError("OUT_DB_NAMES has no supported db names")

            for name, _ns, cols in targets:
                logger.info("[INFO] collections[%s]=%s", name, cols)

            cycle_start = time.time()

            for db_name, ns, col_names in targets:
                out_db = view_db(out_client)
                for col_name in col_names:
                    logger.info("[SYNC] db=%s collection=%s start", db_name, col_name)

                    try:
                        sent_batches = 0
                        sent_docs = 0
                        upserted_total = 0
                        modified_total = 0
                        matched_total = 0

                        for batch_docs in export_batches(ns, col_name):
                            result = upsert_batch(out_db, col_name, batch_docs, "sync_view_worker")
                            sent_batches += 1
                            sent_docs += len(batch_docs)
                            upserted_total += result.get("upserted", 0)
                            modified_total += result.get("modified", 0)
                            matched_total += result.get("matched", 0)

                        logger.info(
                            "[SYNC] db=%s collection=%s done batches=%d docs=%d upserted=%d modified=%d matched=%d",
                            db_name, col_name, sent_batches, sent_docs, upserted_total, modified_total, matched_total
                        )

                    except Exception as e:
                        logger.exception("[ERROR] db=%s collection=%s unexpected_error=%s", db_name, col_name, type(e).__name__)
                        logger.info("[SYNC] db=%s collection=%s done (with error)", db_name, col_name)

            elapsed = time.time() - cycle_start
            sleep_sec = max(0, SYNC_INTERVAL_SEC - elapsed)

            logger.info("[CYCLE END] elapsed=%.1fs sleep=%.1fs", elapsed, sleep_sec)
            time.sleep(sleep_sec)

    except KeyboardInterrupt:
        logger.info("[STOP] interrupted by user (Ctrl+C)")
    except Exception:
        logger.exception("[FATAL] main loop crashed")

if __name__ == "__main__":
    main_loop()
