/** 동행복권 회차 조회. 브라우저에서 직접 호출한다 (이 API 는 CORS 를 허용한다).
 *
 * 응답 예:
 *   {"data": {"list": [{"ltEpsd": 1239, "tm1WnNo": 11, ..., "bnsWnNo": 8,
 *                       "ltRflYmd": "20260829", "rnk1WnNope": 13, "rnk1WnAmt": 2214789375,
 *                       "rnk1SumWnAmt": 28792261875, ..., "rlvtEpsdSumNtslAmt": 58883645203}]}}
 */
export const API_URL = 'https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do';
export const FIRST_DRAW_DATE = '2002-12-07';   // 1회차 추첨일 (토요일)

/** 회차 번호로 추첨일을 계산한다 (매주 토요일). */
export function drawDateOf(no) {
  const first = new Date(`${FIRST_DRAW_DATE}T00:00:00`);
  first.setDate(first.getDate() + (no - 1) * 7);
  const pad = n => String(n).padStart(2, '0');
  return `${first.getFullYear()}-${pad(first.getMonth() + 1)}-${pad(first.getDate())}`;
}

/** 오늘 날짜 기준으로 존재할 법한 최신 회차 번호를 추정한다. */
export function estimateLatestDrawNo(today = new Date()) {
  const first = new Date(`${FIRST_DRAW_DATE}T00:00:00`);
  const weeks = Math.floor((today - first) / (7 * 24 * 3600 * 1000));
  return Math.max(1, weeks + 1);
}

/** 응답 JSON 을 회차 객체로. 아직 추첨 전이면 null. */
export function parsePayload(payload) {
  const items = payload?.data?.list;
  if (!Array.isArray(items) || !items.length) return null;
  const row = items[0];
  const ymd = String(row.ltRflYmd || '');
  const prizes = [];
  for (let rank = 1; rank <= 5; rank++) {
    if (row[`rnk${rank}WnNope`] === undefined) continue;
    prizes.push({
      rank,
      winners: Number(row[`rnk${rank}WnNope`] || 0),
      amount: Number(row[`rnk${rank}WnAmt`] || 0),
      total: Number(row[`rnk${rank}SumWnAmt`] || 0),
    });
  }
  const numbers = [];
  for (let i = 1; i <= 6; i++) numbers.push(Number(row[`tm${i}WnNo`]));
  return {
    no: Number(row.ltEpsd),
    numbers: numbers.sort((a, b) => a - b),
    bonus: Number(row.bnsWnNo),
    drawDate: ymd.length === 8 ? `${ymd.slice(0, 4)}-${ymd.slice(4, 6)}-${ymd.slice(6, 8)}` : ymd,
    prizes,
    totalSales: Number(row.rlvtEpsdSumNtslAmt ?? -1),
  };
}

/** 한 회차를 가져온다. 번호를 생략하면 최신 회차. 아직 추첨 전이면 null. */
export async function fetchDraw(no = null, { timeout = 10000, fetchImpl = null } = {}) {
  const doFetch = fetchImpl || globalThis.fetch;
  const url = no === null ? API_URL : `${API_URL}?srchLtEpsd=${encodeURIComponent(no)}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await doFetch(url, { signal: controller.signal, headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error(`동행복권 응답 오류 (HTTP ${res.status})`);
    return parsePayload(await res.json());
  } finally {
    clearTimeout(timer);
  }
}

/** 회차 목록을 번호 기준으로 합친다. 같은 회차는 incoming 이 이긴다. */
export function mergeDraws(base, incoming) {
  const byNo = new Map(base.map(d => [d.no, d]));
  for (const d of incoming) byNo.set(d.no, d);
  return [...byNo.values()].sort((a, b) => a.no - b.no);
}

/** 캐시에 없는 최신 회차만 이어서 받는다. 실패해도 받은 만큼은 돌려준다. */
export async function fetchNewDraws(draws, options = {}) {
  const { maxFetch = 12 } = options;
  const latest = draws.length ? Math.max(...draws.map(d => d.no)) : 0;
  const newest = await fetchDraw(null, options);
  if (!newest || newest.no <= latest) return { added: [], latest, newest: newest?.no ?? latest };

  const added = [];
  for (let no = latest + 1; no < newest.no && added.length < maxFetch; no++) {
    const d = await fetchDraw(no, options);
    if (!d) break;
    added.push(d);
  }
  added.push(newest);
  return { added, latest, newest: newest.no };
}
