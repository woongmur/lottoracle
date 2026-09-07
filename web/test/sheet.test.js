/** sheet.js — 한 장의 적중 성적과 그 확률 분포. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { multiplicities, totalDist, sheetSummary } from '../src/sheet.js';

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

function comb(n, k) {
  if (k < 0 || k > n) return 0;
  let r = 1;
  for (let i = 0; i < k; i += 1) r = r * (n - i) / (i + 1);
  return r;
}

test('등장 횟수는 줄 사이 중복을 그대로 센다', () => {
  const m = multiplicities([[1, 2, 3, 4, 5, 6], [1, 2, 7, 8, 9, 10]]);
  assert.equal(m[1], 2);
  assert.equal(m[2], 2);
  assert.equal(m[3], 1);
  assert.equal(m[7], 1);
  assert.equal(m[11], 0);
});

test('한 줄 분포는 초기하분포와 정확히 같다', () => {
  const dist = totalDist([[1, 2, 3, 4, 5, 6]]);
  for (let k = 0; k <= 6; k += 1) {
    close(dist[k], comb(6, k) * comb(39, 6 - k) / comb(45, 6));
  }
  close(dist[0], 3262623 / 8145060, 1e-12);   // 아무것도 못 맞을 확률 40.06%
});

test('분포의 합은 1 이다', () => {
  for (const lines of [
    [[1, 2, 3, 4, 5, 6]],
    [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]],            // 완전히 겹치는 두 줄
    [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]],
  ]) {
    const dist = totalDist(lines);
    close(dist.reduce((a, b) => a + b, 0), 1);
  }
});

test('기대값은 겹침과 무관하게 줄수 × 0.8 이다', () => {
  // E[총 적중] = Σ(등장횟수) × 6/45 = 6L × 6/45 = 0.8L — 선형성이라 겹쳐도 같다
  const cases = [
    [[1, 2, 3, 4, 5, 6]],
    [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]],
    [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [13, 14, 15, 16, 17, 18]],
  ];
  for (const lines of cases) {
    const dist = totalDist(lines);
    let e = 0;
    for (let s = 0; s < dist.length; s += 1) e += s * dist[s];
    close(e, 0.8 * lines.length, 1e-9);
  }
});

test('겹치지 않는 줄들은 초기하분포를 따른다 — 줄별 독립이 아니다', () => {
  // 줄끼리 번호가 안 겹치면 총 적중 수 = 쓴 번호 24개 중 몇 개가 뽑혔나 이므로
  // 초기하분포 H(45, 24, 6) 이다. 줄마다 독립이라 보고 합성곱을 돌리면 틀린다 —
  // 당첨번호는 6개뿐인데 합성곱은 7개, 8개가 나올 여지를 남기기 때문이다.
  const lines = [
    [1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12],
    [13, 14, 15, 16, 17, 18], [19, 20, 21, 22, 23, 24],
  ];
  const dist = totalDist(lines);
  for (let k = 0; k <= 6; k += 1) {
    close(dist[k], comb(6, k) * comb(39, 24 - k) / comb(45, 24), 1e-12);
  }
  // 당첨번호가 6개뿐이니 7개 이상은 불가능하다
  for (let s = 7; s < dist.length; s += 1) close(dist[s], 0, 1e-12);
});

test('겹치는 줄은 분산이 커진다', () => {
  const variance = lines => {
    const d = totalDist(lines);
    const m = d.reduce((a, p, s) => a + s * p, 0);
    return d.reduce((a, p, s) => a + p * (s - m) ** 2, 0);
  };
  const same = variance([[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]]);
  const apart = variance([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]);
  assert.ok(same > apart, `${same} <= ${apart}`);
});

test('실제 한 장을 요약한다 — 1240회', () => {
  const draw = { no: 1240, numbers: [11, 13, 19, 20, 31, 44], bonus: 27 };
  const lines = [
    [1, 8, 12, 19, 34, 44],
    [9, 13, 16, 31, 32, 42],
    [8, 11, 12, 24, 33, 45],
    [2, 3, 22, 39, 40, 45],
    [5, 9, 16, 30, 40, 41],
  ];
  const s = sheetSummary(lines, draw);
  assert.deepEqual(s.perLine, [2, 2, 1, 0, 0]);
  assert.equal(s.total, 5);
  assert.equal(s.best, 2);
  assert.equal(s.lineCount, 5);
  close(s.expected, 4.0, 1e-9);
  // 이번만큼 맞거나 더 맞을 확률 — 평균(4개)보다 위이므로 절반 아래여야 한다
  assert.ok(s.atOrAbove > 0.3 && s.atOrAbove < 0.45, `atOrAbove=${s.atOrAbove}`);
  close(s.atOrAbove + s.atOrBelow, 1 + s.dist[s.total], 1e-9);
});

test('한 줄도 요약된다', () => {
  const draw = { no: 1240, numbers: [11, 13, 19, 20, 31, 44], bonus: 27 };
  const s = sheetSummary([[11, 13, 19, 20, 31, 44]], draw);
  assert.equal(s.total, 6);
  assert.equal(s.best, 6);
  close(s.expected, 0.8, 1e-9);
  close(s.atOrAbove, 1 / comb(45, 6), 1e-12);
});
