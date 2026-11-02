/** 일본 로또 당첨 확인 — 등수 규칙과 당첨금. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { GAMES, GAME_KEYS, RANK_MATCH } from '../src/jp/games.js';
import { RANK_RULES, rankOf, gradeLines, lineError } from '../src/jp/grade.js';

const L6 = { numbers: [1, 2, 14, 18, 35, 38], bonus: [33],
  prizes: [[0, 0], [5, 12673400], [193, 354500], [8865, 8100], [149443, 1000]] };
const L7 = { numbers: [2, 3, 8, 12, 21, 25, 26], bonus: [13, 34],
  prizes: [[0, 0], [12, 4926400], [160, 425600], [7063, 5800], [105312, 1300], [163424, 1000]] };
const MINI = { numbers: [17, 18, 26, 28, 30], bonus: [23],
  prizes: [[7, 22223700], [73, 153000], [1452, 13300], [43642, 1100]] };

test('등수표는 게임 등수 수와 같고 일치 조건 글자와 맞는다', () => {
  for (const k of GAME_KEYS) {
    assert.equal(RANK_RULES[k].length, GAMES[k].ranks, k);
    RANK_RULES[k].forEach(([h, b], i) => {
      assert.match(RANK_MATCH[k][i], new RegExp(`^${h}개`), `${k} ${i + 1}등`);
      assert.equal(RANK_MATCH[k][i].includes('보너스'), b > 0, `${k} ${i + 1}등 보너스`);
    });
  }
});

test('로또6 등수', () => {
  assert.equal(rankOf('loto6', [1, 2, 14, 18, 35, 38], L6), 1);
  assert.equal(rankOf('loto6', [1, 2, 14, 18, 35, 33], L6), 2);   // 5개 + 보너스
  assert.equal(rankOf('loto6', [1, 2, 14, 18, 35, 40], L6), 3);
  assert.equal(rankOf('loto6', [1, 2, 14, 18, 40, 41], L6), 4);
  assert.equal(rankOf('loto6', [1, 2, 14, 33, 40, 41], L6), 5);   // 3개 (보너스는 상관없음)
  assert.equal(rankOf('loto6', [1, 2, 33, 40, 41, 42], L6), 0);
});

test('로또7 등수 — 보너스 둘 중 하나면 된다, 6등은 3개 + 보너스', () => {
  assert.equal(rankOf('loto7', [2, 3, 8, 12, 21, 25, 26], L7), 1);
  assert.equal(rankOf('loto7', [2, 3, 8, 12, 21, 25, 34], L7), 2);
  assert.equal(rankOf('loto7', [2, 3, 8, 12, 21, 25, 37], L7), 3);
  assert.equal(rankOf('loto7', [2, 3, 8, 12, 21, 36, 37], L7), 4);
  assert.equal(rankOf('loto7', [2, 3, 8, 12, 35, 36, 37], L7), 5);
  assert.equal(rankOf('loto7', [2, 3, 8, 13, 35, 36, 37], L7), 6);
  assert.equal(rankOf('loto7', [2, 3, 8, 33, 35, 36, 37], L7), 0);  // 3개인데 보너스 없음
});

test('미니로또 등수', () => {
  assert.equal(rankOf('miniloto', [17, 18, 26, 28, 30], MINI), 1);
  assert.equal(rankOf('miniloto', [17, 18, 26, 28, 23], MINI), 2);
  assert.equal(rankOf('miniloto', [17, 18, 26, 28, 1], MINI), 3);
  assert.equal(rankOf('miniloto', [17, 18, 26, 1, 2], MINI), 4);
  assert.equal(rankOf('miniloto', [17, 18, 1, 2, 3], MINI), 0);
});

test('당첨금은 그 회차 1게임당 금액, 당첨자 0 인 등수는 모름', () => {
  const r = gradeLines('loto6', L6, [[1, 2, 14, 18, 35, 33], [1, 2, 14, 18, 40, 41], [3, 4, 5, 6, 7, 8], [1, 2, 14, 18, 35, 38]]);
  assert.deepEqual(r.results.map(x => x.rank), [2, 4, 0, 1]);
  assert.deepEqual(r.results.map(x => x.prize), [12673400, 8100, 0, null]);
  assert.equal(r.bestRank, 1);
  assert.equal(r.prizesKnown, false);
  const noPrizes = gradeLines('miniloto', { ...MINI, prizes: [] }, [[17, 18, 26, 1, 2]]);
  assert.equal(noPrizes.results[0].prize, null);
});

test('입력 검사', () => {
  assert.equal(lineError('loto7', [1, 2, 3, 4, 5, 6, 7]), null);
  assert.match(lineError('loto7', [1, 2, 3, 4, 5, 6]), /7개/);
  assert.match(lineError('miniloto', [1, 2, 3, 4, 32]), /1~31/);
  assert.match(lineError('loto6', [1, 1, 2, 3, 4, 5]), /두 번/);
});
