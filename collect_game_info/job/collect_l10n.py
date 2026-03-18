import json
import hashlib
from datetime import datetime, timezone
from typing import Dict
from pathlib import Path

from pymongo import MongoClient

from common.db.access import info_db
from common.er_api import get_l10n_url
from common.logger import setup_logger

BASE_DIR = Path(__file__).resolve().parent  # job/ 폴더
DEFAULT_L10N_PATH = (BASE_DIR / "l10n-Korean.txt").resolve()

logger = setup_logger("collect_l10n")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_l10n_as_map(file_path: str) -> Dict[str, str]:
    out: Dict[str, str] = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if "┃" not in line:
                continue
            key_raw, value = line.strip().split("┃", 1)
            out[key_raw] = value

    return out


def _compute_file_hash(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def sync_l10n_once(
    client: MongoClient,
    *,
    file_path: str = str(DEFAULT_L10N_PATH),
    locale: str = "Korean",
) -> None:
    now = _utc_now()
    col_l10n = info_db(client)["l10n_info"]

    try:
        get_l10n_url(file_path)

        file_hash = _compute_file_hash(file_path)
        l10n_map = _load_l10n_as_map(file_path)

        approx_bytes = len(
            json.dumps(l10n_map, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        if approx_bytes > 14 * 1024 * 1024:
            logger.warning(f"l10n 문서가 큽니다(약 {approx_bytes/1024/1024:.2f}MB). 16MB 제한에 근접할 수 있어요.")

        doc = {
            "_id": locale,
            "locale": locale,
            "fetchedAt": now,
            "count": len(l10n_map),
            "hash": file_hash,
            "data": l10n_map,
        }

        col_l10n.replace_one({"_id": locale}, doc, upsert=True)
        logger.info(f"l10n 최신화 완료: locale={locale}, count={len(l10n_map)}")

    except Exception as e:
        logger.error(f"l10n 정보 수집 중 오류 발생: {e}")
