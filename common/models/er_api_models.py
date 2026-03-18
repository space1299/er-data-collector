from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ERBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class UserStatsCharacterStat(ERBaseModel):
    characterCode: Optional[int] = None
    totalGames: Optional[int] = None
    usages: Optional[int] = None
    maxKillings: Optional[int] = None
    top3: Optional[int] = None
    wins: Optional[int] = None
    top3Rate: Optional[float] = None
    averageRank: Optional[float] = None


class UserStatsEntry(ERBaseModel):
    seasonId: Optional[int] = None
    matchingMode: Optional[int] = None
    matchingTeamMode: Optional[int] = None
    mmr: Optional[int] = None
    nickname: Optional[str] = None
    rank: Optional[int] = None
    rankSize: Optional[int] = None
    totalGames: Optional[int] = None
    totalWins: Optional[int] = None
    totalTeamKills: Optional[int] = None
    totalDeaths: Optional[int] = None
    escapeCount: Optional[int] = None
    rankPercent: Optional[float] = None
    averageRank: Optional[float] = None
    averageKills: Optional[float] = None
    averageAssistants: Optional[float] = None
    averageHunts: Optional[float] = None
    top1: Optional[float] = None
    top2: Optional[float] = None
    top3: Optional[float] = None
    top5: Optional[float] = None
    top7: Optional[float] = None
    characterStats: Optional[List[UserStatsCharacterStat]] = None


class UserStatsResponse(ERBaseModel):
    code: int
    message: str
    userStats: List[UserStatsEntry]


class BattleUserResult(ERBaseModel):
    nickname: Optional[str] = None
    gameId: int
    seasonId: Optional[int] = None
    matchingMode: Optional[int] = None
    matchingTeamMode: Optional[int] = None
    characterNum: Optional[int] = None
    bestWeapon: Optional[int] = None
    gameRank: Optional[int] = None
    victory: Optional[int] = None
    startDtm: Optional[str] = None
    duration: Optional[int] = None
    versionMajor: Optional[int] = None
    versionMinor: Optional[int] = None
    mmrBefore: Optional[int] = None
    mmrGain: Optional[int] = None
    mmrAfter: Optional[int] = None
    mmrAvg: Optional[int] = None
    damageToPlayer: Optional[float] = None
    teamKill: Optional[int] = None


class UserGamesResponse(ERBaseModel):
    code: int
    message: str
    userGames: List[BattleUserResult]
    next: Optional[int] = None
