import time

from common.db.access import view_db
from common.db.client import get_client
from common.db.init import ensure_indexes
from common.logger import setup_logger
from common.er_version import VersionNotFoundError, resolve_latest_version
from job.generate_statistics import generate_statistics_once

logger = setup_logger("generate_statistics_main")

SLEEP_SEC_ON_NO_VERSION = 60
SLEEP_SEC_BETWEEN_LOOPS = 120


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
    from config import WORKER_RULE, DB_URL

    client = None
    logger.info(f"[main] ?뚯빱 ?쒖옉, WORKER_RULE={WORKER_RULE!r}")

    while True:
        try:
            if client is None:
                try:
                    client = get_client(db_url=DB_URL)
                    ensure_indexes(client)
                except Exception as e:
                    logger.exception(f"[main] DB ?곌껐 ?ㅽ뙣: {e}")
                    time.sleep(5)
                    continue

            version_str = _select_version_str_for_worker(client, WORKER_RULE)
            if version_str is None:
                logger.info(f"[main] ???踰꾩쟾???놁뼱 {SLEEP_SEC_ON_NO_VERSION}s ?湲고빀?덈떎.")
                time.sleep(SLEEP_SEC_ON_NO_VERSION)
                continue

            ensure_indexes(client, raw_versions=[version_str])
            generate_statistics_once(client, version_str)

        except KeyboardInterrupt:
            logger.info("[main] KeyboardInterrupt 媛먯?, ?뚯빱瑜?醫낅즺?⑸땲??")
            break
        except Exception as e:
            logger.exception(f"[main] 猷⑦봽 以??덉쇅 諛쒖깮: {e}")
            time.sleep(5)

        time.sleep(SLEEP_SEC_BETWEEN_LOOPS)


if __name__ == "__main__":
    main()
