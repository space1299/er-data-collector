from common.logger import setup_logger
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pymongo.collection import Collection

logger = setup_logger("er_version")


class VersionNotFoundError(Exception):
    """요청한 버전 정보를 찾지 못한 경우 발생하는 예외."""


class SeasonNameResolutionError(Exception):
    """시즌 이름을 정상적으로 계산하지 못한 경우 발생하는 예외."""


@dataclass(frozen=True)
class VersionInfo:
    """버전 정보를 담는 불변 데이터 객체.

    입력값과 반환값은 정수 기반이며, version_str는 "{season}.{major}.{minor}" 형식이다.
    필드가 누락되거나 변환이 불가능하면 ValueError 또는 VersionNotFoundError가 발생한다.
    """

    season: int
    major: int
    minor: int
    season_id: Optional[int]
    version_str: str


# ===== 파싱/포맷 =====

def parse_version_str(version_str: str) -> VersionInfo:
    """버전 문자열을 파싱해 VersionInfo를 반환한다.

    입력값:
        - version_str: "{season}.{major}.{minor}" 형식의 문자열
    반환값:
        - VersionInfo (season, major, minor는 정수, season_id는 None)
    예외:
        - ValueError: 형식이 잘못되었거나 정수 변환 실패

    예시:
        >>> parse_version_str("9.5.0").season
        9
    """

    if not isinstance(version_str, str):
        raise ValueError("version_str는 문자열이어야 합니다.")

    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError("version_str 형식이 올바르지 않습니다. (예: 9.5.0)")

    try:
        season = int(parts[0])
        major = int(parts[1])
        minor = int(parts[2])
    except Exception as e:
        raise ValueError("version_str의 각 항목은 정수여야 합니다.") from e

    return VersionInfo(
        season=season,
        major=major,
        minor=minor,
        season_id=None,
        version_str=format_version_str(season, major, minor),
    )


def format_version_str(season: int, major: int, minor: int) -> str:
    """버전 정보를 "{season}.{major}.{minor}" 형식 문자열로 변환한다.

    입력값:
        - season, major, minor: 정수
    반환값:
        - 문자열 version_str
    예외:
        - ValueError: 정수 변환 실패
    """

    try:
        return f"{int(season)}.{int(major)}.{int(minor)}"
    except Exception as e:
        raise ValueError("버전 숫자 변환에 실패했습니다.") from e


# ===== Mongo 쿼리 헬퍼 =====

def get_latest_version_doc(col_versions: Collection) -> Optional[Dict[str, Any]]:
    """view_versions에서 최신 버전 문서를 반환한다.

    입력값:
        - col_versions: view_versions 컬렉션
    반환값:
        - 최신 버전 문서(dict) 또는 None
    예외:
        - 없음 (조회 실패 시 None)
    """

    if col_versions is None:
        return None

    return col_versions.find_one(sort=[("season", -1), ("major", -1), ("minor", -1)])


def get_version_doc_by_version_str(col_versions: Collection, version_str: str) -> Optional[Dict[str, Any]]:
    """version_str로 버전 문서를 조회한다.

    입력값:
        - col_versions: view_versions 컬렉션
        - version_str: "{season}.{major}.{minor}" 문자열
    반환값:
        - 버전 문서(dict) 또는 None
    예외:
        - 없음 (조회 실패 시 None)
    """

    if col_versions is None:
        return None
    if not version_str:
        return None
    return col_versions.find_one({"version_str": version_str})


def get_version_doc_by_triple(
    col_versions: Collection,
    season: int,
    major: int,
    minor: int,
) -> Optional[Dict[str, Any]]:
    """season/major/minor 조합으로 버전 문서를 조회한다.

    입력값:
        - col_versions: view_versions 컬렉션
        - season, major, minor: 정수
    반환값:
        - 버전 문서(dict) 또는 None
    예외:
        - 없음 (조회 실패 시 None)
    """

    if col_versions is None:
        return None

    try:
        query = {"season": int(season), "major": int(major), "minor": int(minor)}
    except Exception:
        return None

    return col_versions.find_one(query)


def get_version_doc_by_season_id(
    col_versions: Collection,
    season_id: int,
) -> Optional[Dict[str, Any]]:
    """season_id로 버전 문서를 조회한다.

    입력값:
        - col_versions: view_versions 컬렉션
        - season_id: 정수
    반환값:
        - 버전 문서(dict) 또는 None
    예외:
        - 없음 (조회 실패 시 None)
    """

    if col_versions is None:
        return None

    try:
        sid = int(season_id)
    except Exception:
        return None

    return col_versions.find_one({"season_id": sid})


# ===== 내부 유틸 =====

def _build_version_info_from_doc(doc: Dict[str, Any]) -> VersionInfo:
    """버전 문서로부터 VersionInfo를 구성한다.

    입력값:
        - doc: view_versions 문서
    반환값:
        - VersionInfo
    예외:
        - VersionNotFoundError: 필수 필드가 누락되거나 변환 실패
    """

    if not doc:
        raise VersionNotFoundError("버전 문서를 찾지 못했습니다.")

    for field in ("season", "major", "minor", "version_str"):
        if field not in doc:
            raise VersionNotFoundError(f"버전 문서에 필드가 누락되었습니다: {field}")

    try:
        season = int(doc["season"])
        major = int(doc["major"])
        minor = int(doc["minor"])
    except Exception as e:
        raise VersionNotFoundError("버전 문서의 정수 변환에 실패했습니다.") from e

    season_id = doc.get("season_id")
    if season_id is not None:
        try:
            season_id = int(season_id)
        except Exception:
            season_id = None

    version_str = doc.get("version_str")
    if not isinstance(version_str, str) or not version_str:
        version_str = format_version_str(season, major, minor)

    return VersionInfo(
        season=season,
        major=major,
        minor=minor,
        season_id=season_id,
        version_str=version_str,
    )


def _is_pre_season_from_number(season_number: int) -> bool:
    """시즌 번호의 홀짝에 따라 프리시즌 여부를 판단한다.

    규칙:
        - 짝수: Pre-Season
        - 홀수: Season
    """

    return int(season_number) % 2 == 0


def _apply_ea_prefix(base: str, season_id: int) -> str:
    """season_id 기준으로 EA 접두사를 적용한다."""

    if int(season_id) <= 17:
        return f"EA-{base}"
    return base


# ===== 고수준 API =====

def resolve_latest_version(col_versions: Collection) -> VersionInfo:
    """view_versions에서 최신 버전을 조회해 VersionInfo로 반환한다.

    입력값:
        - col_versions: view_versions 컬렉션
    반환값:
        - VersionInfo
    예외:
        - VersionNotFoundError: 최신 버전 문서를 찾지 못한 경우
    """

    doc = get_latest_version_doc(col_versions)
    if not doc:
        raise VersionNotFoundError("최신 버전 문서를 찾지 못했습니다.")

    logger.debug("최신 버전 문서를 조회했습니다.")
    return _build_version_info_from_doc(doc)


def resolve_version(col_versions: Collection, version_str: str) -> VersionInfo:
    """version_str로 버전을 조회해 VersionInfo로 반환한다.

    입력값:
        - col_versions: view_versions 컬렉션
        - version_str: "{season}.{major}.{minor}" 문자열
    반환값:
        - VersionInfo
    예외:
        - VersionNotFoundError: 버전 문서를 찾지 못한 경우
    """

    doc = get_version_doc_by_version_str(col_versions, version_str)
    if not doc:
        raise VersionNotFoundError("요청한 버전 문서를 찾지 못했습니다.")

    logger.debug("version_str로 버전 문서를 조회했습니다: %s", version_str)
    return _build_version_info_from_doc(doc)


def version_str_to_season_id(col_versions: Collection, version_str: str) -> int:
    """version_str에 해당하는 season_id를 반환한다.

    입력값:
        - col_versions: view_versions 컬렉션
        - version_str: "{season}.{major}.{minor}" 문자열
    반환값:
        - season_id 정수
    예외:
        - VersionNotFoundError: 버전 문서 또는 season_id가 없을 때
    """

    doc = get_version_doc_by_version_str(col_versions, version_str)
    if not doc:
        raise VersionNotFoundError("season_id를 찾기 위한 버전 문서가 없습니다.")

    if "season_id" not in doc or doc.get("season_id") is None:
        raise VersionNotFoundError("버전 문서에 season_id가 없습니다.")

    try:
        return int(doc["season_id"])
    except Exception as e:
        raise VersionNotFoundError("season_id 정수 변환에 실패했습니다.") from e


def season_id_to_season_name(
    col_versions: Collection,
    season_id: int,
    col_info_current: Optional[Collection] = None,
) -> str:
    """season_id를 정규화된 seasonName으로 변환한다.

    우선순위:
        1) view_versions 기반 계산
        2) info_current 기반 보정

    입력값:
        - col_versions: view_versions 컬렉션
        - season_id: 정수
        - col_info_current: info_current 컬렉션(옵션)
    반환값:
        - 정규화된 seasonName 문자열
    예외:
        - SeasonNameResolutionError: 계산 또는 보정 실패
    """

    if col_versions is not None:
        doc = get_version_doc_by_season_id(col_versions, season_id)
        if doc and doc.get("season") is not None:
            try:
                season_number = int(doc.get("season"))
                if season_number <= 0:
                    raise ValueError("season 값이 0 이하입니다.")

                if _is_pre_season_from_number(season_number):
                    base = f"Pre-Season{season_number}"
                else:
                    base = f"Season{season_number}"

                return _apply_ea_prefix(base, season_id)
            except Exception as e:
                logger.debug("view_versions 기반 시즌 이름 계산 실패: %s", e)

    if col_info_current is None:
        raise SeasonNameResolutionError("info_current가 없어 시즌 이름을 계산할 수 없습니다.")

    return season_name_from_info_current(col_info_current, season_id)


def season_name_from_info_current(col_info_current: Collection, season_id: int) -> str:
    """info_current의 Season 문서를 이용해 seasonName을 정규화한다.

    처리 규칙:
        - seasonID 일치 행을 찾는다.
        - seasonName에서 마지막 숫자를 추출해 N으로 사용한다.
        - seasonName에 "pre"가 포함되면 Pre-Season, 아니면 Season으로 처리한다.
        - season_id <= 17이면 "EA-" 접두사를 붙인다.

    입력값:
        - col_info_current: info_current 컬렉션
        - season_id: 정수
    반환값:
        - 정규화된 seasonName 문자열
    예외:
        - SeasonNameResolutionError: 데이터 누락 또는 파싱 실패

    예시:
        >>> # season_id=36, seasonName="Pre-Season10"
        >>> # 결과: "Pre-Season10"
    """

    if col_info_current is None:
        raise SeasonNameResolutionError("info_current 컬렉션이 필요합니다.")

    try:
        sid = int(season_id)
    except Exception as e:
        raise SeasonNameResolutionError("season_id 정수 변환에 실패했습니다.") from e

    season_doc = col_info_current.find_one({"_id": "Season"})
    if not season_doc:
        raise SeasonNameResolutionError("info_current에 Season 문서가 없습니다.")

    data = season_doc.get("data")
    if not isinstance(data, list):
        raise SeasonNameResolutionError("Season 문서의 data가 리스트가 아닙니다.")

    row = None
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("seasonID") == sid:
            row = item
            break

    if not row:
        raise SeasonNameResolutionError("seasonID에 해당하는 행을 찾지 못했습니다.")

    raw_name = row.get("seasonName")
    if not isinstance(raw_name, str) or not raw_name:
        raise SeasonNameResolutionError("seasonName이 유효하지 않습니다.")

    is_pre = re.search(r"pre", raw_name, re.IGNORECASE) is not None
    numbers = re.findall(r"(\d+)", raw_name)
    if not numbers:
        raise SeasonNameResolutionError("seasonName에서 숫자를 추출하지 못했습니다.")

    n = int(numbers[-1])
    base = f"Pre-Season{n}" if is_pre else f"Season{n}"

    return _apply_ea_prefix(base, sid)




