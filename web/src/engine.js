/** 화면이 쓰는 서비스 계층. 데이터 → 통계·모델 준비 → 추천/채점/운세/내 번호.
 *
 * 무거운 계산(통계·경험분포·참조점수)은 옵션이 바뀔 때만 다시 하고 캐싱한다.
 */
import { drawDateOf, fetchDraw, fetchNewDraws, mergeDraws } from './dhlottery.js';
import { ballColor, createFolklore, describe as describeFolklore } from './folklore.js';
import { analysisNote, zonePhrase } from './explain.js';
import { grade } from './grade.js';
import { NUMBER_POOL, summary } from './metrics.js';
import { calibrate, fit, referenceScores } from './model.js';
import { parse as parseQr } from './qr.js';
import { recommend } from './generator.js';
import { build as buildStats, cold, hot, meanFrequency, profileStats } from './stats.js';
import { DEFAULT_STRATEGIES, byKey } from './strategies.js';
import {
  createProfile, dailyFortune, emptyProfile, personalNumbers,
  profileFromJSON, recommendInputs, zodiacTable,
} from './fortune.js';

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** 화면 폼 값을 검증된 추천 옵션으로. 파이썬 Options.from_dict 대응. */
export function parseOptions(raw = {}) {
  const ints = v => {
    const items = Array.isArray(v) ? v : String(v ?? '').replace(/,/g, ' ').split(/\s+/);
    const out = [...new Set(items.filter(x => String(x).trim() !== '').map(Number))].sort((a, b) => a - b);
    const bad = out.filter(n => !NUMBER_POOL.includes(n));
    if (bad.length) throw new Error(`번호는 1~45 범위여야 합니다: ${bad.join(', ')}`);
    return out;
  };
  const num = (v, fallback) => {
    const n = Number(v);
    return Number.isFinite(n) && String(v ?? '').trim() !== '' ? n : fallback;
  };
  const seed = raw.seed;
  return {
    lines: clamp(Math.trunc(num(raw.lines, 5)), 1, 20),
    seed: seed === '' || seed === null || seed === undefined ? null : Number(seed),
    strategies: raw.strategies?.length ? [...raw.strategies] : [],
    lucky: ints(raw.lucky ?? []),
    avoid: ints(raw.avoid ?? []),
    dream: String(raw.dream ?? ''),
    birthday: String(raw.birthday ?? ''),
    zodiac: String(raw.zodiac ?? ''),
    folklore: raw.folklore === undefined ? true : Boolean(raw.folklore),
    coverage: clamp(num(raw.coverage, 0.8), 0.5, 0.99),
    calibrate: raw.calibrate === undefined ? true : Boolean(raw.calibrate),
    candidates: clamp(Math.trunc(num(raw.candidates, 40)), 1, 400),
    temperature: clamp(num(raw.temperature, 1.0), 0.05, 5.0),
    maxOverlap: clamp(Math.trunc(num(raw.maxOverlap, 3)), 0, 6),
    recentWindow: clamp(Math.trunc(num(raw.recentWindow, 30)), 5, 200),
  };
}

const toFolklore = opts => createFolklore({
  enabled: opts.folklore, lucky: opts.lucky, avoid: opts.avoid,
  dream: opts.dream, birthday: opts.birthday, zodiac: opts.zodiac,
});

export function createEngine(initialDraws = [], storage = null) {
  let draws = [...initialDraws].sort((a, b) => a.no - b.no);
  let cache = null;

  const previous = () => (draws.length ? draws[draws.length - 1] : null);
  const findDraw = no => (no === null || no === undefined
    ? previous()
    : draws.find(d => d.no === Number(no)) || null);

  /** 옵션이 바뀔 때만 다시 계산한다. */
  function prepare(opts) {
    const key = `${opts.recentWindow}|${opts.coverage}|${opts.calibrate}|${draws.length}|${previous()?.no}`;
    if (cache && cache.key === key) return cache;
    const stats = buildStats(draws, opts.recentWindow);
    const emp = draws.length ? fit(draws) : null;
    const reference = emp ? referenceScores(draws, emp) : [];
    const rules = opts.calibrate && draws.length ? calibrate(draws, opts.coverage) : null;
    cache = { key, stats, emp, reference, rules };
    return cache;
  }

  const drawPayload = d => ({
    no: d.no,
    date: d.drawDate || drawDateOf(d.no),
    numbers: d.numbers,
    bonus: d.bonus,
    colors: d.numbers.map(ballColor),
    bonusColor: ballColor(d.bonus),
    prizes: d.prizes || [],
    hasPrizes: (d.prizes || []).length === 5,
    totalSales: d.totalSales ?? -1,
    firstWinners: d.prizes?.[0]?.winners ?? -1,
    firstPrize: d.prizes?.[0]?.amount ?? -1,
  });

  return {
    get draws() { return draws; },
    get previous() { return previous(); },
    drawPayload,
    findDraw,

    /** 추천 5줄 + 화면에 필요한 부가 정보. */
    recommendPayload(rawOptions = {}) {
      const opts = parseOptions(rawOptions);
      const { stats, emp, reference, rules } = prepare(opts);
      const folklore = toFolklore(opts);
      const prev = previous();
      const strategies = opts.strategies.length ? opts.strategies.map(byKey) : DEFAULT_STRATEGIES;
      const lines = recommend(stats, {
        previous: prev, strategies, lines: opts.lines, seed: opts.seed,
        folklore, emp, reference, candidates: opts.candidates,
        temperature: opts.temperature, maxOverlap: opts.maxOverlap, rulesOverride: rules,
      });
      return {
        previous: prev ? drawPayload(prev) : null,
        nextDrawNo: prev ? prev.no + 1 : null,
        nextDrawDate: prev ? drawDateOf(prev.no + 1) : null,
        drawsUsed: draws.length,
        folklore: opts.folklore ? describeFolklore(folklore) : ['속설 로직 끔'],
        rules,
        seed: opts.seed,
        lines: lines.map((ln, i) => ({
          index: i + 1,
          strategy: ln.strategy.key,
          strategyName: ln.strategy.name,
          concept: ln.strategy.concept,
          numbers: ln.numbers,
          bonus: ln.bonus,
          colors: ln.numbers.map(ballColor),
          bonusColor: ballColor(ln.bonus),
          note: analysisNote(ln, prev, folklore),
          metrics: summary(ln.profile),
          zones: zonePhrase(ln.numbers),
          omens: ln.omens,
          luck: ln.luck,
          typicality: Number(ln.typicality.toFixed(3)),
          percentile: Number(ln.percentile.toFixed(1)),
          poolSize: ln.poolSize,
          relaxed: ln.relaxedStep,
        })),
      };
    },

    /** 회차 전체 통계 (통계 탭). */
    statsPayload(recentWindow = 30, coverage = 0.8) {
      if (!draws.length) return { drawsUsed: 0 };
      const stats = buildStats(draws, recentWindow);
      const ps = profileStats(draws);
      const rules = calibrate(draws, coverage);
      const dist = counter => [...counter.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([key, count]) => {
          const total = [...counter.values()].reduce((x, y) => x + y, 0) || 1;
          return { key, count, ratio: Number((count / total).toFixed(4)) };
        });
      return {
        drawsUsed: draws.length,
        firstNo: draws[0].no,
        lastNo: draws[draws.length - 1].no,
        meanSum: Number(ps.meanSum.toFixed(2)),
        sumRange80: ps.sumRange80,
        odd: dist(ps.oddDistribution),
        low: dist(ps.lowDistribution),
        ac: dist(ps.acDistribution),
        endSumMean: Number(ps.endSumMean.toFixed(2)),
        consecutiveRatio: Number(ps.consecutiveRatio.toFixed(4)),
        carryover: dist(ps.carryoverDistribution),
        frequency: NUMBER_POOL.map(n => ({
          n, count: stats.frequency.get(n) || 0, bonus: stats.bonusFrequency.get(n) || 0,
          recent: stats.recent.get(n) || 0, gap: stats.gap.get(n), color: ballColor(n),
        })),
        meanFrequency: Number(meanFrequency(stats).toFixed(2)),
        hot: hot(stats, 10),
        cold: cold(stats, 10),
        recentWindow,
        calibratedRules: rules,
        coverage,
      };
    },

    drawsPayload: (limit = 20) => [...draws].sort((a, b) => b.no - a.no).slice(0, limit).map(drawPayload),

    /** 회차 하나의 1~5등 현황. 없으면 그 회차만 받아 채운다. */
    async drawDetailPayload(no, options = {}) {
      let draw = findDraw(no);
      if (!draw || !(draw.prizes || []).length) {
        try {
          const fetched = await fetchDraw(no, options);
          if (fetched) {
            draws = mergeDraws(draws, [fetched]);
            cache = null;
            storage?.saveDrawCache(draws);
            draw = fetched;
          }
        } catch { /* 오프라인이면 있는 것만 보여 준다 */ }
      }
      if (!draw) throw new Error(`${no}회차 데이터가 없습니다.`);
      return { draw: drawPayload(draw), hasPrizes: (draw.prizes || []).length === 5 };
    },

    /** 조합 채점. */
    gradePayload(lines, drawNo = null) {
      const draw = findDraw(drawNo);
      if (!draw) throw new Error(`${drawNo}회차 데이터가 없습니다.`);
      for (const row of lines) {
        if (row.length !== 6 || new Set(row).size !== 6 || row.some(n => n < 1 || n > 45)) {
          throw new Error(`조합은 1~45 사이 서로 다른 번호 6개여야 합니다: ${row.join(', ')}`);
        }
      }
      const g = grade(lines, draw);
      return { draw: drawPayload(draw), ...g };
    },

    /** QR 문자열을 읽어 그 자리에서 채점. */
    qrPayload(text) {
      const ticket = parseQr(text);
      const draw = findDraw(ticket.drawNo);
      const base = {
        ticket,
        drawDate: drawDateOf(ticket.drawNo),
        colors: ticket.lines.map(row => row.map(ballColor)),
      };
      if (!draw) {
        const newest = previous();
        return {
          ...base,
          status: newest && ticket.drawNo > newest.no ? 'pending' : 'missing',
          latestDraw: newest?.no ?? null,
        };
      }
      return { ...base, status: 'graded', draw: drawPayload(draw), ...grade(ticket.lines, draw) };
    },

    // ---------------------------------------------------------- 운세
    loadProfile() {
      try {
        return profileFromJSON(storage?.loadProfile());
      } catch {
        return emptyProfile();     // 손상된 저장값
      }
    },
    saveProfile(input) {
      const profile = createProfile(input);
      if (profile.isEmpty) throw new Error('생년월일을 입력하세요.');
      storage?.saveProfile({
        name: profile.name, birthDate: profile.birthDate,
        birthBranch: profile.birthBranch, birthHour: profile.birthHour,
      });
      return profile;
    },
    clearProfile() { storage?.clearProfile(); },

    fortunePayload(profile = null, today = null) {
      const p = profile || this.loadProfile();
      const prev = previous();
      return {
        profile: p,
        hasProfile: !p.isEmpty,
        fortune: dailyFortune(p, today),
        recommendInputs: p.isEmpty ? null : recommendInputs(p, today),
        zodiacTable: zodiacTable(today, p.zodiac),
        personalNumbers: p.isEmpty ? [] : personalNumbers(p),
        nextDrawNo: prev ? prev.no + 1 : null,
        nextDrawDate: prev ? drawDateOf(prev.no + 1) : null,
      };
    },

    // ---------------------------------------------------------- 내 번호
    picksPayload() {
      const picks = storage ? storage.listPicks() : [];
      return picks
        .sort((a, b) => (b.targetDraw - a.targetDraw) || String(b.savedAt).localeCompare(a.savedAt))
        .map(p => {
          const draw = findDraw(p.targetDraw);
          const item = {
            ...p,
            drawDate: drawDateOf(p.targetDraw),
            colors: p.lines.map(row => row.map(ballColor)),
            draw: null, results: null,
          };
          if (draw) {
            const g = grade(p.lines, draw);
            item.draw = drawPayload(draw);
            item.results = g.results;
            item.bestRank = g.bestRank;
            item.totalPrize = g.totalPrize;
            item.actualPrize = g.actualPrize;
          }
          return item;
        });
    },
    addPick(lines, targetDraw = null, note = '') {
      const prev = previous();
      const target = targetDraw ?? (prev ? prev.no + 1 : 1);
      if (!storage) throw new Error('저장소를 쓸 수 없습니다.');
      return storage.addPick(lines, target, note);
    },
    deletePick: id => (storage ? storage.deletePick(id) : false),

    // ---------------------------------------------------------- 데이터 갱신
    /** 동행복권에서 새 회차만 이어받는다. 실패하면 이유를 담아 돌려준다. */
    async refresh(options = {}) {
      const before = previous()?.no ?? 0;
      try {
        const { added, newest } = await fetchNewDraws(draws, options);
        if (added.length) {
          draws = mergeDraws(draws, added);
          cache = null;
          storage?.saveDrawCache(draws);
        }
        storage?.saveSettings({ lastCheckedAt: new Date().toISOString() });
        return { ok: true, before, after: previous()?.no ?? 0, added: added.length, newest };
      } catch (err) {
        return { ok: false, before, after: before, added: 0, error: String(err.message || err) };
      }
    },
  };
}
