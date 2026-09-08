/** solartime.js — 시각 보정과 태양황경. 파이썬 lottoracle/solartime.py 와 대조한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as st from '../src/solartime.js';

const G = JSON.parse(readFileSync(new URL('./golden/solartime.json', import.meta.url)));

test('상수와 이름표가 파이썬과 같다', () => {
  assert.equal(st.SEOUL_LONGITUDE, G.seoulLongitude);
  assert.deepEqual(st.SOLAR_TERMS, G.terms);
  assert.deepEqual(st.ZODIAC_SIGNS, G.signs);
  assert.equal(st.SOLAR_TERMS.length, 24);
  assert.equal(st.ZODIAC_SIGNS.length, 12);
});

test('벽시계 -> UTC 와 보정량이 파이썬과 같다', () => {
  for (const c of G.wall) {
    const utc = st.wallToUtc(...c.in);
    assert.ok(Math.abs(utc - c.utc) < 1e-6, `${c.in} utc ${utc} != ${c.utc}`);
    assert.equal(st.utcOffsetAt(utc), c.offset, `${c.in} offset`);
    assert.ok(Math.abs(st.correctionMinutes(...c.in) - c.correctionMinutes) < 1e-6, `${c.in} 보정`);
    assert.deepEqual(st.epochToParts(st.seoulSolarEpoch(...c.in)), c.solarParts, `${c.in} 태양시`);
  }
});

test('태양황경·별자리·절기구간이 파이썬과 같다', () => {
  for (const c of G.longitude) {
    const lon = st.solarLongitudeAt(c.epoch);
    assert.ok(Math.abs(lon - c.value) < 1e-8, `${c.epoch} ${lon} != ${c.value}`);
    assert.equal(st.signOf(lon), c.sign);
    assert.equal(st.termIndex(lon), c.termIndex);
  }
});

test('절기 시각이 파이썬과 1초 안에서 같다', () => {
  for (const [year, rows] of Object.entries(G.termTimes)) {
    const mine = st.solarTermTimes(Number(year));
    assert.equal(mine.length, rows.length);
    rows.forEach(([name, epoch], i) => {
      assert.equal(mine[i][0], name, `${year} ${i}번째 이름`);
      assert.ok(Math.abs(mine[i][1] - epoch) < 1, `${year} ${name} ${mine[i][1]} != ${epoch}`);
    });
  }
});

// ---- 성질 검사 (파이썬 없이도 성립해야 하는 것들)

test('절기는 정확히 15도 배수에서 잡힌다', () => {
  for (const year of [1900, 1987, 2026, 2050]) {
    st.solarTermTimes(year).forEach(([name, epoch], i) => {
      const lon = st.solarLongitudeAt(epoch);
      const want = (i * 15) % 360;
      const gap = ((lon - want + 180) % 360 + 360) % 360 - 180;
      assert.ok(Math.abs(gap) < 1e-4, `${year} ${name} 황경 ${lon}`);
    });
  }
});

test('중기가 별자리 경계와 같다 — 사주와 별자리가 만나는 지점', () => {
  st.solarTermTimes(2026).forEach(([name, epoch], i) => {
    if (i % 2) return;
    const lon = st.solarLongitudeAt(epoch);
    const gap = ((lon + 15) % 30 + 30) % 30 - 15;
    assert.ok(Math.abs(gap) < 1e-4, `${name} ${lon}`);
  });
});

test('절기는 시간순이고 간격이 14.5~16일', () => {
  const times = st.solarTermTimes(2026).map(r => r[1]);
  for (let i = 1; i < times.length; i += 1) assert.ok(times[i] > times[i - 1], `${i}번째 역행`);
  for (let i = 1; i < times.length; i += 1) {
    const gap = (times[i] - times[i - 1]) / 86400;
    assert.ok(gap > 14.5 && gap < 16.0, `간격 ${gap}일`);
  }
});

test('서머타임과 자오선 변경을 빼먹지 않는다', () => {
  // 1987 여름은 UTC+10, 1954~61 은 UTC+8:30. 놓치면 시주가 통째로 어긋난다.
  assert.equal(st.utcOffsetAt(st.wallToUtc(1987, 7, 1, 12, 0)), 36000);
  assert.equal(st.utcOffsetAt(st.wallToUtc(1986, 7, 1, 12, 0)), 32400);
  assert.equal(st.utcOffsetAt(st.wallToUtc(1955, 1, 1, 12, 0)), 30600);
  assert.equal(st.utcOffsetAt(st.wallToUtc(1962, 6, 1, 12, 0)), 32400);
});

test('시기별 보정량', () => {
  const cases = [
    [[1905, 6, 1, 12, 0], 0.0],      // 서울 지방시 — 시계가 곧 태양시
    [[1910, 6, 1, 12, 0], -2.1],     // 동경 127.5도
    [[1930, 6, 1, 12, 0], -32.1],    // 동경 135도
    [[1958, 6, 1, 12, 0], -62.1],    // 127.5도 + 서머타임
    [[1987, 7, 1, 12, 0], -92.1],    // 135도 + 서머타임
    [[2026, 9, 7, 12, 0], -32.1],
  ];
  for (const [args, want] of cases) {
    assert.ok(Math.abs(st.correctionMinutes(...args) - want) < 0.15, `${args} ${st.correctionMinutes(...args)}`);
  }
});

test('날짜와 일수가 왕복한다', () => {
  let seed = 12345;
  const rnd = n => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed % n; };
  for (let i = 0; i < 3000; i += 1) {
    const y = 1800 + rnd(400), m = 1 + rnd(12), d = 1 + rnd(28);
    assert.deepEqual(st.civilFromDays(st.daysFromCivil(y, m, d)), [y, m, d]);
  }
  assert.equal(st.daysFromCivil(1970, 1, 1), 0);
  assert.deepEqual(st.civilFromDays(0), [1970, 1, 1]);
});

test('열두 별자리가 한 해를 덮는다', () => {
  const seen = new Set();
  for (let n = 0; n < 365; n += 3) {
    seen.add(st.signOf(st.solarLongitudeAt(st.daysFromCivil(2026, 1, 1) * 86400 + n * 86400)));
  }
  assert.equal(seen.size, 12);
});

test('황경은 0 이상 360 미만', () => {
  let seed = 99;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  for (let i = 0; i < 2000; i += 1) {
    const lon = st.solarLongitudeAt(-2.3e9 + rnd() * 4.9e9);
    assert.ok(lon >= 0 && lon < 360, `${lon}`);
  }
});
