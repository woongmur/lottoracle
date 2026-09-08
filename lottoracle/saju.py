"""사주팔자 — 태어난 순간을 네 기둥 여덟 글자로.

여기 있는 건 전부 답이 있는 계산이다. 만세력과 대조하면 맞다/틀리다를 말할 수
있다. 이 글자들을 '나' 중심으로 읽는 층(십신·신살·강약)은 sipsin.py 에 있다 —
그쪽도 표에서 나오는 값이지만 유파가 갈리는 지점이 있어 따로 뒀다.

기준
  년주  입춘부터 새 해. 설날이 아니다 — 그래서 앱이 보여 주는 띠(설날 기준)와
        어긋나는 구간이 생긴다. 예: 1990-02-01 은 말띠지만 사주 년주는 기사(뱀).
  월주  절(節) 기준. 달력 월이 아니라 입춘·경칩·청명... 12개 절기로 나눈다.
  일주  60갑자가 하루씩 끊기지 않고 도는 것. 2000-01-01 이 무오일(54번)이다.
  시주  서울 평균태양시로 시지를 정하고, 천간은 일간에서 유도한다(오자둔).

시각은 solartime 이 표준시 이력·서머타임·경도를 보정한 값을 쓴다.

야자시(23~24시)는 유파가 갈린다. 여기서는 시주만 다음 날 자시로 넘기고 일주는
그대로 두는 쪽을 따랐다(sxtwl 과 같은 방식). 이 구간에 태어났으면 화면에서
유파에 따라 다를 수 있다고 알려 준다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .solartime import (
    SOLAR_TERMS, epoch_to_parts, seoul_solar_epoch, sign_of, wall_to_utc,
    solar_longitude_at, _days_from_civil, _find_longitude,
)

STEMS = "갑을병정무기경신임계"
BRANCHES = "자축인묘진사오미신유술해"
STEM_HANJA = "甲乙丙丁戊己庚辛壬癸"
BRANCH_HANJA = "子丑寅卯辰巳午未申酉戌亥"
BRANCH_ANIMALS = ("쥐", "소", "호랑이", "토끼", "용", "뱀",
                  "말", "양", "원숭이", "닭", "개", "돼지")

ELEMENTS = ("목", "화", "토", "금", "수")
# 갑을=목 병정=화 무기=토 경신=금 임계=수
STEM_ELEMENT = (0, 0, 1, 1, 2, 2, 3, 3, 4, 4)
# 자=수 축=토 인=목 묘=목 진=토 사=화 오=화 미=토 신=금 유=금 술=토 해=수
BRANCH_ELEMENT = (4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4)
# 갑병무경임 = 양, 을정기신계 = 음
STEM_YIN = (False, True) * 5

# 2000-01-01 이 60갑자 54번(무오)이다. sxtwl 로 확인했다.
_DAY_ANCHOR_DAYS = _days_from_civil(2000, 1, 1)
_DAY_ANCHOR_INDEX = 54


def _gz(index: int) -> tuple[int, int]:
    """60갑자 번호 -> (천간 번호, 지지 번호)."""
    return index % 10, index % 12


@dataclass(frozen=True)
class Pillar:
    stem: int
    branch: int

    @property
    def name(self) -> str:
        return STEMS[self.stem] + BRANCHES[self.branch]

    @property
    def hanja(self) -> str:
        return STEM_HANJA[self.stem] + BRANCH_HANJA[self.branch]

    @property
    def animal(self) -> str:
        return BRANCH_ANIMALS[self.branch]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hanja": self.hanja,
            "stem": STEMS[self.stem],
            "branch": BRANCHES[self.branch],
            "animal": self.animal,
            "stemElement": ELEMENTS[STEM_ELEMENT[self.stem]],
            "branchElement": ELEMENTS[BRANCH_ELEMENT[self.branch]],
            "yin": STEM_YIN[self.stem],
        }


_LICHUN_CACHE: dict[int, float] = {}


def lichun_epoch(year: int) -> float:
    """그 해 입춘(황경 315도)의 순간. 2월 4일 언저리다."""
    hit = _LICHUN_CACHE.get(year)
    if hit is None:
        hit = _find_longitude(315.0, _days_from_civil(year, 2, 4) * 86400.0)
        _LICHUN_CACHE[year] = hit
    return hit


def year_pillar(utc_epoch: float, local_year: int) -> Pillar:
    """입춘을 새 해의 시작으로 본다 — 설날이 아니다.

    황경만 보고 가르려다 틀렸었다. 황경 285~315도 구간이 1월 하순~2월 초라
    달력 해와 사주 해가 엇갈리는데, 달을 보고 판정하니 입춘 전날까지 새 해로
    셌다. 그 해 입춘 시각과 직접 견주는 게 확실하다.

    어느 해의 입춘과 견줄지는 태어난 곳 달력(local_year)으로 고르고,
    앞뒤 판정은 진짜 UTC 순간끼리 한다.
    """
    year = local_year if utc_epoch >= lichun_epoch(local_year) else local_year - 1
    return Pillar(*_gz((year - 4) % 60))


def month_pillar(utc_epoch: float, year_stem: int) -> Pillar:
    """절(節) 기준. 입춘(315도)부터 인월이고 30도마다 다음 지지로 넘어간다.

    천간은 년간에서 유도한다(오호둔): 갑기년의 인월은 병인, 을경년은 무인 ...
    """
    lon = solar_longitude_at(utc_epoch)
    step = int(((lon - 315.0) % 360.0) // 30)     # 인월부터 몇 번째 달인가
    branch = (2 + step) % 12
    first = (year_stem % 5) * 2 + 2               # 그 해 인월의 천간
    stem = (first + step) % 10
    return Pillar(stem, branch)


# 절(節)은 달을 가르는 열두 마디다. 24절기 중 홀수 번째(입춘·경칩·청명 ...)로,
# 황경으로는 15도에서 30도마다 하나씩 있다. 중기(춘분·곡우 ...)는 달을 가르지 않는다.
_DEGREES_PER_DAY = 0.98564736


def _jeol_name(longitude: float) -> str:
    """절 황경 -> 이름. solartime 의 24절기 표를 그대로 쓴다."""
    return SOLAR_TERMS[int(round(longitude / 15.0)) % 24]


def next_jeol(utc_epoch: float) -> tuple[str, float]:
    """그 순간 다음에 오는 절의 (이름, UTC epoch 초).

    대운이 언제 시작하는지를 이 간격으로 잰다 — 순행이면 다음 절까지,
    역행이면 지난 절부터의 날수를 세어 3일을 1년으로 친다.
    """
    lon = solar_longitude_at(utc_epoch)
    past = (lon - 15.0) % 30.0                      # 지난 절에서 몇 도 왔나
    target = (lon - past + 30.0) % 360.0
    guess = utc_epoch + (30.0 - past) / _DEGREES_PER_DAY * 86400.0
    return _jeol_name(target), _find_longitude(target, guess)


def prev_jeol(utc_epoch: float) -> tuple[str, float]:
    """그 순간 직전에 지난 절의 (이름, UTC epoch 초)."""
    lon = solar_longitude_at(utc_epoch)
    past = (lon - 15.0) % 30.0
    target = (lon - past) % 360.0
    guess = utc_epoch - past / _DEGREES_PER_DAY * 86400.0
    return _jeol_name(target), _find_longitude(target, guess)


def day_pillar(solar_epoch: float) -> Pillar:
    """60갑자가 하루씩 끊기지 않고 돈다. 서울 태양시의 날짜로 센다."""
    days = math.floor(solar_epoch / 86400.0)
    idx = (_DAY_ANCHOR_INDEX + (days - _DAY_ANCHOR_DAYS)) % 60
    return Pillar(*_gz(idx))


def hour_branch_of(hour: int) -> int:
    """23~01시가 자시, 01~03시가 축시 ... 두 시간씩."""
    return ((hour + 1) // 2) % 12


def hour_pillar(solar_epoch: float, day_stem: int) -> Pillar:
    """천간은 일간에서 유도한다(오자둔): 갑기일의 자시는 갑자, 을경일은 병자 ...

    23시대(야자시)는 다음 날 자시로 본다. 그래서 일간도 다음 날 것을 쓴다.
    """
    _, _, _, hh, *_ = epoch_to_parts(solar_epoch)
    branch = hour_branch_of(hh)
    stem_base = day_stem
    if hh >= 23:                                   # 야자시 — 다음 날 자시
        stem_base = (day_stem + 1) % 10
    first = (stem_base % 5) * 2                    # 그 날 자시의 천간
    return Pillar((first + branch) % 10, branch)


def elements_count(pillars: list[Pillar]) -> dict[str, int]:
    """여덟 글자를 목화토금수로 세어 본다. 지장간은 아직 넣지 않는다."""
    out = {e: 0 for e in ELEMENTS}
    for p in pillars:
        out[ELEMENTS[STEM_ELEMENT[p.stem]]] += 1
        out[ELEMENTS[BRANCH_ELEMENT[p.branch]]] += 1
    return out


@dataclass(frozen=True)
class Saju:
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar
    utc_epoch: float          # 천문 계산용 (황경·절기·입춘)
    solar_epoch: float        # 서울 태양시 시계 (날짜·시각 읽기)
    correction_minutes: float
    late_night: bool          # 23~24시라 유파에 따라 갈리는가
    hour_edge_minutes: float  # 시주 경계까지 몇 분 남았나

    @property
    def pillars(self) -> list[Pillar]:
        return [self.year, self.month, self.day, self.hour]

    def to_dict(self) -> dict:
        y, mo, d, hh, mi, _ = epoch_to_parts(self.solar_epoch)
        return {
            "year": self.year.to_dict(),
            "month": self.month.to_dict(),
            "day": self.day.to_dict(),
            "hour": self.hour.to_dict(),
            "eightChars": "".join(p.name for p in self.pillars),
            "hanja": " ".join(p.hanja for p in self.pillars),
            "dayStem": STEMS[self.day.stem],
            "elements": elements_count(self.pillars),
            "sign": sign_of(solar_longitude_at(self.utc_epoch)),
            "solarTime": f"{y:04d}-{mo:02d}-{d:02d} {hh:02d}:{mi:02d}",
            "correctionMinutes": round(self.correction_minutes, 1),
            "lateNight": self.late_night,
            "hourEdgeMinutes": round(self.hour_edge_minutes, 1),
        }


def four_pillars_at(utc_epoch: float, solar_epoch: float, correction: float = 0.0) -> Saju:
    """두 시각으로 팔자를 세운다.

    utc_epoch   진짜 UTC 순간. 황경을 구해 입춘·절 경계를 가른다.
    solar_epoch 서울 태양시 시계. 날짜(일주)와 시각(시지)을 읽는다.
    """
    ly, _, _, hh, mi, _ = epoch_to_parts(solar_epoch)
    yp = year_pillar(utc_epoch, ly)
    mp = month_pillar(utc_epoch, yp.stem)
    dp = day_pillar(solar_epoch)
    hp = hour_pillar(solar_epoch, dp.stem)
    # 시지 경계는 홀수 시각(23,01,03,...)에 있다. 홀수 시면 방금 그 지지에
    # 들어온 것이라 다음 경계까지 120-mi, 짝수 시면 한 시간 전에 들어와 60-mi.
    edge = (60 - mi) if hh % 2 == 0 else (120 - mi)
    return Saju(yp, mp, dp, hp, utc_epoch, solar_epoch, correction,
                late_night=hh >= 23, hour_edge_minutes=float(edge))


def four_pillars(y: int, mo: int, d: int, hh: int = 0, mi: int = 0) -> Saju:
    """벽시계 시각(태어난 곳 시계가 가리킨 값)으로 팔자를 세운다."""
    naive = _days_from_civil(y, mo, d) * 86400.0 + hh * 3600.0 + mi * 60.0
    utc = wall_to_utc(y, mo, d, hh, mi)
    solar = seoul_solar_epoch(y, mo, d, hh, mi)
    return four_pillars_at(utc, solar, (solar - naive) / 60.0)


# 프로필의 '태어난 시' 는 12지지 선택지라 정확한 분이 없다. 선택지 구간의
# 한가운데를 쓴다 — 그 구간 표(23:30~01:30 …)가 이미 서울 보정을 머금은
# 벽시계 범위라, 여기에 보정을 걸면 같은 지지로 되돌아온다.
BRANCH_MID_HOUR = {
    "자": (0, 30), "축": (2, 30), "인": (4, 30), "묘": (6, 30),
    "진": (8, 30), "사": (10, 30), "오": (12, 30), "미": (14, 30),
    "신": (16, 30), "유": (18, 30), "술": (20, 30), "해": (22, 30),
}


def _age_years(birth_date: str, today) -> float | None:
    """만나이를 소수로. 대운 구간은 해 단위라 이 정도면 충분하다."""
    if not birth_date or today is None:
        return None
    y, mo, d = (int(x) for x in birth_date.split("-"))
    days = _days_from_civil(today.year, today.month, today.day) - _days_from_civil(y, mo, d)
    return days / 365.2425


def from_profile(profile, today=None) -> dict | None:
    """프로필 -> 화면에 넘길 사주 묶음. 생년월일이 없으면 None.

    태어난 시를 모르면 정오로 세우고 시주는 없는 것으로 표시한다 — 모르는 값을
    아는 척하지 않는다. 일주도 자정 근처를 피해야 해서 정오가 안전하다.
    """
    if not getattr(profile, "birth_date", ""):
        return None
    y, mo, d = (int(x) for x in profile.birth_date.split("-"))

    known = True
    if profile.birth_hour is not None:
        hh, mi = profile.birth_hour, 0
    elif profile.birth_branch:
        hh, mi = BRANCH_MID_HOUR[profile.birth_branch]
    else:
        hh, mi, known = 12, 0, False

    s = four_pillars(y, mo, d, hh, mi)
    out = s.to_dict()
    out["hourKnown"] = known
    out["exactTime"] = profile.birth_hour is not None
    pillars = s.pillars
    if not known:
        out["hour"] = None
        out["eightChars"] = out["eightChars"][:6]
        pillars = [s.year, s.month, s.day]
        out["elements"] = elements_count(pillars)
    # 십신·신살은 여덟 글자를 '나' 중심으로 읽는 층이라 여기서 얹는다.
    # 시주를 모르면 세 기둥으로만 센다 — 모르는 글자를 넣고 세면 답이 달라진다.
    from .sipsin import reading
    out["reading"] = reading(pillars, s.day.stem, out["elements"])
    # 대운은 시간 축이라 '오늘' 이 있어야 지금 어느 칸인지 짚을 수 있다.
    # 성별을 모르면 방향이 안 정해져서 None 이 온다 — 지어내지 않는다.
    from datetime import date as _date
    from .daeun import daeun
    out["daeun"] = daeun(s.year, s.month, s.day.stem, s.utc_epoch,
                         getattr(profile, "gender", ""),
                         _age_years(profile.birth_date, today or _date.today()))
    # 띠(설날 기준)와 사주 년주(입춘 기준)가 갈리는 구간인지
    from .folklore import zodiac_of_birth
    folk = zodiac_of_birth(profile.birth_date, getattr(profile, "lunar", False))
    out["folkZodiac"] = folk
    out["zodiacDiffers"] = bool(folk) and folk != s.year.animal
    return out
