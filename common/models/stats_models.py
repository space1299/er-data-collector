from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class CharacterStatisticsDoc(BaseModel):
    model_config = ConfigDict(extra="allow")

    _id: Optional[Any] = None
    pickCount: int
    mmrGain_sum: int
    gameRank_sum: int
    top3_count: int
    victory_count: int
    damage_sum: int
    tk_sum: int
    characterNum: int
    bestWeapon: int
    mmrRange: str
    versionSeason: int
    versionMajor: int
    versionMinor: int
