/** engine.js — 화면이 쓰는 서비스 계층 전체를 실제 회차 데이터로 검사한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createEngine, parseOptions } from '../src/engine.js';
import { createStorage } from '../src/storage.js';

const draws = JSON.parse(readFileSync(new URL('../data/draws.json', import.meta.url)));
const WIN = [11, 13, 22, 32, 33, 36];

const memStorage = () => {
  const map = new Map();
  return createStorage({
    getItem: k => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: k => map.delete(k),
  });
};
const freshEngine = () => createEngine(draws, memStorage());

test('폼 값을 검증된 옵션으로 바꾼다', () => {
  const o = parseOptions({ lines: '3', lucky: '7 13', avoid: '4,9', coverage: '0.9', seed: '' });
  assert.equal(o.lines, 3);
  assert.deepEqual(o.lucky, [7, 13]);
  assert.deepEqual(o.avoid, [4, 9]);
  assert.equal(o.coverage, 0.9);
  assert.equal(o.seed, null);
  assert.equal(parseOptions({}).lines, 5, '기본값');
});

test('범위를 벗어난 값은 잘라 넣는다', () => {
  assert.equal(parseOptions({ lines: 999 }).lines, 20);
  assert.equal(parseOptions({ lines: 0 }).lines, 1);
  assert.equal(parseOptions({ coverage: 2 }).coverage, 0.99);
  assert.equal(parseOptions({ temperature: 0 }).temperature, 0.05);
  assert.equal(parseOptions({ maxOverlap: 99 }).maxOverlap, 6);
});

test('범위 밖 번호는 거절한다', () => {
  assert.throws(() => parseOptions({ lucky: '0 7' }), /1~45 범위/);
  assert.throws(() => parseOptions({ avoid: '46' }), /1~45 범위/);
});

test('추천 결과에 화면이 필요한 값이 모두 있다', () => {
  const r = freshEngine().recommendPayload({ seed: 7 });
  assert.equal(r.lines.length, 5);
  assert.equal(r.previous.no, 1239);
  assert.equal(r.nextDrawNo, 1240);
  assert.equal(r.nextDrawDate, '2026-09-05');
  assert.equal(r.drawsUsed, draws.length);
  for (const L of r.lines) {
    assert.equal(L.numbers.length, 6);
    assert.equal(L.colors.length, 6);
    assert.ok(L.note.endsWith('.'), '분석 문장');
    assert.ok(L.metrics.includes('합계'));
    assert.ok(L.zones.length > 0);
    assert.ok(L.omens.length > 0);
    assert.ok(L.percentile >= 0 && L.percentile <= 100);
  }
});

test('같은 시드는 같은 추천을 준다', () => {
  const a = freshEngine().recommendPayload({ seed: 11 });
  const b = freshEngine().recommendPayload({ seed: 11 });
  assert.deepEqual(a.lines.map(L => L.numbers), b.lines.map(L => L.numbers));
});

test('전략을 골라 쓸 수 있다', () => {
  const r = freshEngine().recommendPayload({ seed: 2, lines: 2, strategies: ['aggressive'] });
  assert.equal(r.lines.length, 2);
  for (const L of r.lines) assert.equal(L.strategy, 'aggressive');
});

test('속설을 끄면 그렇게 알린다', () => {
  const r = freshEngine().recommendPayload({ seed: 1, folklore: false });
  assert.deepEqual(r.folklore, ['속설 로직 끔']);
});

test('통계 페이로드가 화면 규격에 맞는다', () => {
  const s = freshEngine().statsPayload(30, 0.8);
  assert.equal(s.drawsUsed, draws.length);
  assert.equal(s.firstNo, 1);
  assert.equal(s.lastNo, 1239);
  assert.equal(s.frequency.length, 45);
  assert.equal(s.hot.length, 10);
  assert.equal(s.cold.length, 10);
  assert.ok(s.meanSum > 130 && s.meanSum < 145, `합 평균이 이상하다: ${s.meanSum}`);
  assert.ok(s.calibratedRules.sumRange[0] < s.calibratedRules.sumRange[1]);
  for (const d of s.odd) assert.ok(d.ratio >= 0 && d.ratio <= 1);
});

test('회차 목록은 최신순이고 당첨금을 담는다', () => {
  const rows = freshEngine().drawsPayload(5);
  assert.equal(rows.length, 5);
  assert.equal(rows[0].no, 1239);
  assert.ok(rows[0].no > rows[1].no, '최신순');
  assert.equal(rows[0].hasPrizes, true);
  assert.equal(rows[0].prizes.length, 5);
});

test('채점이 실제 당첨금으로 계산된다', () => {
  const r = freshEngine().gradePayload([WIN, [1, 2, 3, 4, 5, 7]], 1239);
  assert.equal(r.results[0].label, '1등');
  assert.equal(r.results[1].label, '낙첨');
  assert.equal(r.bestRank, 1);
  assert.equal(r.actualPrize, true);
  assert.equal(r.results[0].prize, 2214789375);
});

test('잘못된 조합·없는 회차는 거절한다', () => {
  const eng = freshEngine();
  assert.throws(() => eng.gradePayload([[1, 1, 2, 3, 4, 5]], 1239), /서로 다른 번호 6개/);
  assert.throws(() => eng.gradePayload([WIN], 99999), /데이터가 없습니다/);
});

test('QR 채점과 미추첨 구분', () => {
  const eng = freshEngine();
  assert.equal(eng.qrPayload('1239m111322323336').status, 'graded');
  assert.equal(eng.qrPayload('1239m111322323336').bestRank, 1);
  const pending = eng.qrPayload('1250m010203040506');
  assert.equal(pending.status, 'pending');
  assert.equal(pending.latestDraw, 1239);
});

test('프로필 저장·운세·삭제가 이어진다', () => {
  const eng = freshEngine();
  assert.equal(eng.fortunePayload(null, '2026-09-03').hasProfile, false);
  eng.saveProfile({ name: '홍길동', birthDate: '1990-05-21', birthBranch: '진' });
  const f = eng.fortunePayload(null, '2026-09-03');
  assert.equal(f.hasProfile, true);
  assert.equal(f.profile.zodiac, '말');
  assert.equal(f.profile.hourLabel, '진시(용)');
  assert.equal(f.zodiacTable.length, 11, '내 띠는 표에서 뺀다');
  assert.equal(f.recommendInputs.birthday, '1990-05-21');
  assert.deepEqual(f.recommendInputs.lucky, f.fortune.numbers);
  assert.equal(f.nextDrawNo, 1240);
  eng.clearProfile();
  assert.equal(eng.fortunePayload(null, '2026-09-03').hasProfile, false);
});

test('생년월일 없이 저장하면 거절한다', () => {
  assert.throws(() => freshEngine().saveProfile({ name: '홍길동' }), /생년월일을 입력하세요/);
});

test('내 번호가 추첨 후 자동 채점된다', () => {
  const eng = freshEngine();
  eng.addPick([WIN], 1239, '테스트');
  eng.addPick([[1, 2, 3, 4, 5, 6]], 1240);
  const picks = eng.picksPayload();
  assert.equal(picks[0].targetDraw, 1240, '목표 회차 내림차순');
  assert.equal(picks[0].results, null, '추첨 전이면 채점하지 않는다');
  assert.equal(picks[1].bestRank, 1);
  assert.equal(picks[1].totalPrize, 2214789375);
  assert.ok(eng.deletePick(picks[1].id));
  assert.equal(eng.picksPayload().length, 1);
});

test('저장 시 목표 회차를 생략하면 다음 회차로 잡는다', () => {
  const eng = freshEngine();
  assert.equal(eng.addPick([WIN]).targetDraw, 1240);
});

test('데이터가 없어도 죽지 않는다', () => {
  const eng = createEngine([], memStorage());
  assert.equal(eng.previous, null);
  assert.deepEqual(eng.statsPayload(), { drawsUsed: 0 });
  assert.deepEqual(eng.drawsPayload(5), []);
  const r = eng.recommendPayload({ seed: 1, lines: 2, calibrate: false });
  assert.equal(r.lines.length, 2);
  assert.equal(r.previous, null);
  assert.equal(r.nextDrawNo, null);
});

test('갱신 실패는 예외 대신 결과로 알린다', async () => {
  const eng = freshEngine();
  const r = await eng.refresh({ fetchImpl: async () => { throw new Error('네트워크 없음'); } });
  assert.equal(r.ok, false);
  assert.match(r.error, /네트워크 없음/);
  assert.equal(r.after, 1239, '기존 데이터는 그대로');
});

test('갱신 성공 시 새 회차가 붙는다', async () => {
  const eng = freshEngine();
  const fake = async url => ({
    ok: true,
    json: async () => {
      const m = /srchLtEpsd=(\d+)/.exec(url);
      const no = m ? Number(m[1]) : 1240;
      return { data: { list: [{
        ltEpsd: no, tm1WnNo: 1, tm2WnNo: 2, tm3WnNo: 3, tm4WnNo: 4, tm5WnNo: 5, tm6WnNo: 6,
        bnsWnNo: 7, ltRflYmd: '20260905', rnk1WnNope: 1, rnk1WnAmt: 100, rnk1SumWnAmt: 100,
      }] } };
    },
  });
  const r = await eng.refresh({ fetchImpl: fake });
  assert.equal(r.ok, true);
  assert.equal(r.added, 1);
  assert.equal(r.after, 1240);
  assert.equal(eng.previous.no, 1240);
  assert.equal(eng.recommendPayload({ seed: 1 }).nextDrawNo, 1241, '캐시가 갱신된다');
});
