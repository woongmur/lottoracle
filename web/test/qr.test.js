/** qr.js — 동행복권 용지 QR 파싱. 파이썬 lottoracle.qr 과 같은 판정을 해야 한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as qr from '../src/qr.js';

const URL_FORM = 'https://m.dhlottery.co.kr/qr.do?method=winQr&v=1239m111322323336q010203040506';

test('URL 형태를 읽는다', () => {
  const t = qr.parse(URL_FORM);
  assert.equal(t.drawNo, 1239);
  assert.deepEqual(t.lines, [[11, 13, 22, 32, 33, 36], [1, 2, 3, 4, 5, 6]]);
  assert.deepEqual(t.kinds, ['수동', '자동']);
});

test('v 값만 줘도 읽고, 앞자리 0 회차도 처리한다', () => {
  assert.equal(qr.parse('0843m192130333442').drawNo, 843);
  assert.deepEqual(qr.parse('v=1239q111322323336').lines[0], [11, 13, 22, 32, 33, 36]);
});

test('번호를 오름차순으로 정렬한다', () => {
  assert.deepEqual(qr.parse('1239m363332221311').lines[0], [11, 13, 22, 32, 33, 36]);
});

test('5게임까지 허용하고 6게임은 거절한다', () => {
  const game = 'm010203040506';
  assert.equal(qr.parse('1239' + game.repeat(5)).lines.length, 5);
  assert.throws(() => qr.parse('1239' + game.repeat(6)), /최대 5게임/);
});

test('잘못된 입력을 모두 거절한다', () => {
  const bad = [
    ['', /비어 있습니다/],
    ['   ', /비어 있습니다/],
    ['https://example.com/?v=1239m010203040506', /동행복권 QR 이 아닙니다/],
    ['https://m.dhlottery.co.kr/qr.do?method=winQr', /v 값이 없습니다/],
    ['1239', /번호 조합을 읽지 못했습니다/],
    ['1239m111322323346', /1~45 범위를 벗어납니다/],
    ['1239m000102030405', /1~45 범위를 벗어납니다/],
    ['1239m111111111111', /중복된 번호/],
    ['1239m01020304050', /번호 조합을 읽지 못했습니다/],
    ['1239m010203040506ZZ', /알 수 없는 문자/],
  ];
  for (const [input, pattern] of bad) {
    assert.throws(() => qr.parse(input), pattern, `거절해야 함: "${input}"`);
  }
});

test('모르는 구분자는 확인불가로 남긴다', () => {
  assert.deepEqual(qr.parse('1239x010203040506').kinds, ['확인불가']);
});
