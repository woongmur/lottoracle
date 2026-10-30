/** 일본 로또 추천·엔진 — 난수가 개입하므로 값이 아니라 지켜야 할 성질을 본다.
 *
 * (값 대조는 jp_golden.test.js. 여기서는 결정론·번호 범위·규칙 준수·옵션 처리.)
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GAMES, GAME_KEYS, RANK_MATCH, getGame } from '../src/jp/games.js';
import * as gen from '../src/jp/generator.js';
import * as jst from '../src/jp/stats.js';
import * as jmo from '../src/jp/model.js';
import { check } from '../src/jp/filters.js';
import { createWishes } from '../src/jp/folklore.js';
import { strategies } from '../src/jp/strategies.js';
import { createJpEngine, nextDrawDate, parseOptions } from '../src/jp/engine.js';

const raw = Object.fromEntries(GAME_KEYS.map(k => [k,
  JSON.parse(readFileSync(new URL(`../data/jp/${k}.json`, import.meta.url)))]));
const engines = Object.fromEntries(GAME_KEYS.map(k => [k, createJpEngine(k, raw[k])]));

const valid = (game, nums, label) => {
  assert.equal(nums.length, game.pick, `${label}: ${game.pick}개여야 한다`);
  assert.equal(new Set(nums).size, game.pick, `${label}: 중복이 없어야 한다`);
  for (const n of nums) assert.ok(Number.isInteger(n) && n >= 1 && n <= game.pool, `${label}: ${n} 범위 밖`);
  assert.deepEqual(nums, [...nums].sort((a, b) => a - b), `${label}: 오름차순`);
};

for (const key of GAME_KEYS) {
  const game = GAMES[key];
  const engine = engines[key];
  const draws = engine.draws;
  const prev = draws[draws.length - 1];
  const st = jst.build(game, draws, 30);
  const emp = jmo.fit(game, draws);
  const ref = jmo.referenceScores(draws, emp);
  const rules = jmo.calibrate(game, draws, 0.8);
  const base = () => ({ previous: prev, emp, reference: ref, rulesOverride: rules });

  test(`${game.name}: 5줄이 모두 이 게임의 유효한 조합이고 전략이 돈다`, () => {
    const lines = gen.recommend(game, st, { ...base(), seed: 1 });
    const keys = strategies(game).map(s => s.key);
    assert.equal(lines.length, 5);
    lines.forEach((L, i) => {
      valid(game, L.numbers, `${i + 1}줄`);
      assert.equal(L.strategy.key, keys[i]);
      assert.ok(L.percentile >= 0 && L.percentile <= 100);
      assert.equal(L.bonus, undefined, '일본 로또는 보너스를 고르지 않는다');
    });
  });

  test(`${game.name}: 같은 시드는 같은 결과, 다른 시드는 다른 결과`, () => {
    const a = gen.recommend(game, st, { ...base(), seed: 42 }).map(L => L.numbers);
    const b = gen.recommend(game, st, { ...base(), seed: 42 }).map(L => L.numbers);
    const c = gen.recommend(game, st, { ...base(), seed: 43 }).map(L => L.numbers);
    assert.deepEqual(a, b);
    assert.notDeepEqual(a, c);
  });

  test(`${game.name}: 완화 없이 찾은 줄은 적용된 규칙을 통과한다`, () => {
    for (const seed of [1, 2, 3, 7, 11]) {
      for (const L of gen.recommend(game, st, { ...base(), seed })) {
        if (L.relaxedStep !== 0) continue;
        const r = { ...rules, carryoverRange: L.strategy.rules.carryoverRange };
        const v = check(game, L.numbers, r, prev.numbers);
        assert.ok(v.ok, `${L.strategy.key} ${L.numbers}: ${v.violations.join(', ')}`);
      }
    }
  });

  test(`${game.name}: 줄끼리 maxOverlap 을 넘게 겹치지 않는다 (기본은 절반)`, () => {
    for (const seed of [1, 5, 9]) {
      const lines = gen.recommend(game, st, { ...base(), seed, lines: 8 });
      const cap = Math.floor(game.pick / 2);
      for (let i = 0; i < lines.length; i++) {
        for (let j = i + 1; j < lines.length; j++) {
          if (lines[i].relaxedStep >= 3 || lines[j].relaxedStep >= 3) continue;
          const a = new Set(lines[i].numbers);
          assert.ok(lines[j].numbers.filter(n => a.has(n)).length <= cap, `${seed}: ${i}·${j}`);
        }
      }
    }
  });

  test(`${game.name}: 기피수는 절대 안 나오고, 행운수는 범위 밖이면 버린다`, () => {
    const avoid = [1, 2, 3, game.pool];
    const wishes = createWishes({ lucky: [7, 44, 45], avoid });
    for (const seed of [1, 2, 3]) {
      for (const L of gen.recommend(game, st, { ...base(), seed, wishes })) {
        for (const n of avoid) assert.ok(!L.numbers.includes(n), `${seed}: 기피수 ${n}`);
      }
    }
    const opts = parseOptions(game, { lucky: '7 44 45 3', avoid: [] });
    assert.deepEqual(opts.lucky, [3, 7].filter(n => n <= game.pool), '범위 밖 행운수는 조용히 빠진다');
  });

  test(`${game.name}: 범위 밖 기피수는 오류로 알린다`, () => {
    assert.throws(() => parseOptions(game, { avoid: [game.pool + 1] }), /범위/);
    const tooMany = Array.from({ length: game.pool - game.pick + 1 }, (_, i) => i + 1);
    assert.throws(() => parseOptions(game, { avoid: tooMany }), /남지 않습니다/);
  });

  test(`${game.name}: 엔진 추천 화면 값`, () => {
    const r = engine.recommendPayload({ seed: 3 });
    assert.equal(r.game.key, key);
    assert.equal(r.lines.length, 5);
    assert.equal(r.previous.no, prev.no);
    assert.equal(r.next.no, prev.no + 1);
    assert.ok(r.next.date > prev.date, '다음 추첨일은 직전 추첨일 뒤');
    for (const L of r.lines) {
      valid(game, L.numbers, L.strategy);
      assert.ok(L.note.endsWith('.'));
      assert.ok(L.note.includes(`(평균 ${r.game.expectedSum})`));
      assert.ok(L.zones.length > 0);
    }
    assert.deepEqual(r.rules, jmo.calibrate(game, draws, 0.8), '기본은 실데이터 80% 보정');
  });

  test(`${game.name}: 엔진 통계 화면 값`, () => {
    const s = engine.statsPayload();
    assert.equal(s.drawsUsed, draws.length);
    assert.equal(s.frequency.length, game.pool);
    const total = s.frequency.reduce((a, f) => a + f.count, 0);
    assert.equal(total, draws.length * game.pick, '본숫자 출현 합 = 회차 × 개수');
    const bonus = s.frequency.reduce((a, f) => a + f.bonus, 0);
    assert.equal(bonus, draws.length * game.bonus, '보너스 출현 합 = 회차 × 보너스 개수');
    assert.equal(s.lastNo, prev.no);
  });

  test(`${game.name}: 다음 추첨일은 이 게임의 추첨 요일이다`, () => {
    for (const d of draws.slice(-30)) {
      const next = nextDrawDate(game, d.date);
      const wd = (new Date(`${next}T00:00:00Z`).getUTCDay() + 6) % 7;
      assert.ok(game.weekdays.includes(wd), `${d.date} → ${next}`);
      assert.ok(next > d.date);
    }
  });
}

test('로또6 은 월·목, 로또7 은 금, 미니로또는 화', () => {
  assert.equal(nextDrawDate(GAMES.loto6, '2026-10-12'), '2026-10-15');   // 월 → 목
  assert.equal(nextDrawDate(GAMES.loto6, '2026-10-15'), '2026-10-19');   // 목 → 월
  assert.equal(nextDrawDate(GAMES.loto7, '2026-10-09'), '2026-10-16');
  assert.equal(nextDrawDate(GAMES.miniloto, '2026-10-13'), '2026-10-20');
});

test('다른 게임 데이터를 넣으면 막는다', () => {
  assert.throws(() => createJpEngine('loto7', raw.loto6), /loto6/);
  assert.throws(() => getGame('loto8'), /모르는 게임/);
});

test('데이터가 없어도 추천은 된다 (전형성 없이 규칙만)', () => {
  const e = createJpEngine('miniloto', []);
  const r = e.recommendPayload({ seed: 1 });
  assert.equal(r.lines.length, 5);
  assert.equal(r.previous, null);
  assert.equal(r.next, null);
  for (const L of r.lines) valid(GAMES.miniloto, L.numbers, L.strategy);
});

test('등수표는 파이썬과 같고 게임 등수만큼 있다', () => {
  for (const k of GAME_KEYS) assert.equal(RANK_MATCH[k].length, GAMES[k].ranks, k);
  const py = readFileSync(new URL('../../lottoracle/jp/games.py', import.meta.url), 'utf8');
  for (const k of GAME_KEYS) {
    const m = py.match(new RegExp(`"${k}": \\(([^)]*)\\)`));
    assert.ok(m, k);
    assert.deepEqual([...m[1].matchAll(/"([^"]+)"/g)].map(x => x[1]), RANK_MATCH[k], k);
  }
});
