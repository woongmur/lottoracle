"""오늘의 운세 — 프로필(이름·생년월일·태어난 시)과 날짜로 결정되는 '기분' 모듈.

확률과는 아무 상관이 없다. 같은 사람은 하루 종일 같은 운세를 본다(날짜+프로필 시드).
문장 규칙:
  * 결과를 약속하지 않는다 — '당첨', '대박' 같은 단어는 금칙어(FORBIDDEN_WORDS)로 막는다.
  * 좋은 날도 단정하지 않고, 나쁜 날도 겁주지 않는다. 나쁜 날은 내일로 이어 준다.
  * 구매를 부추기는 표현을 쓰지 않는다.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .folklore import (
    ZODIAC_NUMBERS,
    ZODIAC_ORDER,
    ball_color,
    birthday_numbers,
    zodiac_numbers,
    zodiac_of_birth,
    zodiac_of_year,
)
from .metrics import NUMBER_POOL

TAGLINE = "숫자는 우연을, 기분은 당신이 정합니다"
DISCLAIMER = (
    "이 서비스의 운세와 추천 번호는 통계적 근거가 없으며 당첨을 보장하지 않습니다. "
    "로또는 매 회차 독립적인 무작위 추첨이고, 1등 확률은 조합과 무관하게 1/8,145,060으로 고정입니다. "
    "지출은 잃어도 괜찮은 금액까지만. 도박문제 상담 국번없이 1336."
)

# 운세 문장에 절대 쓰지 않는 말. 테스트가 모든 템플릿을 검사한다.
FORBIDDEN_WORDS = ("당첨", "대박", "1등", "재물", "횡재", "보장", "반드시", "꼭 ", "구매", "사세요", "사면")

# 등급 1(낮음)~5(높음). 라벨은 어느 쪽으로도 기분을 크게 흔들지 않게.
GRADE_LABELS = {
    5: "기운이 맑은 날",
    4: "흐름이 순한 날",
    3: "고요히 흐르는 날",
    2: "상황을 살피는 날",
    1: "서서히 오르는 조짐",
}
GRADE_WEIGHTS = {5: 2, 4: 3, 3: 3, 2: 2, 1: 1}  # 살짝 낙관적으로

# 등급별 문장. 흐름 / 태도 / 시선 전환 세 갈래를 섞어 패턴이 보이지 않게 한다.
SENTENCES: dict[int, tuple[str, ...]] = {
    5: (
        "막힘 없이 흐르는 하루입니다. 눈에 들어오는 숫자를 가볍게 적어 두세요.",
        "마음이 가는 대로 골라도 괜찮은 날입니다. 오래 고민하지 않아도 됩니다.",
        "숫자보다 사람에게서 좋은 소식이 올 수 있는 날입니다. 연락 한 통이 하루를 바꿉니다.",
        "아침에 떠오른 숫자가 저녁까지 따라다니는 날입니다. 그 느낌을 기억해 두세요.",
    ),
    4: (
        "잔잔하게 잘 풀리는 하루입니다. 평소 좋아하던 숫자를 곁에 두세요.",
        "서두르지 않아도 제자리를 찾는 날입니다. 늘 하던 대로가 답입니다.",
        "가까운 사람과의 대화에서 힌트를 얻는 날입니다.",
        "오늘의 숫자 중 하나가 유난히 눈에 밟힐 수 있습니다. 그냥 지나치지 마세요.",
    ),
    3: (
        "특별할 것 없이 고요한 하루입니다. 평소의 리듬을 지키면 충분합니다.",
        "결정은 가볍게, 기대는 느긋하게 가져가는 날입니다.",
        "숫자보다 오늘 할 일에 집중하면 저녁이 편안해집니다.",
        "잔잔한 물처럼 흐르는 날입니다. 큰 변화보다 작은 정리가 어울립니다.",
    ),
    2: (
        "오늘은 상황을 살피는 날입니다. 내일의 흐름이 더 또렷해집니다.",
        "천천히 가도 좋은 날입니다. 서두른 선택보다 하루 묵힌 선택이 낫습니다.",
        "숫자보다 사람이 잘 풀리는 날입니다. 오늘은 그쪽에 마음을 두세요.",
        "구름이 옅게 낀 하루입니다. 내일 다시 하늘을 올려다보세요.",
    ),
    1: (
        "서서히 운이 오르는 조짐이 보입니다. 오늘은 준비하고 내일을 기다리세요.",
        "쉬어가는 날입니다. 오늘 아낀 기운이 내일의 몫이 됩니다.",
        "숫자와 잠시 거리를 두는 날입니다. 오늘은 사람과 음식에서 기분을 챙기세요.",
        "바닥을 지나 올라오는 길목입니다. 내일 다시 들러 보세요.",
    ),
}

KEYWORDS = ("여유", "호기심", "정리", "기다림", "배려", "집중", "산책", "대화", "휴식", "기록", "온기", "느긋함")
TIPS = (
    "따뜻한 차 한 잔으로 하루를 시작해 보세요.",
    "오래 미뤄 둔 답장을 오늘 보내 보세요.",
    "저녁엔 짧게라도 걸어 보세요.",
    "책상 위를 한 번 정리해 보세요.",
    "좋아하는 노래를 한 곡 끝까지 들어 보세요.",
    "오늘 고마웠던 사람에게 한마디 건네 보세요.",
    "잠들기 전 오늘 좋았던 일 하나를 떠올려 보세요.",
    "점심은 평소보다 천천히 드셔 보세요.",
)

# 태어난 시(時) → 12지지. 요즘 한국 사주에서 통용되는 30분 보정 기준
# (한국 표준시가 동경 135도 기준이라 실제 태양시보다 약 30분 빠른 것을 반영).
HOUR_BRANCHES = ("자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해")
BRANCH_ANIMAL = dict(zip(HOUR_BRANCHES, ("쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지")))
BRANCH_RANGE = {
    "자": "23:30~01:30", "축": "01:30~03:30", "인": "03:30~05:30", "묘": "05:30~07:30",
    "진": "07:30~09:30", "사": "09:30~11:30", "오": "11:30~13:30", "미": "13:30~15:30",
    "신": "15:30~17:30", "유": "17:30~19:30", "술": "19:30~21:30", "해": "21:30~23:30",
}


def branch_of_time(hour: int | None, minute: int = 0) -> str:
    """시:분 → 12지지 한 글자 (30분 보정). None 이면 빈 문자열."""
    if hour is None:
        return ""
    total = (int(hour) * 60 + int(minute) + 30) % 1440
    return HOUR_BRANCHES[total // 120]


def hour_branch(hour: int | None) -> str:
    """정시 기준 12지지. branch_of_time(hour, 0) 과 같다 (하위 호환)."""
    return branch_of_time(hour, 0)


def normalize_branch(text: str | None) -> str:
    """'진', '진시', '용' 같은 입력을 지지 한 글자로. 모르면 빈 문자열, 틀리면 ValueError."""
    token = str(text or "").strip().replace("시", "")
    if not token:
        return ""
    if token in HOUR_BRANCHES:
        return token
    for b, animal in BRANCH_ANIMAL.items():
        if token == animal:
            return b
    raise ValueError(f"태어난 시는 자·축·인·묘·진·사·오·미·신·유·술·해 중 하나여야 합니다: {text}")


def branch_choices() -> list[dict[str, str]]:
    """GUI 선택지: [{value:'자', label:'자시 (23:30~01:30) · 쥐'}, ...]"""
    return [{"value": b, "label": f"{b}시 ({BRANCH_RANGE[b]}) · {BRANCH_ANIMAL[b]}"} for b in HOUR_BRANCHES]


# ------------------------------------------------------------------ 프로필
@dataclass
class Profile:
    """운세와 추천 입력을 함께 채우는 사용자 프로필. 이 기기의 data/ 폴더에만 저장된다."""

    name: str = ""
    birth_date: str = ""          # YYYY-MM-DD
    birth_branch: str = ""        # 태어난 시의 12지지 한 글자 ('진'), 모르면 빈 문자열
    birth_hour: int | None = None  # (하위 호환) 0~23. birth_branch 가 비어 있으면 여기서 유도
    lunar: bool = False           # 생년월일을 음력으로 적었는가 (기본은 양력)

    def __post_init__(self) -> None:
        self.lunar = bool(self.lunar)
        self.name = str(self.name or "").strip()[:20]
        self.birth_date = str(self.birth_date or "").strip()
        if self.birth_date:
            m = re.fullmatch(r"(\d{4})[-./]?(\d{1,2})[-./]?(\d{1,2})", self.birth_date)
            if not m:
                raise ValueError("생년월일은 YYYY-MM-DD 형식으로 입력하세요.")
            y, mo, d = (int(x) for x in m.groups())
            try:
                self.birth_date = date(y, mo, d).isoformat()
            except ValueError as exc:
                raise ValueError(f"생년월일이 올바르지 않습니다: {self.birth_date}") from exc
            if not 1900 <= y <= date.today().year:
                raise ValueError("생년은 1900년 이후여야 합니다.")
        if self.birth_hour in ("", None):
            self.birth_hour = None
        else:
            h = int(self.birth_hour)
            if not 0 <= h <= 23:
                raise ValueError("태어난 시는 0~23 사이여야 합니다.")
            self.birth_hour = h
        self.birth_branch = normalize_branch(self.birth_branch)
        if not self.birth_branch and self.birth_hour is not None:
            self.birth_branch = branch_of_time(self.birth_hour)

    @property
    def is_empty(self) -> bool:
        return not self.birth_date

    @property
    def year(self) -> int | None:
        return int(self.birth_date[:4]) if self.birth_date else None

    @property
    def zodiac(self) -> str:
        return zodiac_of_birth(self.birth_date, self.lunar) if self.year else ""

    @property
    def hour_animal(self) -> str:
        return BRANCH_ANIMAL[self.birth_branch] if self.birth_branch else ""

    @property
    def hour_label(self) -> str:
        """'진시(용)' 같은 표시용 문자열. 모르면 빈 문자열."""
        return f"{self.birth_branch}시({self.hour_animal})" if self.birth_branch else ""

    def personal_numbers(self) -> tuple[int, ...]:
        """띠수 + 생일수 + 태어난 시의 띠수. 추천 입력의 '내 편' 번호."""
        pool: set[int] = set(zodiac_numbers(self.zodiac))
        pool.update(birthday_numbers(self.birth_date))
        if self.hour_animal:
            pool.update(ZODIAC_NUMBERS.get(self.hour_animal, ()))
        return tuple(sorted(n for n in pool if n in NUMBER_POOL))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "birth_date": self.birth_date,
            "birth_branch": self.birth_branch,
            "birth_hour": self.birth_hour,
            "hour_label": self.hour_label,
            "zodiac": self.zodiac,
            "lunar": self.lunar,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "Profile":
        raw = raw or {}
        return cls(
            name=raw.get("name", ""),
            birth_date=raw.get("birth_date", ""),
            birth_branch=raw.get("birth_branch", ""),
            birth_hour=raw.get("birth_hour", None),
            lunar=bool(raw.get("lunar", False)),
        )

    def recommend_inputs(self, today: date | None = None) -> dict[str, Any]:
        """추천 폼에 그대로 넣을 값. 생일·띠는 프로필에서, 행운수는 오늘의 숫자에서."""
        f = daily_fortune(self, today)
        return {"birthday": self.birth_date, "zodiac": self.zodiac, "lucky": list(f.numbers)}


# ------------------------------------------------------------------- 운세
@dataclass
class Fortune:
    date: str
    grade: int
    label: str
    sentence: str
    numbers: tuple[int, ...]
    color: str
    keyword: str
    tip: str
    zodiac: str = ""
    hour_branch: str = ""
    hour_animal: str = ""
    name: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "grade": self.grade,
            "label": self.label,
            "sentence": self.sentence,
            "numbers": list(self.numbers),
            "colors": [ball_color(n) for n in self.numbers],
            "color": self.color,
            "keyword": self.keyword,
            "tip": self.tip,
            "zodiac": self.zodiac,
            "hour_branch": self.hour_branch,
            "hour_animal": self.hour_animal,
            "name": self.name,
            "tags": list(self.tags),
            "tagline": TAGLINE,
        }


def _seed(*parts: Any) -> int:
    text = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _pick_grade(rng: random.Random) -> int:
    grades = list(GRADE_WEIGHTS)
    return rng.choices(grades, weights=[GRADE_WEIGHTS[g] for g in grades], k=1)[0]


def _pick_numbers(rng: random.Random, personal: tuple[int, ...], count: int = 3) -> tuple[int, ...]:
    """오늘의 숫자: 개인 번호에서 1~2개 + 나머지는 무작위. 전부 서로 다르게."""
    chosen: set[int] = set()
    if personal:
        take = min(len(personal), rng.choice((1, 2)))
        chosen.update(rng.sample(personal, take))
    rest = [n for n in NUMBER_POOL if n not in chosen]
    chosen.update(rng.sample(rest, count - len(chosen)))
    return tuple(sorted(chosen))


def daily_fortune(profile: Profile | None, today: date | None = None) -> Fortune:
    """프로필과 날짜로 결정되는 오늘의 운세. 프로필이 비어 있으면 날짜만으로 만든다."""
    today = today or date.today()
    profile = profile or Profile()
    branch = profile.birth_branch
    rng = random.Random(_seed("fortune", today.isoformat(), profile.birth_date, branch, profile.name))
    grade = _pick_grade(rng)
    sentence = rng.choice(SENTENCES[grade])
    numbers = _pick_numbers(rng, profile.personal_numbers())
    color = rng.choice(("노랑", "파랑", "빨강", "회색", "초록"))
    keyword = rng.choice(KEYWORDS)
    tip = rng.choice(TIPS)
    tags: list[str] = []
    if profile.zodiac:
        tags.append(f"{profile.zodiac}띠")
    if branch:
        tags.append(f"{branch}시({profile.hour_animal})생")
    return Fortune(
        date=today.isoformat(),
        grade=grade,
        label=GRADE_LABELS[grade],
        sentence=sentence,
        numbers=numbers,
        color=color,
        keyword=keyword,
        tip=tip,
        zodiac=profile.zodiac,
        hour_branch=branch,
        hour_animal=profile.hour_animal,
        name=profile.name,
        tags=tags,
    )


def zodiac_table(today: date | None = None, exclude: str = "") -> list[dict[str, Any]]:
    """띠로만 보는 오늘. 프로필 없이도 볼 수 있다.

    개인 운세(daily_fortune)와는 씨앗이 달라 서로 다른 결과가 나온다. 같은 화면에서
    두 값이 어긋나 보이지 않도록, 프로필이 있으면 그 띠를 exclude 로 빼고 보여 준다.
    """
    today = today or date.today()
    out = []
    for z in ("쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"):
        if z == exclude:
            continue
        rng = random.Random(_seed("zodiac", today.isoformat(), z))
        grade = _pick_grade(rng)
        sentence = rng.choice(SENTENCES[grade])
        numbers = _pick_numbers(rng, ZODIAC_NUMBERS[z], count=2)
        out.append({
            "zodiac": z,
            "grade": grade,
            "label": GRADE_LABELS[grade],
            "short": sentence.split(". ")[0].rstrip(".") + ".",
            "numbers": list(numbers),
            "colors": [ball_color(n) for n in numbers],
        })
    return out


def all_sentences() -> list[str]:
    """금칙어 검사용: 화면에 나갈 수 있는 모든 문장."""
    out = list(GRADE_LABELS.values())
    for group in SENTENCES.values():
        out.extend(group)
    out.extend(TIPS)
    out.extend(KEYWORDS)
    out.append(TAGLINE)
    return out


def forbidden_hits(text: str) -> list[str]:
    return [w for w in FORBIDDEN_WORDS if w in text]


__all__ = [
    "TAGLINE", "DISCLAIMER", "FORBIDDEN_WORDS", "GRADE_LABELS", "ZODIAC_ORDER",
    "Profile", "Fortune", "daily_fortune", "zodiac_table", "hour_branch", "branch_of_time",
    "normalize_branch", "branch_choices", "BRANCH_RANGE", "BRANCH_ANIMAL",
    "all_sentences", "forbidden_hits",
]
