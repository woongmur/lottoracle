/** 한 장(여러 줄)의 적중 성적을 확률 분포와 함께 설명한다.
 *
 * 낙첨만 던지고 끝내면 "몇 개나 맞았는지"가 안 보인다. 그렇다고 맞은 개수만
 * 크게 띄우면 실제보다 잘한 것처럼 읽힌다 — 여러 줄에 넓게 뿌리면 뭔가는
 * 걸리기 때문이다. 그래서 적중 수와 함께 그 장의 기대값과 분포상 위치를
 * 같이 준다. 맥락이 붙어야 부풀리지 않고 사실을 전할 수 있다.
 *
 * 여기서 계산하는 값은 저장하지 않는다. 화면을 그릴 때마다 다시 구한다.
 */

const POOL = 45;   // 1~45
const PICK = 6;    // 한 회차에 뽑는 개수

/** 번호별 등장 횟수. 같은 번호가 여러 줄에 들어가면 그만큼 더 센다. */
export function multiplicities(lines) {
  const mult = new Array(POOL + 1).fill(0);
  for (const row of lines) {
    for (const n of row) {
      const v = Number(n);
      if (Number.isInteger(v) && v >= 1 && v <= POOL) mult[v] += 1;
    }
  }
  return mult;
}

/**
 * 총 적중 개수의 정확한 분포. 반환값 dist[t] = 총 t 개가 맞을 확률.
 *
 * 추첨은 45개에서 6개를 고르는 균등 추첨이다. 그러므로 총 적중 수는
 * "번호별 등장 횟수" 중 6개를 비복원으로 뽑아 더한 값과 정확히 같다.
 * 줄끼리 번호가 겹쳐도(같은 번호를 두 줄에 쓰면 등장 횟수가 2) 그대로 반영된다.
 *
 * 6개 선택 × 합계로 배낭 DP 를 돌리면 근사 없이 분포가 나온다.
 * 경우의 수 합은 C(45,6)=8,145,060 이라 배정밀도로 오차 없이 담긴다.
 */
export function totalDist(lines) {
  const mult = multiplicities(lines);
  const maxSum = lines.length * PICK;
  // dp[c][s] = 서로 다른 번호 c 개를 골라 등장 횟수 합이 s 가 되는 경우의 수
  const dp = Array.from({ length: PICK + 1 }, () => new Float64Array(maxSum + 1));
  dp[0][0] = 1;
  for (let n = 1; n <= POOL; n += 1) {
    const w = mult[n];
    // c 를 내림차순으로 돌아야 같은 번호를 두 번 세지 않는다
    for (let c = PICK; c >= 1; c -= 1) {
      const from = dp[c - 1], to = dp[c];
      for (let s = 0; s + w <= maxSum; s += 1) {
        if (from[s]) to[s + w] += from[s];
      }
    }
  }
  const ways = dp[PICK];
  let total = 0;
  for (const v of ways) total += v;
  return Array.from(ways, v => (total ? v / total : 0));
}

/**
 * 한 장의 성적 요약.
 *
 * atOrAbove = 이번만큼 맞거나 더 맞을 확률. "상위 몇 %" 로 쓴다.
 * atOrBelow = 이번 이하로 맞을 확률.
 */
export function sheetSummary(lines, draw) {
  const winning = new Set(draw.numbers);
  const perLine = lines.map(row => row.filter(n => winning.has(n)).length);
  const total = perLine.reduce((a, b) => a + b, 0);
  const dist = totalDist(lines);

  let expected = 0;
  for (let s = 0; s < dist.length; s += 1) expected += s * dist[s];
  let atOrAbove = 0;
  for (let s = total; s < dist.length; s += 1) atOrAbove += dist[s];
  let atOrBelow = 0;
  for (let s = 0; s <= total && s < dist.length; s += 1) atOrBelow += dist[s];

  return {
    lineCount: lines.length,
    perLine,
    total,
    best: perLine.length ? Math.max(...perLine) : 0,
    expected,
    atOrAbove,
    atOrBelow,
    dist,
  };
}
