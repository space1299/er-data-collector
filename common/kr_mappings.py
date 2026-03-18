from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# =========================
# 1) 원본 리스트: (id, en, kr)
# =========================

WEAPONS: List[Tuple[int, str, str]] = [
    (0,  "None",          "없음"),
    (1,  "Glove",         "글러브"),
    (2,  "Tonfa",         "톤파"),
    (3,  "Bat",           "방망이"),
    (4,  "Whip",          "채찍"),
    (5,  "HighAngleFire", "투척"),
    (6,  "DirectFire",    "암기"),
    (7,  "Bow",           "활"),
    (8,  "CrossBow",      "석궁"),
    (9,  "Pistol",        "권총"),
    (10, "AssaultRifle",  "돌격 소총"),
    (11, "SniperRifle",   "저격총"),
    (13, "Hammer",        "망치"),
    (14, "Axe",           "도끼"),
    (15, "OneHandSword",  "단검"),
    (16, "TwoHandSword",  "양손검"),
    (17, "Polearm",       "폴암"),
    (18, "DualSword",     "쌍검"),
    (19, "Spear",         "창"),
    (20, "Nunchaku",      "쌍절곤"),
    (21, "Rapier",        "레이피어"),
    (22, "Guitar",        "기타"),
    (23, "Camera",        "카메라"),
    (24, "Arcana",        "아르카나"),
    (25, "VFArm",         "VF의수"),
]

TIERS: List[Tuple[int, str, str, int, int]] = [
    (0, "Iron",     "아이언",     0, 599),
    (1, "Bronze",   "브론즈",   600, 1399),
    (2, "Silver",   "실버",    1400, 2399),
    (3, "Gold",     "골드",    2400, 3599),
    (4, "Platinum", "플래티넘", 3600, 4999),
    (5, "Diamond",  "다이아몬드", 5000, 6399),
    (6, "Meteor",   "메테오",  6400, 7399),
    (7, "Mithril",  "미스릴",  7400, 10**9),
    (8, "Demigod",  "데미갓",  8100, 10**9),
    (9, "Eternity", "이터니티", 8100, 10**9),
]

# Characters는 요청 포맷의 튜플 목록을 source of truth로 둔다.
CHARACTERS: List[Tuple[int, str, str]] = [
    (0,  "0",  "무작위"),
    (1,  "1",  "재키"),
    (2,  "2",  "아야"),
    (3,  "3",  "피오라"),
    (4,  "4",  "매그너스"),
    (5,  "5",  "자히르"),
    (6,  "6",  "나딘"),
    (7,  "7",  "현우"),
    (8,  "8",  "하트"),
    (9,  "9",  "아이솔"),
    (10, "10", "리 다이린"),
    (11, "11", "유키"),
    (12, "12", "혜진"),
    (13, "13", "쇼우"),
    (14, "14", "키아라"),
    (15, "15", "시셀라"),
    (16, "16", "실비아"),
    (17, "17", "아드리아나"),
    (18, "18", "쇼이치"),
    (19, "19", "엠마"),
    (20, "20", "레녹스"),
    (21, "21", "로지"),
    (22, "22", "루크"),
    (23, "23", "캐시"),
    (24, "24", "아델라"),
    (25, "25", "버니스"),
    (26, "26", "바바라"),
    (27, "27", "알렉스"),
    (28, "28", "수아"),
    (29, "29", "레온"),
    (30, "30", "일레븐"),
    (31, "31", "리오"),
    (32, "32", "윌리엄"),
    (33, "33", "니키"),
    (34, "34", "나타폰"),
    (35, "35", "얀"),
    (36, "36", "이바"),
    (37, "37", "다니엘"),
    (38, "38", "제니"),
    (39, "39", "카밀로"),
    (40, "40", "클로에"),
    (41, "41", "요한"),
    (42, "42", "비앙카"),
    (43, "43", "셀린"),
    (44, "44", "에키온"),
    (45, "45", "마이"),
    (46, "46", "에이든"),
    (47, "47", "라우라"),
    (48, "48", "띠아"),
    (49, "49", "펠릭스"),
    (50, "50", "엘레나"),
    (51, "51", "프리야"),
    (52, "52", "아디나"),
    (53, "53", "마커스"),
    (54, "54", "칼라"),
    (55, "55", "에스텔"),
    (56, "56", "피올로"),
    (57, "57", "마르티나"),
    (58, "58", "헤이즈"),
    (59, "59", "아이작"),
    (60, "60", "타지아"),
    (61, "61", "이렘"),
    (62, "62", "테오도르"),
    (63, "63", "이안"),
    (64, "64", "바냐"),
    (65, "65", "데비&마를렌"),
    (66, "66", "아르다"),
    (67, "67", "아비게일"),
    (68, "68", "알론소"),
    (69, "69", "레니"),
    (70, "70", "츠바메"),
    (71, "71", "케네스"),
    (72, "72", "카티야"),
    (73, "73", "샬럿"),
    (74, "74", "다르코"),
    (75, "75", "르노어"),
    (76, "76", "가넷"),
    (77, "77", "유민"),
    (78, "78", "히스이"),
    (79, "79", "유스티나"),
    (80, "80", "이슈트반"),
    (81, "81", "니아"),
    (82, "82", "슈린"),
    (83, "83", "헨리"),
    (84, "84", "블레어"),
    (85, "85", "미르카"),
    (86, "86", "펜리르"),
]

CHARACTER_KR: Dict[int, str] = {i: kr for i, _, kr in CHARACTERS}

# =========================
# Tier 판정 정책
# =========================
DEMIGOD_ETERNITY_MIN_MMR = 8100
ETERNITY_MAX_RANK = 300       # 1~300
DEMIGOD_MAX_RANK = 1000       # 301~1000 (Eternity 제외)

# =========================
# 2) 파생 매핑: dict
# =========================

WEAPON_ID_TO_EN: Dict[int, str] = {i: en for i, en, _ in WEAPONS}
WEAPON_ID_TO_KR: Dict[int, str] = {i: kr for i, _, kr in WEAPONS}
WEAPON_EN_TO_ID: Dict[str, int] = {en: i for i, en, _ in WEAPONS}
WEAPON_EN_TO_KR: Dict[str, str] = {en: kr for _, en, kr in WEAPONS}

TIER_EN_TO_KR: Dict[str, str] = {en: kr for _, en, kr, _, _ in TIERS}
TIER_EN_TO_RANGE: Dict[str, tuple[int, int]] = {en: (mn, mx) for _, en, _, mn, mx in TIERS}
TIER_ORDER: Dict[str, int] = {en: order for order, en, _, _, _ in TIERS}

# =========================
# 3) 조회 함수
# =========================

def character_kr(code: int) -> Optional[str]:
    return CHARACTER_KR.get(code)


def weapon_kr(code: int) -> Optional[str]:
    return WEAPON_ID_TO_KR.get(code)


def weapon_en(code: int) -> Optional[str]:
    return WEAPON_ID_TO_EN.get(code)


def weapon_id(en: str) -> Optional[int]:
    return WEAPON_EN_TO_ID.get(en)


def weapon_kr_by_en(en: str) -> Optional[str]:
    return WEAPON_EN_TO_KR.get(en)


def tier_kr(en: str) -> Optional[str]:
    return TIER_EN_TO_KR.get(en)


def tier_by_mmr(mmr: int) -> Optional[str]:
    for _, en, _, mn, mx in TIERS:
        if mn <= mmr <= mx:
            return en
    return None


def tier_kr_by_mmr(mmr: int) -> Optional[str]:
    en = tier_by_mmr(mmr)
    return TIER_EN_TO_KR.get(en) if en else None


def tier_en_by_mmr_rank(*, mmr: Optional[int], rank: Optional[int]) -> Optional[str]:
    if mmr is not None and mmr >= DEMIGOD_ETERNITY_MIN_MMR and rank is not None:
        if 1 <= rank <= ETERNITY_MAX_RANK:
            return "Eternity"
        if ETERNITY_MAX_RANK < rank <= DEMIGOD_MAX_RANK:
            return "Demigod"

    if mmr is None:
        return None

    if mmr >= DEMIGOD_ETERNITY_MIN_MMR:
        return "Mithril"

    return tier_by_mmr(mmr)


def tier_kr_by_mmr_rank(*, mmr: Optional[int], rank: Optional[int]) -> Optional[str]:
    en = tier_en_by_mmr_rank(mmr=mmr, rank=rank)
    return TIER_EN_TO_KR.get(en) if en else None


# character_statistics 컬렉션의 mmrRange 값 매핑
_TIER_TO_STAT_MMR_RANGE: Dict[str, str] = {
    "Iron": "Iron",
    "Bronze": "Bronze",
    "Silver": "Silver",
    "Gold": "Gold",
    "Platinum": "Platinum",
    "Diamond": "Diamond",
    "Meteor": "Meteor",
    "Mithril": "MythrilPlus",
    "Demigod": "MythrilPlus",
    "Eternity": "MythrilPlus",
}


def tier_to_stat_mmr_range(tier_en: Optional[str]) -> Optional[str]:
    """티어 영문명 → character_statistics.mmrRange 값."""
    if tier_en is None:
        return None
    return _TIER_TO_STAT_MMR_RANGE.get(tier_en)