"""대운 — 10년마다 바뀌는 큰 흐름.

팔자는 태어난 순간에 고정된다. 대운은 거기서 시간이 흐르는 축이라, 사람들이
사주에서 가장 자주 다시 보는 자리다("지금 내가 어디쯤인가").

세 가지를 정하면 끝난다. 전부 표와 산수다.

  방향    년간이 양이고 남자, 또는 년간이 음이고 여자면 순행. 반대면 역행.
          여기서만 성별이 필요하다 — 팔자 여덟 글자와 십신은 성별과 무관하다.
  시작    순행이면 태어난 순간부터 '다음' 절입까지, 역행이면 '지난' 절입부터
          태어난 순간까지의 날수를 세어 3일을 1년으로 친다(대운수).
  간지    월주에서 60갑자를 한 칸씩 순행/역행으로 옮긴다. 한 칸이 10년이다.

유파가 갈리는 곳은 대운수의 끝수 처리다. 여기서는 날수를 3으로 나눠 반올림
한다(나머지 1일은 버리고 2일은 올리는 관행과 같은 값). 화면에는 잰 날수를
그대로 함께 적어서, 다른 만세력과 하루 이틀 다를 때 왜 그런지 보이게 했다.
"""

from __future__ import annotations

from .saju import BRANCHES, Pillar, STEM_YIN, STEMS, next_jeol, prev_jeol
from .sipsin import TEN_GOD_TEXT, ten_god, ten_god_of_branch

# 몇 칸까지 보여 줄까. 대운수(1~10)에 80년을 더하면 90 언저리라 한 생애를 덮는다.
COUNT = 8

INTRO = ("대운은 10년마다 바뀌는 큰 흐름입니다. 태어난 달(월주)에서 60갑자를 "
         "한 칸씩 옮겨 가며 정하고, 어느 쪽으로 옮길지는 년간의 음양과 성별로 갈립니다.")
BEFORE_FIRST = "첫 대운에 들기 전까지는 태어난 달(월주)의 기운이 그대로 이어진다고 봅니다."
NO_GENDER = ("대운은 방향이 성별로 갈려서 성별을 알아야 세울 수 있습니다. "
             "프로필에 넣으면 함께 보여 드립니다. 지금 보이는 여덟 글자와 십신은 "
             "성별과 무관하니 그대로입니다.")


def gz_index(pillar: Pillar) -> int:
    """천간·지지 -> 60갑자 번호. 십간과 십이지가 맞물리는 자리는 하나뿐이다."""
    for i in range(60):
        if i % 10 == pillar.stem and i % 12 == pillar.branch:
            return i
    raise ValueError(f"60갑자에 없는 짝: {pillar.name}")


def is_forward(year_stem: int, male: bool) -> bool:
    """순행인가. 년간이 양이고 남자, 또는 년간이 음이고 여자면 순행이다."""
    return (not STEM_YIN[year_stem]) == male


def direction_reason(year_stem: int, male: bool) -> str:
    yin = STEM_YIN[year_stem]
    return (f"년간이 {'음' if yin else '양'}({STEMS[year_stem]})이고 "
            f"{'남자' if male else '여자'}라 {'순행' if is_forward(year_stem, male) else '역행'}입니다")


def start_at(utc_epoch: float, forward: bool) -> dict:
    """대운이 언제부터인가. 절입까지의 날수를 3으로 나눈다.

    3일이 1년이므로 하루는 4개월, 두 시간은 10일이다. 여기서는 초 단위로 잰
    간격을 그대로 나눠서 년·개월까지 낸 다음, 관행대로 반올림한 대운수도 함께 낸다.
    """
    name, target = (next_jeol if forward else prev_jeol)(utc_epoch)
    days = abs(target - utc_epoch) / 86400.0
    years = days / 3.0
    return {
        "jeol": name,
        "days": round(days, 2),
        "years": round(years, 3),
        "number": int(round(years)),          # 화면과 나이 구간에 쓰는 대운수
        "months": int(round(years % 1 * 12)),
    }


def pillars(month: Pillar, forward: bool, count: int = COUNT) -> list[Pillar]:
    """월주에서 한 칸씩. 순행이면 다음 갑자, 역행이면 이전 갑자."""
    base = gz_index(month)
    step = 1 if forward else -1
    return [Pillar((base + step * (k + 1)) % 60 % 10,
                   (base + step * (k + 1)) % 60 % 12) for k in range(count)]


def current_index(number: int, age: float | None, count: int = COUNT) -> int | None:
    """지금 몇 번째 대운인가. 첫 대운 전이거나 표 밖이면 None."""
    if age is None or age < number:
        return None
    k = int((age - number) // 10)
    return k if k < count else None


def daeun(year: Pillar, month: Pillar, day_stem: int,
          utc_epoch: float, gender: str, age: float | None = None) -> dict | None:
    """대운 한 벌. 성별을 모르면 None — 방향을 찍어 맞힐 수는 없다."""
    if gender not in ("남", "여"):
        return None
    male = gender == "남"
    forward = is_forward(year.stem, male)
    start = start_at(utc_epoch, forward)
    now = current_index(start["number"], age)

    rows = []
    for k, p in enumerate(pillars(month, forward)):
        stem_god = ten_god(day_stem, p.stem)
        branch_god = ten_god_of_branch(day_stem, p.branch)
        rows.append({
            "index": k + 1,
            "from": start["number"] + 10 * k,
            "to": start["number"] + 10 * (k + 1),
            "name": p.name,
            "hanja": p.hanja,
            "animal": p.animal,
            "stemGod": stem_god,
            "branchGod": branch_god,
            "word": TEN_GOD_TEXT[stem_god][0],
            "now": now == k,
        })

    out = {
        "forward": forward,
        "reason": direction_reason(year.stem, male),
        "gender": gender,
        "start": start,
        "list": rows,
        "current": rows[now] if now is not None else None,
        "beforeFirst": age is not None and age < start["number"],
    }
    if out["current"]:
        g = out["current"]["stemGod"]
        out["currentText"] = TEN_GOD_TEXT[g][1]
    return out
