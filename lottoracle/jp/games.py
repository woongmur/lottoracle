"""일본 로또 세 종류의 규칙표.

번호 범위·개수·보너스 개수·등수가 게임마다 다르다. 이 표 하나만 보고 움직이게 해서
'45' 나 '6' 같은 한국 로또 숫자가 일본 쪽 코드에 박히지 않게 한다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Game:
    key: str                  # 파일 이름과 화면 선택값 (loto6 / loto7 / miniloto)
    name: str                 # 화면에 쓰는 한국어 이름
    name_ja: str              # 일본 표기
    pool: int                 # 번호 범위 1~pool
    pick: int                 # 고르는 개수
    bonus: int                # 보너스 숫자 개수
    ranks: int                # 등수 개수
    weekdays: tuple[int, ...]  # 추첨 요일 (월=0 … 일=6)
    carryover: bool           # 이월(キャリーオーバー)이 있는 게임인가


GAMES: dict[str, Game] = {
    "loto6": Game("loto6", "로또6", "ロト6", 43, 6, 1, 5, (0, 3), True),
    "loto7": Game("loto7", "로또7", "ロト7", 37, 7, 2, 6, (4,), True),
    "miniloto": Game("miniloto", "미니로또", "ミニロト", 31, 5, 1, 4, (1,), False),
}


def get(key: str) -> Game:
    try:
        return GAMES[key]
    except KeyError:
        raise ValueError(f"모르는 게임입니다: {key!r} (가능: {', '.join(GAMES)})") from None
