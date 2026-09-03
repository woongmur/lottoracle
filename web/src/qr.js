/** 동행복권 로또 용지 QR 코드 파싱.
 *
 * 용지 QR 은 아래 형태의 URL 을 담고 있다:
 *   https://m.dhlottery.co.kr/qr.do?method=winQr&v=1239m111322323336q010203040506
 *
 * v 값은 [회차][게임]... 구조다.
 *  - 회차: 앞쪽 연속 숫자 (843회는 '0843' 처럼 0 이 붙기도 한다)
 *  - 게임: 구분자 한 글자 + 번호 6개(각 2자리). 구분자는 수동/자동 표시라 판정과 무관하다.
 *
 * QR 리더가 URL 대신 v 값만 주는 경우도 있어서 둘 다 받는다.
 * (웹 GUI 는 번호 직접 입력을 쓰고, 이 파서는 앱의 카메라 스캔용이다.)
 */
import { NUMBER_POOL } from './metrics.js';

// 게임 구분자 → 사람이 읽을 이름. 표기가 제보마다 조금씩 달라 모르는 글자는 그대로 둔다.
export const GAME_KIND = { m: '수동', q: '자동', s: '반자동', n: '반자동' };
export const MAX_GAMES = 5;   // 용지 한 장은 A~E 다섯 게임

/** QR 문자열에서 v 값을 꺼낸다. URL 이 아니면 문자열 자체를 값으로 본다. */
export function extractValue(text) {
  const raw = String(text ?? '').trim();
  if (!raw) throw new Error('QR 내용이 비어 있습니다.');
  if (raw.includes('://') || raw.toLowerCase().startsWith('www.')) {
    const url = new URL(raw.includes('://') ? raw : `https://${raw}`);
    if (!url.hostname.toLowerCase().includes('dhlottery')) {
      throw new Error(`동행복권 QR 이 아닙니다: ${url.hostname || raw.slice(0, 40)}`);
    }
    const v = url.searchParams.get('v');
    if (!v) throw new Error('QR 주소에 v 값이 없습니다. 로또 용지의 QR 이 맞는지 확인하세요.');
    return v.trim();
  }
  if (raw.toLowerCase().startsWith('v=')) return raw.slice(2).trim();
  return raw;
}

/** QR 문자열을 {drawNo, lines, kinds} 로. 형식이 어긋나면 예외. */
export function parse(text) {
  const value = extractValue(text);
  const head = /^(\d+)/.exec(value);
  if (!head) throw new Error('QR 값에서 회차를 읽지 못했습니다.');
  const drawNo = Number(head[1]);
  if (drawNo <= 0) throw new Error(`회차 번호가 올바르지 않습니다: ${drawNo}`);

  const body = value.slice(head[0].length);
  const games = [...body.matchAll(/([A-Za-z])(\d{12})/g)];
  if (!games.length) {
    throw new Error('QR 값에서 번호 조합을 읽지 못했습니다. 로또 용지의 QR 이 맞는지 확인하세요.');
  }
  if (games.length > MAX_GAMES) {
    throw new Error(`한 장에 최대 ${MAX_GAMES}게임까지입니다 (읽은 게임 ${games.length}개).`);
  }
  if (body.replace(/([A-Za-z])(\d{12})/g, '')) {
    throw new Error('QR 값에 알 수 없는 문자가 섞여 있습니다.');
  }

  const lines = [], kinds = [];
  games.forEach(([, marker, digits], i) => {
    const nums = [];
    for (let j = 0; j < 12; j += 2) nums.push(Number(digits.slice(j, j + 2)));
    nums.sort((a, b) => a - b);
    const bad = nums.filter(n => !NUMBER_POOL.includes(n));
    if (bad.length) {
      throw new Error(`${i + 1}번째 게임의 번호가 1~45 범위를 벗어납니다: ${bad.join(', ')}`);
    }
    if (new Set(nums).size !== 6) {
      throw new Error(`${i + 1}번째 게임에 중복된 번호가 있습니다: ${nums.join(', ')}`);
    }
    lines.push(nums);
    kinds.push(GAME_KIND[marker.toLowerCase()] || '확인불가');
  });
  return { drawNo, lines, kinds };
}
