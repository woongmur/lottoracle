# lottoracle web

서버 없이 브라우저에서 도는 버전. 파이썬 패키지(`../lottoracle/`)의 계산 로직을 JS 로 옮긴 것이다.
빌드 도구도 외부 의존성도 없다 — 표준 ES 모듈과 Node 내장 테스트 러너만 쓴다.

```bash
cd web && npm test          # node --test test/*.test.js
```

## 파이썬과 값이 같은지 어떻게 보장하나

`tools/gen_golden.py` 가 파이썬으로 계산한 결과를 `test/golden/*.json` 에 떨구고,
JS 테스트가 같은 입력에 같은 값이 나오는지 대조한다. 파이썬 쪽 로직을 고치면
골든을 다시 생성해서 양쪽을 맞춘다.

```bash
python3 tools/gen_golden.py    # 저장소 루트에서
```

부동소수점은 상대오차 1e-12 로 비교한다. 양쪽 다 IEEE 754 배정밀도라 연산 순서만 같으면
오차가 그 아래로 떨어진다.

### 이식하면서 주의한 것

| 파이썬 | JS | 왜 |
|---|---|---|
| `a // b` | `Math.floor(a / b)` | 구간 나누기(합계/5, 끝수합/3, 폭/4) |
| `round()` | `roundHalfEven()` | 파이썬은 .5 를 짝수로 보낸다. `Math.round` 를 쓰면 백분위가 어긋난다 |
| `Counter` | `Map` | 삽입 순서가 보존돼 `most_common` 동점 순서까지 재현된다 |
| `frozenset((a,b))` | `"3-17"` 문자열 키 | 번호쌍(궁합수) 집계 |
| `tuple(sorted(zones))` | `"0,1,1,2,2"` 문자열 키 | 구간 패턴 분포 |

`random.Random(seed)` 만은 재현할 수 없다. 파이썬은 메르센 트위스터를 쓰는데 JS 에 같은 구현이
없어서, 시드가 같아도 **파이썬판과 JS판은 서로 다른 번호를 뽑는다.** 각각은 여전히 결정론적이라
같은 시드로 같은 결과가 나오고, 기능상 문제는 없다.

## 진행 상황

| 모듈 | 상태 |
|---|---|
| `metrics.js` | 완료 — 골든 대조 |
| `filters.js` | 완료 — 골든 대조 |
| `stats.js` | 완료 — 골든 대조 |
| `model.js` | 완료 — 골든 대조 |
| `rng.js` | 완료 — 시드 결정론·분포 검사 |
| `folklore.js` | 완료 — 골든 대조 |
| `strategies.js` | 완료 — 골든 대조 |
| `generator.js` | 완료 — 성질 기반 검사 (난수라 값 대조 불가) |
| `fortune.js` | 완료 — 문구·프로필은 골든 대조, 운세 생성은 성질 검사 |
| `explain.js` | 완료 — 골든 대조 |
| `grade.js` | 완료 — 실제 당첨금·평균치 양쪽 |
| `qr.js` | 완료 — 거절 경로까지 |
| `engine.js` (조합·저장소) | 예정 |
| UI (`index.html`) · PWA · 배포 | 예정 |

## public/

| 파일 | 내용 |
|---|---|
| `privacy.html` | 개인정보처리방침. 앱 스토어 등록에 URL 이 필요하고, 광고를 붙이면 더 중요해진다 |
