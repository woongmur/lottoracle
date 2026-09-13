"""동행복권 로또 용지 QR 코드 파싱.

용지 QR 은 아래 형태의 URL 을 담고 있다::

    https://m.dhlottery.co.kr/qr.do?method=winQr&v=1239m111322323336q010203040506

`v` 값은 [회차][게임]... 구조다.

* 회차 — 앞쪽 연속 숫자 (843회는 '0843' 처럼 0 이 붙기도 한다)
* 게임 — 구분자 한 글자 + 번호 6개(각 2자리). 구분자는 수동/자동/반자동 표시라
  당첨 판정과는 상관이 없어 종류만 읽고 넘긴다.
* 꼬리 — 게임 뒤에 발행 일련번호(용지의 TR 번호)가 숫자로 더 붙는다. 판정에 쓰지
  않지만 버리지 않고 들고 있는다.

처음에는 '게임을 뺀 나머지가 남으면 잘못된 QR' 로 봤는데, 실제 용지에는 저 꼬리가
늘 붙어 있어서 멀쩡한 용지가 전부 거부됐다. 이제는 앞에서부터 게임을 차례로 떼어
내고, 남은 것이 숫자면 일련번호로 본다. 글자가 섞여 있을 때만 거부한다.

QR 리더가 URL 대신 v 값만 주는 경우도 있어서 둘 다 받는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from .metrics import NUMBER_POOL

# 게임 구분자 → 사람이 읽을 이름. 표기가 제보마다 조금씩 달라 모르는 글자는 그대로 둔다.
GAME_KIND = {"m": "수동", "q": "자동", "s": "반자동", "n": "반자동"}
# match(body, pos) 는 그 자리에 앵커된다. \A 를 붙이면 문자열 맨 앞에만 걸려서
# 첫 게임 뒤로 한 발도 못 나간다.
GAME_RE = re.compile(r"([A-Za-z])(\d{12})")
MAX_GAMES = 5  # 용지 한 장은 A~E 다섯 게임


@dataclass(frozen=True)
class Ticket:
    """QR 한 장에서 읽어낸 내용."""

    draw_no: int
    lines: tuple[tuple[int, ...], ...]
    kinds: tuple[str, ...]  # 줄마다 '자동'/'수동'/'반자동'
    serial: str = ""        # 게임 뒤에 붙는 발행 일련번호. 판정에는 쓰지 않는다

    def to_dict(self) -> dict:
        return {
            "draw_no": self.draw_no,
            "lines": [list(row) for row in self.lines],
            "kinds": list(self.kinds),
            "serial": self.serial,
        }


def extract_value(text: str) -> str:
    """QR 문자열에서 v 값을 꺼낸다. URL 이 아니면 문자열 자체를 값으로 본다."""
    text = (text or "").strip()
    if not text:
        raise ValueError("QR 내용이 비어 있습니다.")
    if "://" in text or text.lower().startswith("www."):
        url = urlparse(text if "://" in text else "https://" + text)
        host = url.netloc.lower()
        if "dhlottery" not in host:
            raise ValueError(f"동행복권 QR 이 아닙니다: {host or text[:40]}")
        values = parse_qs(url.query).get("v")
        if not values or not values[0]:
            raise ValueError("QR 주소에 v 값이 없습니다. 로또 용지의 QR 이 맞는지 확인하세요.")
        return values[0].strip()
    if text.lower().startswith("v="):
        return text[2:].strip()
    return text


def parse(text: str) -> Ticket:
    """QR 문자열을 Ticket 으로. 형식이 어긋나면 ValueError."""
    value = extract_value(text)
    head = re.match(r"(\d+)", value)
    if not head:
        raise ValueError("QR 값에서 회차를 읽지 못했습니다.")
    draw_no = int(head.group(1))
    if draw_no <= 0:
        raise ValueError(f"회차 번호가 올바르지 않습니다: {draw_no}")

    # 앞에서부터 차례로 뗀다. 중간에서 끊기면 그 자리가 그대로 꼬리로 남아
    # 아래 검사에 걸린다 — 가운데 게임을 조용히 건너뛰는 일이 없어야 한다.
    body = value[head.end():]
    games: list[tuple[str, str]] = []
    pos = 0
    while (m := GAME_RE.match(body, pos)) is not None:
        games.append((m.group(1), m.group(2)))
        pos = m.end()
    tail = body[pos:]

    if not games:
        raise ValueError("QR 값에서 번호 조합을 읽지 못했습니다. 로또 용지의 QR 이 맞는지 확인하세요.")
    if len(games) > MAX_GAMES:
        raise ValueError(f"한 장에 최대 {MAX_GAMES}게임까지입니다 (읽은 게임 {len(games)}개).")
    if tail and not tail.isdigit():
        # 무엇이 남았는지 적어 둔다. 안 그러면 다음에도 원인을 못 찾는다.
        raise ValueError(f"QR 값에 알 수 없는 문자가 섞여 있습니다: '{tail[:20]}'")

    lines: list[tuple[int, ...]] = []
    kinds: list[str] = []
    for i, (marker, digits) in enumerate(games, start=1):
        nums = tuple(sorted(int(digits[j:j + 2]) for j in range(0, 12, 2)))
        bad = [n for n in nums if n not in NUMBER_POOL]
        if bad:
            raise ValueError(f"{i}번째 게임의 번호가 1~45 범위를 벗어납니다: {bad}")
        if len(set(nums)) != 6:
            raise ValueError(f"{i}번째 게임에 중복된 번호가 있습니다: {list(nums)}")
        lines.append(nums)
        kinds.append(GAME_KIND.get(marker.lower(), "확인불가"))
    return Ticket(draw_no=draw_no, lines=tuple(lines), kinds=tuple(kinds), serial=tail)
