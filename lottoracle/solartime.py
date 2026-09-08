"""태어난 시각을 서울 평균태양시로 옮기고, 태양황경으로 절기와 별자리를 구한다.

명리학에서 시주는 '시계가 가리킨 값' 이 아니라 그 자리의 태양 위치로 정한다.
그래서 두 가지를 보정한다.

1) 표준시 이력 — 한국은 표준 자오선이 여러 번 바뀌었고 서머타임도 12차례 있었다.
   tzhistory.py 의 표(IANA tz 원본)로 그 시점의 오프셋을 찾아 UTC 로 되돌린다.
2) 경도 — 서울은 동경 약 127도라 동경 135도 표준시보다 태양이 32분 늦게 뜬다.

이 둘은 사실 한 번에 처리된다. 벽시계 시각을 UTC 로 되돌리면 그 시대에 무슨
자오선을 썼든 상관없어지고, 거기에 서울 경도만큼 더하면 서울 평균태양시다.

    서울 평균태양시 = UTC + 서울경도/15 시간

균시차(진태양시와 평균태양시의 차, ±16분)는 넣지 않는다. 한국 만세력의
일반적인 관행을 따른 것이다. 대신 시주 경계에 가까우면 화면에서 알려 준다.
"""

from __future__ import annotations

import math
from bisect import bisect_right

from .tzhistory import KST_TRANSITIONS

# 서울시청 기준. 만세력마다 126°58'~127° 사이를 쓰는데 그 차이는 3초 남짓이라
# 시주 판정에 영향을 주지 않는다.
SEOUL_LONGITUDE = 126.9784
SEOUL_LMT_SECONDS = SEOUL_LONGITUDE / 15.0 * 3600.0   # 약 8시간 27분 55초

_TZ_AT = [t for t, _ in KST_TRANSITIONS]
_TZ_OFF = [o for _, o in KST_TRANSITIONS]

SOLAR_TERMS = (
    "춘분", "청명", "곡우", "입하", "소만", "망종",
    "하지", "소서", "대서", "입추", "처서", "백로",
    "추분", "한로", "상강", "입동", "소설", "대설",
    "동지", "소한", "대한", "입춘", "우수", "경칩",
)
# 12궁은 황경 0도(춘분)부터 30도씩. 절기 중 짝수 번째(중기)와 경계가 같다.
ZODIAC_SIGNS = (
    "양자리", "황소자리", "쌍둥이자리", "게자리", "사자자리", "처녀자리",
    "천칭자리", "전갈자리", "궁수자리", "염소자리", "물병자리", "물고기자리",
)


def utc_offset_at(epoch: float) -> int:
    """그 순간 한국이 쓰던 UTC 오프셋(초)."""
    i = bisect_right(_TZ_AT, epoch) - 1
    return _TZ_OFF[max(0, i)]


def wall_to_utc(y: int, mo: int, d: int, hh: int = 0, mi: int = 0) -> float:
    """벽시계 시각(그때 그 자리 시계가 가리킨 값) -> UTC epoch 초.

    오프셋이 시각에 달려 있어 한 번에 못 구한다. 후보 오프셋을 넣어 보고
    앞뒤가 맞는 것을 고른다. 서머타임이 끝나 같은 시각이 두 번 오는 구간은
    앞쪽(서머타임이 아직 걸린 쪽)을, 서머타임이 시작해 건너뛴 구간은
    전환 직전 오프셋을 쓴다.
    """
    naive = _days_from_civil(y, mo, d) * 86400.0 + hh * 3600.0 + mi * 60.0
    best = None
    for cand in _candidate_offsets(naive):
        utc = naive - cand
        if utc_offset_at(utc) == cand:
            if best is None or utc < best:      # 겹치면 이른 쪽
                best = utc
    if best is not None:
        return best
    # 건너뛴 구간: 전환 직전 오프셋으로 밀어 준다
    return naive - utc_offset_at(naive - _TZ_OFF[0])


def _candidate_offsets(naive: float) -> list[int]:
    seen: list[int] = []
    for off in _TZ_OFF:
        i = bisect_right(_TZ_AT, naive - off) - 1
        o = _TZ_OFF[max(0, i)]
        if o not in seen:
            seen.append(o)
    return seen


def seoul_solar_epoch(y: int, mo: int, d: int, hh: int = 0, mi: int = 0) -> float:
    """벽시계 시각 -> 서울 평균태양시를 나타내는 epoch 초.

    돌려주는 값은 '서울 태양시로 읽었을 때의 시각' 을 UTC epoch 처럼 담은 것이라,
    그대로 시/분으로 풀면 보정된 시각이 나온다.
    """
    return wall_to_utc(y, mo, d, hh, mi) + SEOUL_LMT_SECONDS


def correction_minutes(y: int, mo: int, d: int, hh: int = 0, mi: int = 0) -> float:
    """벽시계 대비 몇 분을 옮겼는지. 화면에 설명할 때 쓴다."""
    naive = _days_from_civil(y, mo, d) * 86400.0 + hh * 3600.0 + mi * 60.0
    return (seoul_solar_epoch(y, mo, d, hh, mi) - naive) / 60.0


# --------------------------------------------------------------- 달력 셈
def _days_from_civil(y: int, m: int, d: int) -> int:
    """1970-01-01 부터의 일수. Howard Hinnant 의 civil_from_days 역함수."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z: int) -> tuple[int, int, int]:
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return y + (m <= 2), m, d


def epoch_to_parts(epoch: float) -> tuple[int, int, int, int, int, int]:
    days = math.floor(epoch / 86400.0)
    rest = epoch - days * 86400.0
    y, m, d = civil_from_days(int(days))
    hh = int(rest // 3600)
    mi = int((rest - hh * 3600) // 60)
    ss = int(rest - hh * 3600 - mi * 60)
    return y, m, d, hh, mi, ss


def julian_day(epoch: float) -> float:
    """UTC epoch 초 -> 율리우스일. 윤초는 무시한다(사주에 무의미한 크기)."""
    return epoch / 86400.0 + 2440587.5


# ------------------------------------------------------------- 태양황경
def solar_longitude(jd: float) -> float:
    """겉보기 태양황경(도, 0~360). Meeus 천문알고리즘 25장.

    태양은 하루에 약 0.986도 움직인다. 절기와 별자리 경계를 분 단위로 가르려면
    0.001도 수준이 필요해서, 기본 식에 주요 섭동항을 더했다.
    """
    t = (jd - 2451545.0) / 36525.0
    rad = math.radians

    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    mr = rad(m)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr)
         + 0.000289 * math.sin(3 * mr))
    true_long = l0 + c

    # 금성·목성·달이 만드는 주요 섭동 (Meeus 25장 주석)
    a1 = rad(351.52 + 22518.7541 * t)
    a2 = rad(253.14 + 45037.5082 * t)
    a3 = rad(157.23 + 32964.4678 * t)
    a4 = rad(297.85 + 445267.1115 * t)
    a5 = rad(252.08 + 20.190 * t)
    a6 = rad(31.80 + 45036.8840 * t)
    true_long += (0.00134 * math.cos(a1) + 0.00154 * math.cos(a2)
                  + 0.00200 * math.cos(a3) + 0.00179 * math.sin(a4)
                  + 0.00178 * math.sin(a5) + 0.00090 * math.cos(a6))

    omega = rad(125.04 - 1934.136 * t)
    apparent = true_long - 0.00569 - 0.00478 * math.sin(omega)
    return apparent % 360.0


def solar_longitude_at(epoch: float) -> float:
    return solar_longitude(julian_day(epoch))


def _find_longitude(target: float, guess: float) -> float:
    """태양황경이 target 도가 되는 순간(UTC epoch 초).

    고정 폭 구간을 잡고 이분법을 돌리면 안 된다. 절기 간격은 14.7~15.7일로
    변해서(지구 궤도가 타원이라 근일점 근처에서 빨리 움직인다) 등간격으로
    추정하면 근이 구간 밖에 놓이는 일이 생긴다.

    태양은 하루 약 0.9856도씩 거의 단조증가하므로, 남은 각도만큼 시간을
    밀어 주는 방식으로 먼저 근처까지 간 다음 이분법으로 다듬는다.
    """
    def diff(e: float) -> float:
        return (solar_longitude_at(e) - target + 180.0) % 360.0 - 180.0

    e = guess
    for _ in range(20):
        d = diff(e)
        if abs(d) < 1e-6:
            return e
        e -= d / 0.98564736 * 86400.0        # 남은 각도 -> 시간

    # 다듬기: 부호가 갈리는 좁은 구간을 만들어 이분법
    lo, hi = e - 3600.0, e + 3600.0
    flo, fhi = diff(lo), diff(hi)
    grow = 0
    while flo * fhi > 0 and grow < 12:       # 혹시 못 감쌌으면 넓힌다
        lo -= 3600.0
        hi += 3600.0
        flo, fhi = diff(lo), diff(hi)
        grow += 1
    if flo * fhi > 0:
        return e
    for _ in range(60):
        mid = (lo + hi) / 2
        fm = diff(mid)
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
        if hi - lo < 0.5:
            break
    return (lo + hi) / 2


def solar_term_times(year: int) -> list[tuple[str, float]]:
    """그해 절기 24개의 (이름, UTC epoch 초). 춘분(황경 0도)부터 15도 간격."""
    out = []
    for i, name in enumerate(SOLAR_TERMS):
        deg = (i * 15) % 360
        # 춘분 ~ 3/20 에서 시작해 15도마다 약 15.2일
        guess = _days_from_civil(year, 3, 20) * 86400.0 + i * 15.218 * 86400.0
        out.append((name, _find_longitude(deg, guess)))
    return out


def term_index(longitude: float) -> int:
    """황경 -> 절기 구간 번호(0=춘분 구간)."""
    return int(longitude // 15) % 24


def sign_of(longitude: float) -> str:
    """황경 -> 12궁. 춘분 0도가 양자리 시작."""
    return ZODIAC_SIGNS[int(longitude // 30) % 12]
