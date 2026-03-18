import argparse
import os
import time
from dataclasses import dataclass

from common.db.access import info_db, report_db, view_db
from common.db.client import get_client
from common.db.init import ensure_indexes
from common.logger import setup_logger
from common.models.report_models import ReportJobDoc, UserReportDoc
from job.build_view import build_user_report_view, write_error_view
from job.get_job import (
    claim_next_job,
    complete_job,
    ensure_job_indexes,
    fail_job,
)
from job.fill_compare import fill_compare_for_report
from job.report_service import build_report_payload, fetch_er_data

import config

logger = setup_logger("generate_user_report_worker")

DEFAULT_WINDOW_DAYS = 90

@dataclass(frozen=True)
class ReportSettings:
    db_url: str
    worker_lock_id: str
    poll_interval_sec: int
    max_games: int
    matching_mode: int
    lease_sec: int
    max_retry: int


def build_settings() -> ReportSettings:
    return ReportSettings(
        db_url=config.DB_URL,
        worker_lock_id=config.WORKER_LOCK_ID,
        poll_interval_sec=config.POLL_INTERVAL_SEC,
        max_games=config.N_TARGET,
        matching_mode=config.MATCHING_MODE,
        lease_sec=config.REPORT_JOB_LEASE_SEC,
        max_retry=config.REPORT_JOB_MAX_RETRY,
    )


def _build_worker_id(worker_lock_id: str) -> str:
    if worker_lock_id:
        return worker_lock_id
    import os
    import socket
    return f"{socket.gethostname()}:{os.getpid()}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate user report worker")
    parser.add_argument("--once", action="store_true", help="process a single job then exit")
    return parser.parse_args()


def _log_report_summary(doc: UserReportDoc) -> None:
    meta = doc.meta
    logger.info(
        "[report] nickname=%s season=%s mode=%s version=%s.%s.%s recent=%s slices=%s",
        meta.nickname,
        meta.seasonId,
        meta.matchingMode,
        meta.versionSeason,
        meta.versionMajor,
        meta.versionMinor,
        meta.recentGameCount,
        len(doc.characterSlices.items),
    )


def main() -> None:
    args = _parse_args()
    settings = build_settings()
    client = None
    stats_client = None
    report_db_handle = None
    db_view_handle = None
    db_info_handle = None

    worker_id = _build_worker_id(settings.worker_lock_id)
    logger.info("[워커] 시작: worker_id=%s, max_retry=%s", worker_id, settings.max_retry)

    while True:
        try:
            if client is None:
                try:
                    client = get_client(db_url=settings.db_url)
                    internal_uri = os.environ.get("MONGO_INTERNAL_URI")
                    if not internal_uri:
                        raise RuntimeError("missing env: MONGO_INTERNAL_URI")
                    stats_client = get_client(db_url=internal_uri)
                    ensure_indexes(client)
                    report_db_handle = report_db(client)
                    db_view_handle = view_db(client)
                    db_info_handle = info_db(stats_client)
                    ensure_job_indexes(report_db_handle)
                except Exception as e:
                    logger.exception("[워커] DB 연결 실패: %s", e)
                    time.sleep(5)
                    continue

            job = claim_next_job(report_db_handle, worker_id, settings.lease_sec, settings.max_retry)
            if not job:
                if args.once:
                    logger.info("[워커] 처리할 작업 없음; 종료 (--once)")
                    break
                time.sleep(settings.poll_interval_sec)
                continue

            job_id = job.get("_id")
            job_doc = ReportJobDoc.model_validate(job)
            attempts = job.get("attempts", 0)
            if attempts > 0:
                logger.info("[워커] 작업 재시도: id=%s nickname=%s attempts=%s/%s",
                            job_id, job_doc.nickname, attempts, settings.max_retry)
            else:
                logger.info("[워커] 작업 잠금: id=%s nickname=%s", job_id, job_doc.nickname)

            try:
                user_id, season_id, matching_mode, report_version, stats_resp, recent_games, canonical_nickname = fetch_er_data(
                    job=job,
                    default_matching_mode=settings.matching_mode,
                    window_days=DEFAULT_WINDOW_DAYS,
                    max_games=settings.max_games,
                )

                report_doc, dedupe_key = build_report_payload(
                    job=job,
                    canonical_nickname=canonical_nickname,
                    stats_resp=stats_resp,
                    recent_games=recent_games,
                    report_version=report_version,
                    season_id=season_id,
                    matching_mode=matching_mode,
                    user_id=user_id,
                    window_days=DEFAULT_WINDOW_DAYS,
                    max_games=settings.max_games,
                )

                report_doc, compare_result = fill_compare_for_report(
                    report_doc,
                    stats_client=stats_client,
                )
                logger.info(
                    "[비교] dedupe_key=%s nickname=%s seasonId=%s matchingMode=%s slices=%s filled=%s missing=%s db=%s",
                    dedupe_key,
                    job_doc.nickname,
                    job.get("seasonId"),
                    job.get("matchingMode"),
                    compare_result["slice_count"],
                    compare_result["filled_count"],
                    compare_result["missing_count"],
                    compare_result["db_name"],
                )

                build_user_report_view(
                    report_doc,
                    dedupe_key,
                    db_view=db_view_handle,
                )

                complete_job(report_db_handle, job_id, dedupe_key)
                _log_report_summary(report_doc)
                logger.info("[워커] 작업 완료: id=%s", job_id)
            except Exception as e:
                logger.exception("[워커] 작업 실패: id=%s err=%s", job_id, e)
                fail_job(report_db_handle, job_id, str(e))
                try:
                    write_error_view(
                        job_doc.dedupe_key,
                        str(e),
                        db_view=db_view_handle,
                    )
                except Exception as ve:
                    logger.exception("[워커] 에러 view 기록 실패: id=%s err=%s", job_id, ve)

            if args.once:
                break

        except KeyboardInterrupt:
            logger.info("[워커] KeyboardInterrupt, 중지")
            break
        except Exception as e:
            logger.exception("[워커] 루프 오류: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
