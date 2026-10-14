/** web/src/jp/ 가 파이썬 lottoracle/jp 와 같은 값을 내는지 골든 데이터로 대조한다.
 *
 * 골든은 tools/gen_golden.py 가 web/data/jp 의 실제 회차로 만든다. 일본 회차가 늘면
 * update-jp 워크플로가 골든을 다시 만들고 이 테스트를 돌린다.
 * 부동소수점은 상대오차로 비교한다 (같은 IEEE 754 연산이라 오차는 극히 작아야 한다).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GAMES, GAME_KEYS } from '../src/jp/games.js';
import * as jm from '../src/jp/metrics.js';
import * as jf from '../src/jp/filters.js';
import * as js from '../src/jp/stats.js';
import * as jmo from '../src/jp/model.js';
import * as jsg from '../src/jp/strategies.js';
import * as jx from '../src/jp/explain.js';
import * as jl from '../src/jp/folklore.js';

const load = name => JSON.parse(readFileSync(new URL(`./golden/jp_${name}.json`, import.meta.url)));
const G = {
  metrics: load('metrics'), filters: load('filters'), stats: load('stats'),
  model: load('model'), strategies: load('strategies'), explain: load('explain'),
};
const draws = Object.fromEntries(GAME_KEYS.map(k => [k,
  JSON.parse(readFileSync(new URL(`../data/jp/${k}.json`, import.meta.url))).draws]));

const near = (a, b, label, eps = 1e-12) => {
  const scale = Math.max(1, Math.abs(a), Math.abs(b));
  assert.ok(Math.abs(a - b) / scale < eps, `${label}: ${a} != ${b}`);
};
const mapObj = map => Object.fromEntries([...map.entries()].sort((a, b) => a[0] - b[0]).map(([k, v]) => [String(k), v]));

for (const key of GAME_KEYS) {
  const game = GAMES[key];
  const ds = draws[key];

  test(`${game.name}: 게임 규칙표와 파생값이 파이썬과 같다`, () => {
    const g = G.metrics[key];
    assert.deepEqual(
      { pool: game.pool, pick: game.pick, bonus: game.bonus, ranks: game.ranks,
        weekdays: game.weekdays, carryover: game.carryover, name: game.name, nameJa: game.nameJa },
      g.game);
    assert.equal(jm.lowMax(game), g.lowMax);
    assert.deepEqual(jm.zoneBounds(game), g.zoneBounds);
    assert.deepEqual(jm.twinNumbers(game), g.twins);
    assert.equal(jm.expectedSum(game), g.expectedSum);
    assert.equal(jm.maxSum(game), g.maxSum);
    assert.equal(jm.maxAc(game), g.maxAc);
  });

  test(`${game.name}: 지표가 파이썬과 같다`, () => {
    const g = G.metrics[key];
    for (const c of g.cases) {
      const { summary: s1, ...want1 } = c.noPrev;
      const { summary: s2, ...want2 } = c.withPrev;
      const p1 = jm.profile(game, c.numbers);
      const p2 = jm.profile(game, c.numbers, g.previous);
      assert.deepEqual(p1, want1, `${c.numbers}`);
      assert.deepEqual(p2, want2, `${c.numbers} (직전 있음)`);
      assert.equal(jm.summary(p1), s1);
      assert.equal(jm.summary(p2), s2);
    }
  });

  test(`${game.name}: 필터 기본값·완화·판정이 파이썬과 같다`, () => {
    const g = G.filters[key];
    const base = jf.defaultRules(game);
    assert.deepEqual(base, g.base);
    for (const [step, want] of Object.entries(g.relaxed)) {
      assert.deepEqual(jf.relaxed(game, base, Number(step)), want, `완화 ${step}단계`);
    }
    for (const c of g.cases) {
      const v = jf.check(game, c.numbers, base, G.metrics[key].previous);
      assert.deepEqual({ ok: v.ok, violations: v.violations }, c.verdict, `${c.numbers}`);
    }
  });

  test(`${game.name}: 번호 통계가 파이썬과 같다`, () => {
    const g = G.stats[key];
    const st = js.build(game, ds, g.recentWindow);
    assert.equal(st.drawsUsed, g.drawsUsed);
    near(js.meanFrequency(st), g.meanFrequency, '평균 출현');
    const pool = jm.numberPool(game);
    const full = map => Object.fromEntries(pool.map(n => [String(n), map.get(n) || 0]));
    assert.deepEqual(full(st.frequency), g.frequency);
    assert.deepEqual(full(st.recent), g.recent);
    assert.deepEqual(full(st.gap), g.gap);
    assert.deepEqual(full(st.bonusFrequency), g.bonusFrequency);
    assert.deepEqual(js.hot(st, 10), g.hot10);
    assert.deepEqual(js.cold(st, 10), g.cold10);
    assert.deepEqual(js.companions(st, 7, 6), g.companionsOf7);
    for (const [pair, want] of Object.entries(g.pairSamples)) {
      const [a, b] = pair.split('-').map(Number);
      assert.equal(st.pairs.get(js.pairKey(a, b)) || 0, want, pair);
    }
    const ps = js.profileStats(game, ds);
    const w = g.profileStats;
    assert.equal(ps.count, w.count);
    near(ps.meanSum, w.meanSum, '합계 평균');
    assert.deepEqual(ps.sumRange80, w.sumRange80);
    assert.deepEqual(mapObj(ps.oddDistribution), w.oddDistribution);
    assert.deepEqual(mapObj(ps.lowDistribution), w.lowDistribution);
    assert.deepEqual(mapObj(ps.acDistribution), w.acDistribution);
    near(ps.endSumMean, w.endSumMean, '끝수합 평균');
    near(ps.consecutiveRatio, w.consecutiveRatio, '연속 비율');
    assert.deepEqual(mapObj(ps.carryoverDistribution), w.carryoverDistribution);
  });

  test(`${game.name}: 보정 규칙·평활 확률·전형성이 파이썬과 같다`, () => {
    const g = G.model[key];
    const emp = jmo.fit(game, ds);
    const ref = jmo.referenceScores(ds, emp);
    assert.equal(emp.count, g.empCount);
    assert.deepEqual(jmo.supports(game), {
      total: g.supports.total, odd: g.supports.odd, low: g.supports.low, ac: g.supports.ac,
      endSum: g.supports.end_sum, consecutive: g.supports.consecutive, zone: g.supports.zone,
      carryover: g.supports.carryover, spread: g.supports.spread, position: g.supports.position,
    });
    for (const [cov, want] of Object.entries(g.calibrated)) {
      assert.deepEqual(jmo.calibrate(game, ds, Number(cov)), want, `coverage ${cov}`);
    }
    const p = g.probes;
    const one = (fn, table, label) => {
      for (const [v, want] of Object.entries(table)) near(fn(emp, Number(v)), want, `${label}(${v})`);
    };
    one(jmo.pTotal, p.pTotal, 'pTotal');
    one(jmo.pOdd, p.pOdd, 'pOdd');
    one(jmo.pLow, p.pLow, 'pLow');
    one(jmo.pAc, p.pAc, 'pAc');
    one(jmo.pEndSum, p.pEndSum, 'pEndSum');
    one(jmo.pConsecutive, p.pConsecutive, 'pConsecutive');
    one(jmo.pCarryover, p.pCarryover, 'pCarryover');
    one(jmo.pSpread, p.pSpread, 'pSpread');
    for (const [z, want] of Object.entries(p.pZone)) near(jmo.pZone(emp, z.split('-').map(Number)), want, `pZone(${z})`);
    for (const [k, want] of Object.entries(p.pPosition)) {
      const [i, n] = k.split('-').map(Number);
      near(jmo.pPosition(emp, i, n), want, `pPosition(${k})`);
    }
    const prev = G.metrics[key].previous;
    for (const c of g.typicality) {
      near(jmo.typicality(c.numbers, emp), c.noPrev, `${c.numbers} 점수`);
      const withPrev = jmo.typicality(c.numbers, emp, prev);
      near(withPrev, c.withPrev, `${c.numbers} 점수(직전 있음)`);
      near(jmo.typicalityPercentile(withPrev, ref), c.percentile, `${c.numbers} 백분위`);
    }
    assert.equal(ref.length, g.referenceStats.count);
    near(ref[0], g.referenceStats.min, '최솟값');
    near(ref[ref.length - 1], g.referenceStats.max, '최댓값');
    near(ref[Math.floor(ref.length / 2)], g.referenceStats.median, '중앙값');
  });

  test(`${game.name}: 전략 다섯이 파이썬과 같다`, () => {
    const got = jsg.strategies(game).map(s => ({
      key: s.key, name: s.name, concept: s.concept, wFrequency: s.wFrequency, wRecent: s.wRecent,
      wGap: s.wGap, wCompanion: s.wCompanion, wTwin: s.wTwin,
      carryoverTarget: s.carryoverTarget, usePrevBonus: s.usePrevBonus, rules: s.rules,
    }));
    assert.deepEqual(got, G.strategies[key]);
  });

  test(`${game.name}: 속설 가중과 분석 문장이 파이썬과 한 글자도 다르지 않다`, () => {
    const g = G.explain[key];
    const prev = g.previous;
    const wishes = jl.createWishes({ lucky: [7, 13, 44], avoid: [4] });
    assert.deepEqual([...jl.neighborNumbers(game, prev)].sort((a, b) => a - b), g.neighbors);
    assert.deepEqual(mapObj(jl.multipliers(game, wishes, prev)), g.multipliers);
    for (const c of g.cases) {
      assert.equal(jx.zonePhrase(game, c.numbers), c.zonePhrase, `${c.numbers} 구간`);
      assert.equal(jx.analysisNote(game, c.numbers, 0, prev, wishes), c.noteWithPrev, `${c.numbers}`);
      assert.equal(jx.analysisNote(game, c.numbers, 2, prev, wishes), c.noteRelaxed, `${c.numbers} 완화`);
      assert.equal(jx.analysisNote(game, c.numbers, 0, null, wishes), c.noteNoPrev, `${c.numbers} 직전 없음`);
      assert.equal(jx.analysisNote(game, c.numbers, 0, prev, null), c.noteNoWishes, `${c.numbers} 행운수 없음`);
    }
  });
}

test('골든에 세 게임이 다 들어 있다', () => {
  for (const name of Object.keys(G)) assert.deepEqual(Object.keys(G[name]).sort(), [...GAME_KEYS].sort(), name);
});
