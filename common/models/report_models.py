from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_object_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and "$oid" in value:
        oid = value.get("$oid")
        return oid if isinstance(oid, str) else None
    return None


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, dict) and "$date" in value:
        value = value.get("$date")
    if isinstance(value, str):
        # Minimal parsing for ISO-8601 with optional Z suffix.
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class ReportJobError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: Optional[str] = None
    detail: Optional[str] = None


class ReportJobDoc(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())

    id: Optional[str] = Field(default=None, alias="_id")
    dedupe_key: str
    nickname: str
    status: str
    createdAt: datetime
    updatedAt: datetime
    expiresAt: Optional[datetime] = None
    lockedAt: Optional[datetime] = None
    lockedBy: Optional[str] = None
    result_ref: Optional[str] = None
    error: Optional[ReportJobError] = None

    @field_validator("id", "result_ref", mode="before")
    @classmethod
    def _parse_object_id(cls, value: Any) -> Optional[str]:
        return _coerce_object_id(value)

    @field_validator(
        "createdAt",
        "updatedAt",
        "expiresAt",
        "lockedAt",
        mode="before",
    )
    @classmethod
    def _parse_datetime(cls, value: Any) -> Optional[datetime]:
        return _coerce_datetime(value)


class UserReportMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reportVersion: str
    nickname: str
    userId: Optional[str] = None
    seasonId: int
    versionSeason: Optional[int] = None
    matchingMode: int
    matchingTeamMode: Optional[int] = None
    versionMajor: int
    versionMinor: int
    createdAt: datetime
    sourceWindowDays: Optional[int] = None
    cutoffReason: Optional[str] = None
    recentGameCount: Optional[int] = None

    @field_validator("createdAt", mode="before")
    @classmethod
    def _parse_created_at(cls, value: Any) -> Optional[datetime]:
        return _coerce_datetime(value)


class ApiCharacterStat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    characterCode: int
    totalGames: Optional[int] = None
    wins: Optional[int] = None
    top3Rate: Optional[float] = None
    averageRank: Optional[float] = None
    maxKillings: Optional[int] = None


class SeasonSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mmr: Optional[int] = None
    rank: Optional[int] = None
    rankSize: Optional[int] = None
    rankPercent: Optional[float] = None
    totalGames: Optional[int] = None
    totalWins: Optional[int] = None
    averageRank: Optional[float] = None
    top1: Optional[float] = None
    top2: Optional[float] = None
    top3: Optional[float] = None
    top5: Optional[float] = None
    top7: Optional[float] = None
    apiCharacterStats: Optional[List[ApiCharacterStat]] = None


class CharacterSlice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    characterNum: int
    bestWeapon: int
    mmrRange: Optional[str] = None
    versionSeason: Optional[int] = None
    versionMajor: Optional[int] = None
    versionMinor: Optional[int] = None
    pickCount: int
    mmrGain_sum: int
    gameRank_sum: int
    top3_count: int
    victory_count: int
    damage_sum: int
    tk_sum: int


class CharacterCompareKey(BaseModel):
    model_config = ConfigDict(extra="ignore")

    characterNum: int
    bestWeapon: int
    mmrRange: Optional[str] = None
    versionSeason: Optional[int] = None
    versionMajor: int
    versionMinor: int


class TierCharacterWeaponStat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pickCount: int
    mmrGain_sum: int
    gameRank_sum: int
    top3_count: int
    victory_count: int
    damage_sum: int
    tk_sum: int
    characterNum: int
    bestWeapon: int
    mmrRange: Optional[str] = None
    versionMajor: int
    versionMinor: int


class CharacterCompareDiff(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mmrGain_avg_delta: Optional[float] = None
    avg_rank_delta: Optional[float] = None
    top3_rate_delta: Optional[float] = None
    win_rate_delta: Optional[float] = None
    avg_damage_delta: Optional[float] = None
    avg_tk_delta: Optional[float] = None


class CharacterCompareItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: CharacterCompareKey
    user: CharacterSlice
    tierAvg: Optional[TierCharacterWeaponStat] = None
    diff: Optional[CharacterCompareDiff] = None


class CharacterSlicesSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: List[CharacterSlice]


class CharacterCompareSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: List[CharacterCompareItem]


class UserReportDoc(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    id: Optional[str] = Field(default=None, alias="_id")
    meta: UserReportMeta
    seasonSummary: SeasonSummary
    characterSlices: CharacterSlicesSection
    characterCompare: CharacterCompareSection

    @field_validator("id", mode="before")
    @classmethod
    def _parse_object_id(cls, value: Any) -> Optional[str]:
        return _coerce_object_id(value)
