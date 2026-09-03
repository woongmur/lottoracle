/** generator.js — 난수가 개입하므로 값이 아니라 '지켜야 할 성질'을 검사한다.
 *
 * 파이썬판과 같은 시드로 같은 번호가 나오지는 않는다(메르센 트위스터를 재현할 수 없다).
 * 대신 결정론·규칙 준수·제약 반영을 확인한다.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as gen from '../src/generator.js';
import * as stats from '../src/stats.js';
import * as model from '../src/model.js';
import { check, defaultRules } from '../src/filters.js';
import { createFolklore } from '../src/folklore.js';
import { byKey, DEFAULT_STRATEGIES } from '../src/strategies.js';
import { createRng } from '../src/rng.js';
import { PICK } from '../src/metrics.js';

const draws = JSON.parse(readFileSync(new URL('../data/draws.json', import.meta.url)));
const st = stats.build(draws, 30);
const emp = model.fit(draws);
const ref = model.referenceScores(draws, emp);
const PREV = draws[draws.length - 1];
const RULES = model.calibrate(draws, 0.8);

const baseOpts = () => ({ previous: PREV, emp, reference: ref, rulesOverride: RULES });
const validCombo = (nums, label) => {
  assert.equal(nums.length, PICK, `${label}: 6개여야 한다`);
  assert.equal(new Set(nums).size, PICK, `${label}: 중복이 없어야 한다`);
  for (const n of nums) assert.ok(Number.isInteger(n) && n >= 1 && n <= 45, `${label}: ${n} 범위 밖`);
  assert.deepEqual(nums, [...nums].sort((a, b) => a - b), `${label}: 오름차순이어야 한다`);
};

test('5줄이 모두 유효한 조합이다', () => {
  const lines = gen.recommend(st, { ...baseOpts(), seed: 1 });
  assert.equal(lines.length, 5);
  lines.forEach((L, i) => {
    validCombo(L.numbers, `${i + 1}줄`);
    assert.ok(L.bonus >= 1 && L.bonus <= 45, '보너스 범위');
    assert.ok(!L.numbers.includes(L.bonus), '보너스는 당첨번호와 겹치지 않는다');
    assert.equal(L.strategy.key, DEFAULT_STRATEGIES[i].key, '전략이 순환한다');
    assert.ok(L.luck >= 0 && L.luck <= 100, '기분점수 범위');
    assert.ok(L.percentile >= 0 && L.percentile <= 100, '백분위 범위');
  });
});

test('같은 시드는 같은 결과를 낸다', () => {
  const a = gen.recommend(st, { ...baseOpts(), seed: 42 });
  const b = gen.recommend(st, { ...baseOpts(), seed: 42 });
  assert.deepEqual(a.map(L => [L.numbers, L.bonus]), b.map(L => [L.numbers, L.bonus]));
});

test('다른 시드는 다른 결과를 낸다', () => {
  const a = gen.recommend(st, { ...baseOpts(), seed: 1 });
  const b = gen.recommend(st, { ...baseOpts(), seed: 2 });
  assert.notDeepEqual(a.map(L => L.numbers), b.map(L => L.numbers));
});

test('시드를 안 주면 매번 달라진다', () => {
  const runs = Array.from({ length: 5 }, () => gen.recommend(st, { ...baseOpts(), lines: 1 })[0].numbers);
  assert.ok(new Set(runs.map(String)).size > 1, '시드 없이 같은 결과만 나온다');
});

test('뽑힌 조합은 적용된 규칙을 통과한다 (완화 없이 찾은 줄에 한해)', () => {
  for (const seed of [1, 2, 3, 7, 11]) {
    for (const L of gen.recommend(st, { ...baseOpts(), seed })) {
      if (L.relaxedStep !== 0) continue;
      const rules = { ...RULES, carryoverRange: L.strategy.rules.carryoverRange };
      const v = check(L.numbers, rules, PREV.numbers);
      assert.ok(v.ok, `${L.strategy.key} ${L.numbers}: ${v.violations.join(', ')}`);
    }
  }
});

test('줄끼리 maxOverlap 을 넘게 겹치지 않는다', () => {
  for (const seed of [1, 5, 9]) {
    const lines = gen.recommend(st, { ...baseOpts(), seed, maxOverlap: 2 });
    for (let i = 0; i < lines.length; i++) {
      for (let j = i + 1; j < lines.length; j++) {
        const a = new Set(lines[i].numbers);
        const overlap = lines[j].numbers.filter(n => a.has(n)).length;
        // 완화 3단계 이상으로 찾은 줄은 제한이 풀린다
        if (lines[i].relaxedStep < 3 && lines[j].relaxedStep < 3) {
          assert.ok(overlap <= 2, `${i + 1}·${j + 1}줄이 ${overlap}개 겹침`);
        }
      }
    }
  }
});

test('기피수는 절대 나오지 않는다', () => {
  const folklore = createFolklore({ avoid: [4, 13, 22, 33, 44, 7, 8, 9, 10] });
  for (const seed of [1, 2, 3]) {
    for (const L of gen.recommend(st, { ...baseOpts(), seed, folklore })) {
      for (const bad of folklore.avoid) {
        assert.ok(!L.numbers.includes(bad), `${L.numbers} 에 기피수 ${bad}`);
        assert.notEqual(L.bonus, bad, `보너스에 기피수 ${bad}`);
      }
    }
  }
});

test('기피수가 40개면 조합을 못 만들고 명확히 실패한다', () => {
  const folklore = createFolklore({ avoid: Array.from({ length: 41 }, (_, i) => i + 1) });
  assert.throws(() => gen.recommend(st, { ...baseOpts(), seed: 1, folklore }),
    /조합을 찾지 못했습니다|뽑을 번호가 남지 않았습니다/);
});

test('이월수 전략은 직전 회차 번호를 실제로 물고 온다', () => {
  const prevSet = new Set(PREV.numbers);
  let withCarryover = 0;
  for (const seed of [1, 2, 3, 4, 5]) {
    const L = gen.generateLine(byKey('carryover'), st, {
      ...baseOpts(), rng: createRng(seed),
      rulesOverride: { ...RULES, carryoverRange: [1, 3] },
    });
    if (L.numbers.filter(n => prevSet.has(n)).length >= 1) withCarryover++;
  }
  assert.ok(withCarryover >= 4, `이월수가 거의 안 붙었다 (${withCarryover}/5)`);
});

test('공격형은 이월수를 끊는다', () => {
  const prevSet = new Set(PREV.numbers);
  for (const seed of [1, 2, 3]) {
    const L = gen.generateLine(byKey('aggressive'), st, {
      ...baseOpts(), rng: createRng(seed),
      rulesOverride: { ...RULES, carryoverRange: [0, 0] },
    });
    if (L.relaxedStep === 0) {
      assert.equal(L.numbers.filter(n => prevSet.has(n)).length, 0, `${L.numbers} 에 이월수`);
    }
  }
});

test('과거 데이터가 없어도 규칙 필터만으로 동작한다', () => {
  const emptyStats = stats.build([], 30);
  const lines = gen.recommend(emptyStats, { lines: 3, seed: 1, rulesOverride: defaultRules() });
  assert.equal(lines.length, 3);
  lines.forEach((L, i) => {
    validCombo(L.numbers, `${i + 1}줄`);
    assert.equal(L.percentile, 50.0, '근거가 없으면 백분위는 50');
  });
});

test('온도를 낮추면 더 전형적인 조합으로 쏠린다', () => {
  const avg = temp => {
    const runs = [1, 2, 3, 4, 5, 6, 7, 8].map(seed =>
      gen.generateLine(byKey('balance'), st, { ...baseOpts(), rng: createRng(seed), temperature: temp }).percentile);
    return runs.reduce((a, b) => a + b, 0) / runs.length;
  };
  assert.ok(avg(0.1) > avg(3.0), '낮은 온도가 더 전형적이어야 한다');
});

test('줄 수를 늘려도 전략이 순환하며 계속 유효하다', () => {
  const lines = gen.recommend(st, { ...baseOpts(), seed: 8, lines: 12 });
  assert.equal(lines.length, 12);
  lines.forEach((L, i) => {
    validCombo(L.numbers, `${i + 1}줄`);
    assert.equal(L.strategy.key, DEFAULT_STRATEGIES[i % 5].key);
  });
});

test('속설을 켜면 용지 직선 모양이 나오지 않는다', () => {
  const folklore = createFolklore({});
  for (const seed of [1, 2, 3, 4]) {
    for (const L of gen.recommend(st, { ...baseOpts(), seed, folklore })) {
      if (L.relaxedStep < 3) {
        assert.ok(L.omens.length > 0, '속설 태그가 붙어야 한다');
      }
    }
  }
});
