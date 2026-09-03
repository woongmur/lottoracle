/** dhlottery.js — 회차 조회·파싱·병합. 네트워크는 가짜 fetch 로 대체한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as dh from '../src/dhlottery.js';

const ROW = {
  ltEpsd: 1239, tm1WnNo: 11, tm2WnNo: 13, tm3WnNo: 22, tm4WnNo: 32, tm5WnNo: 33, tm6WnNo: 36,
  bnsWnNo: 8, ltRflYmd: '20260829',
  rnk1WnNope: 13, rnk1WnAmt: 2214789375, rnk1SumWnAmt: 28792261875,
  rnk2WnNope: 71, rnk2WnAmt: 67587470, rnk2SumWnAmt: 4798710370,
  rnk3WnNope: 3081, rnk3WnAmt: 1557518, rnk3SumWnAmt: 4798712958,
  rnk4WnNope: 152825, rnk4WnAmt: 50000, rnk4SumWnAmt: 7641250000,
  rnk5WnNope: 2570542, rnk5WnAmt: 5000, rnk5SumWnAmt: 12852710000,
  rlvtEpsdSumNtslAmt: 58883645203,
};
const payload = rows => ({ data: { list: rows } });
const fakeFetch = handler => async url => ({ ok: true, json: async () => handler(url) });

test('추첨일 계산이 맞는다', () => {
  assert.equal(dh.drawDateOf(1), '2002-12-07');
  assert.equal(dh.drawDateOf(2), '2002-12-14');
  assert.equal(dh.drawDateOf(1239), '2026-08-29');
  assert.equal(dh.drawDateOf(1240), '2026-09-05');
});

test('응답을 회차 객체로 파싱한다', () => {
  const d = dh.parsePayload(payload([ROW]));
  assert.equal(d.no, 1239);
  assert.deepEqual(d.numbers, [11, 13, 22, 32, 33, 36]);
  assert.equal(d.bonus, 8);
  assert.equal(d.drawDate, '2026-08-29');
  assert.equal(d.prizes.length, 5);
  assert.deepEqual(d.prizes[0], { rank: 1, winners: 13, amount: 2214789375, total: 28792261875 });
  assert.equal(d.totalSales, 58883645203);
});

test('등수별 총액이 인원×금액과 맞는다', () => {
  for (const p of dh.parsePayload(payload([ROW])).prizes) {
    assert.equal(p.winners * p.amount, p.total, `${p.rank}등`);
  }
});

test('빈 응답은 null (아직 추첨 전)', () => {
  assert.equal(dh.parsePayload(payload([])), null);
  assert.equal(dh.parsePayload({}), null);
  assert.equal(dh.parsePayload(null), null);
});

test('회차를 가져온다', async () => {
  const d = await dh.fetchDraw(1239, { fetchImpl: fakeFetch(() => payload([ROW])) });
  assert.equal(d.no, 1239);
  const latest = await dh.fetchDraw(null, { fetchImpl: fakeFetch(url => {
    assert.ok(!url.includes('srchLtEpsd'), '최신 조회는 파라미터 없이');
    return payload([ROW]);
  }) });
  assert.equal(latest.no, 1239);
});

test('HTTP 오류를 알린다', async () => {
  const bad = async () => ({ ok: false, status: 503, json: async () => ({}) });
  await assert.rejects(() => dh.fetchDraw(1239, { fetchImpl: bad }), /HTTP 503/);
});

test('회차 병합은 번호 기준이고 새 값이 이긴다', () => {
  const old = [{ no: 1, numbers: [1, 2, 3, 4, 5, 6], bonus: 7 }];
  const merged = dh.mergeDraws(old, [
    { no: 1, numbers: [1, 2, 3, 4, 5, 6], bonus: 7, prizes: [{ rank: 1 }] },
    { no: 2, numbers: [7, 8, 9, 10, 11, 12], bonus: 13 },
  ]);
  assert.equal(merged.length, 2);
  assert.equal(merged[0].prizes.length, 1, '새 값으로 덮인다');
  assert.deepEqual(merged.map(d => d.no), [1, 2], '회차 순으로 정렬');
});

test('새 회차만 이어받는다', async () => {
  const have = [{ no: 1237, numbers: [1, 2, 3, 4, 5, 6], bonus: 7 }];
  const make = no => ({ ...ROW, ltEpsd: no });
  const impl = fakeFetch(url => {
    const m = /srchLtEpsd=(\d+)/.exec(url);
    return payload([make(m ? Number(m[1]) : 1240)]);
  });
  const r = await dh.fetchNewDraws(have, { fetchImpl: impl });
  assert.deepEqual(r.added.map(d => d.no), [1238, 1239, 1240]);
  assert.equal(r.newest, 1240);
});

test('이미 최신이면 아무것도 받지 않는다', async () => {
  const have = [{ no: 1239, numbers: [1, 2, 3, 4, 5, 6], bonus: 7 }];
  const r = await dh.fetchNewDraws(have, { fetchImpl: fakeFetch(() => payload([ROW])) });
  assert.deepEqual(r.added, []);
  assert.equal(r.newest, 1239);
});
