/** explain.js 가 파이썬 lottoracle.explain 과 같은 문장을 만드는지 대조한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as ex from '../src/explain.js';
import { profile } from '../src/metrics.js';
import { createFolklore } from '../src/folklore.js';

const golden = JSON.parse(readFileSync(new URL('./golden/explain.json', import.meta.url)));
const PREVIOUS = [11, 13, 22, 32, 33, 36];
const PREV_DRAW = { no: 1239, numbers: PREVIOUS, bonus: 8 };
const FL = createFolklore({ lucky: [7, 13], avoid: [4], dream: '돼지꿈', birthday: '1990-05-21', zodiac: '말' });

test('구간 라벨이 같다', () => {
  assert.deepEqual(ex.ZONE_LABELS, golden.zoneLabels);
});

test('구간 문장과 분석 핵심이 파이썬과 같다', () => {
  for (const c of golden.cases) {
    const line = {
      numbers: c.numbers,
      profile: profile(c.numbers, PREVIOUS),
      relaxedStep: c.relaxedStep,
    };
    assert.equal(ex.zonePhrase(c.numbers), c.zonePhrase, `${c.numbers} 구간`);
    assert.equal(ex.analysisNote(line, PREV_DRAW, FL), c.noteWithPrev, `${c.numbers} 분석(직전 있음)`);
    assert.equal(ex.analysisNote(line, null, FL), c.noteNoPrev, `${c.numbers} 분석(직전 없음)`);
    assert.equal(ex.analysisNote(line, PREV_DRAW, null), c.noteNoFolklore, `${c.numbers} 분석(속설 없음)`);
  }
});

test('완화 단계가 문장에 반영된다', () => {
  const nums = [11, 13, 22, 32, 33, 36];
  const mk = step => ({ numbers: nums, profile: profile(nums, PREVIOUS), relaxedStep: step });
  assert.ok(ex.analysisNote(mk(0), PREV_DRAW, FL).includes('평균치 안에 안착'));
  assert.ok(ex.analysisNote(mk(2), PREV_DRAW, FL).includes('완화된 기준으로 통과'));
});
