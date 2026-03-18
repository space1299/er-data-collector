import time

from common.db.access import view_db
from common.db.client import get_client
from common.db.init import ensure_indexes
from common.logger import setup_logger
from common.er_version import VersionNotFoundError, resolve_latest_version
from job.collect_data_raw import init_data_once, collect_raw_once, ensure_user_checks_seeded

logger = setup_logger("collect_data_raw_main")

SLEEP_SEC_ON_NO_VERSION = 60
SLEEP_SEC_BETWEEN_LOOPS = 1

def _select_version_str_for_worker(client, rule: str):
    col_versions = view_db(client)["versions"]

    if rule == "before":
        docs = list(
            col_versions.find({}, {"version_str": 1})
            .sort([("season", -1), ("major", -1), ("minor", -1)])
            .limit(2)
        )
        if len(docs) < 2:
            return None
        return docs[1].get("version_str")

    try:
        return resolve_latest_version(col_versions).version_str
    except VersionNotFoundError:
        return None


def main():
    from config import INIT_NICKNAME, WORKER_RULE, DB_URL

    client = None
    init_done = False
    last_seed_attempt = 0.0

    logger.info(
        f"[main] 워커 시작, WORKER_RULE={WORKER_RULE!r}, INIT_NICKNAME={INIT_NICKNAME!r}"
    )

    while True:
        try:
            if client is None:
                try:
                    client = get_client(db_url=DB_URL)
                    ensure_indexes(client)
                except Exception as e:
                    logger.exception(f"[main] DB 연결 실패: {e}")
                    time.sleep(5)
                    continue

            if INIT_NICKNAME and not init_done:
                try:
                    init_data_once(client, INIT_NICKNAME)
                except Exception as e:
                    logger.exception(f"[main] init_data_once 중 예외 발생: {e}")
                init_done = True

            version_str = _select_version_str_for_worker(client, WORKER_RULE)
            if version_str is None:
                logger.info(
                    f"[main] 대상 버전이 없어 {SLEEP_SEC_ON_NO_VERSION}s 대기 후 재시도합니다."
                )
                time.sleep(SLEEP_SEC_ON_NO_VERSION)
                continue

            now = time.time()
            if now - last_seed_attempt >= 60:
                ensure_indexes(client, raw_versions=[version_str])
                seeded = ensure_user_checks_seeded(client, version_str, INIT_NICKNAME)
                last_seed_attempt = now
                if not seeded:
                    logger.info("[main] user_checks empty; seed attempt failed")

            collect_raw_once(client, version_str)

        except KeyboardInterrupt:
            logger.info("[main] KeyboardInterrupt 감지, 워커를 종료합니다.")
            break
        except Exception as e:
            logger.exception(f"[main] 루프 중 예외 발생: {e}")
            time.sleep(5)

        time.sleep(SLEEP_SEC_BETWEEN_LOOPS)


if __name__ == "__main__":
    main()
