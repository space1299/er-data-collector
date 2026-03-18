from datetime import datetime
from typing import List, Optional

from common.models.er_api_models import BattleUserResult, ERBaseModel, UserGamesResponse


def _parse_start_dtm(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


class MatchFact(ERBaseModel):
    userId: int
    gameId: int
    playedAt: Optional[datetime] = None
    seasonId: Optional[int] = None
    matchingMode: Optional[int] = None
    matchingTeamMode: Optional[int] = None
    versionMajor: Optional[int] = None
    versionMinor: Optional[int] = None
    characterNum: Optional[int] = None
    bestWeapon: Optional[int] = None
    gameRank: Optional[int] = None
    victory: Optional[int] = None
    isTop3: Optional[bool] = None
    mmrBefore: Optional[int] = None
    mmrGain: Optional[int] = None
    mmrAfter: Optional[int] = None
    mmrAvg: Optional[int] = None
    damageToPlayer: Optional[float] = None
    teamKill: Optional[int] = None


def battle_to_match_fact(user_id: int, b: BattleUserResult) -> MatchFact:
    damage_value: Optional[float]
    if b.damageToPlayer is None:
        damage_value = None
    else:
        try:
            damage_value = float(b.damageToPlayer)
        except (TypeError, ValueError):
            damage_value = None

    is_top3: Optional[bool]
    if b.gameRank is None:
        is_top3 = None
    else:
        is_top3 = b.gameRank <= 3

    return MatchFact(
        userId=user_id,
        gameId=b.gameId,
        playedAt=_parse_start_dtm(b.startDtm),
        seasonId=b.seasonId,
        matchingMode=b.matchingMode,
        matchingTeamMode=b.matchingTeamMode,
        versionMajor=b.versionMajor,
        versionMinor=b.versionMinor,
        characterNum=b.characterNum,
        bestWeapon=b.bestWeapon,
        gameRank=b.gameRank,
        victory=b.victory,
        isTop3=is_top3,
        mmrBefore=b.mmrBefore,
        mmrGain=b.mmrGain,
        mmrAfter=b.mmrAfter,
        mmrAvg=b.mmrAvg,
        damageToPlayer=damage_value,
        teamKill=b.teamKill,
    )


def to_match_facts(user_id: int, resp: UserGamesResponse) -> List[MatchFact]:
    return [battle_to_match_fact(user_id, b) for b in resp.userGames]
