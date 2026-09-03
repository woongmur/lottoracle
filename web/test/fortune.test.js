/** fortune.js — 문구·십이지·프로필 파싱은 골든 대조, 운세 생성은 성질로 검사한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as f from '../src/fortune.js';

const golden = JSON.parse(readFileSync(new URL('./golden/fortune.json', import.meta.url)));
const DAY = '2026-09-03';
const P = f.createProfile({ name: '홍길동', birthDate: '1990-05-21', birthBranch: '진' });

test('문구와 상수가 파이썬과 같다', () => {
  assert.equal(f.TAGLINE, golden.tagline);
  assert.equal(f.DISCLAIMER, golden.disclaimer);
  assert.deepEqual(f.FORBIDDEN_WORDS, golden.forbiddenWords);
  assert.deepEqual(f.KEYWORDS, golden.keywords);
  assert.deepEqual(f.TIPS, golden.tips);
  for (const [k, v] of Object.entries(golden.gradeLabels)) assert.equal(f.GRADE_LABELS[k], v);
  for (const [k, v] of Object.entries(golden.gradeWeights)) assert.equal(f.GRADE_WEIGHTS[k], v);
  for (const [k, v] of Object.entries(golden.sentences)) assert.deepEqual(f.SENTENCES[k], v);
  assert.equal(f.allSentences().length, golden.allSentencesCount);
});

test('십이지 시간대가 파이썬과 같다', () => {
  assert.deepEqual(f.BRANCH_RANGE, golden.branchRange);
  assert.deepEqual(f.BRANCH_ANIMAL, golden.branchAnimal);
  assert.deepEqual(f.branchChoices(), golden.branchChoices);
  for (const [key, want] of Object.entries(golden.branchOfTime)) {
    const [h, m] = key.split(':').map(Number);
    assert.equal(f.branchOfTime(h, m), want, `${key}`);
  }
  for (const [input, want] of Object.entries(golden.normalizeBranch)) {
    assert.equal(f.normalizeBranch(input), want, `normalizeBranch("${input}")`);
  }
  assert.throws(() => f.normalizeBranch('갑'), /자·축·인/);
});

test('표시 범위와 계산이 서로 맞는다', () => {
  for (const [branch, range] of Object.entries(f.BRANCH_RANGE)) {
    const [h, m] = range.split('~')[0].split(':').map(Number);
    assert.equal(f.branchOfTime(h, m), branch, `${branch}시 시작 ${range}`);
  }
});

test('프로필 파싱이 파이썬과 같다', () => {
  for (const c of golden.profiles) {
    const opts = {
      name: c.input.name, birthDate: c.input.birth_date,
      birthBranch: c.input.birth_branch, birthHour: c.input.birth_hour,
    };
    const p = f.createProfile(opts);
    for (const key of ['birthDate', 'birthBranch', 'zodiac', 'hourAnimal', 'hourLabel', 'name', 'isEmpty']) {
      assert.deepEqual(p[key], c[key], `${JSON.stringify(c.input)} 의 ${key}`);
    }
    assert.deepEqual(f.personalNumbers(p), c.personalNumbers, `${JSON.stringify(c.input)} 의 내 편 번호`);
  }
});

test('잘못된 입력은 거절한다', () => {
  assert.throws(() => f.createProfile({ birthDate: '1990-13-40' }), /올바르지 않습니다/);
  assert.throws(() => f.createProfile({ birthDate: '어제' }), /YYYY-MM-DD/);
  assert.throws(() => f.createProfile({ birthDate: '1800-01-01' }), /1900년 이후/);
  assert.throws(() => f.createProfile({ birthDate: '1990-05-21', birthHour: 25 }), /0~23/);
  assert.throws(() => f.createProfile({ birthDate: '1990-05-21', birthBranch: '갑' }), /자·축·인/);
});

test('저장·복원이 값을 보존한다', () => {
  const restored = f.profileFromJSON(f.profileToJSON(P));
  assert.deepEqual(restored, P);
  assert.ok(f.emptyProfile().isEmpty);
});

test('같은 날 같은 프로필이면 운세가 똑같다', () => {
  const a = f.dailyFortune(P, DAY);
  const b = f.dailyFortune(P, DAY);
  assert.deepEqual(a, b);
});

test('날짜가 바뀌면 운세도 바뀐다', () => {
  const a = f.dailyFortune(P, DAY);
  const b = f.dailyFortune(P, '2026-09-04');
  assert.notDeepEqual(
    [a.grade, a.sentence, a.numbers, a.keyword],
    [b.grade, b.sentence, b.numbers, b.keyword]);
});

test('사람이 다르면 운세도 다르다', () => {
  const other = f.createProfile({ name: '김철수', birthDate: '1985-03-14' });
  const a = f.dailyFortune(P, DAY), b = f.dailyFortune(other, DAY);
  assert.notDeepEqual([a.grade, a.sentence, a.numbers], [b.grade, b.sentence, b.numbers]);
});

test('운세의 모양이 언제나 규격에 맞는다', () => {
  for (let d = 1; d <= 28; d++) {
    const fo = f.dailyFortune(P, `2026-03-${String(d).padStart(2, '0')}`);
    assert.ok(fo.grade >= 1 && fo.grade <= 5, '등급 범위');
    assert.equal(fo.label, f.GRADE_LABELS[fo.grade], '라벨이 등급과 맞아야 한다');
    assert.ok(f.SENTENCES[fo.grade].includes(fo.sentence), '문장이 그 등급 것이어야 한다');
    assert.equal(fo.numbers.length, 3);
    assert.equal(new Set(fo.numbers).size, 3, '오늘의 숫자 중복 없음');
    assert.deepEqual(fo.numbers, [...fo.numbers].sort((a, b) => a - b), '오름차순');
    for (const n of fo.numbers) assert.ok(n >= 1 && n <= 45, '번호 범위');
    assert.equal(fo.colors.length, 3);
    assert.ok(f.KEYWORDS.includes(fo.keyword));
    assert.ok(f.TIPS.includes(fo.tip));
  }
});

test('어떤 문장에도 금칙어가 없다', () => {
  for (const text of f.allSentences()) {
    assert.deepEqual(f.forbiddenHits(text), [], `금칙어: ${text}`);
  }
  for (let d = 1; d <= 28; d++) {
    const fo = f.dailyFortune(P, `2026-05-${String(d).padStart(2, '0')}`);
    for (const text of [fo.label, fo.sentence, fo.tip, fo.keyword]) {
      assert.deepEqual(f.forbiddenHits(text), [], `생성 결과 금칙어: ${text}`);
    }
  }
});

test('나쁜 날 문장은 겁주지 않고 내일로 이어 준다', () => {
  for (const s of [...f.SENTENCES[1], ...f.SENTENCES[2]]) {
    assert.ok(['내일', '오늘', '천천히', '쉬어'].some(w => s.includes(w)), s);
  }
});

test('프로필 없이도 운세가 나온다', () => {
  const fo = f.dailyFortune(null, DAY);
  assert.equal(fo.numbers.length, 3);
  assert.equal(fo.zodiac, '');
  assert.deepEqual(fo.tags, []);
});

test('띠 표는 11개(내 띠 제외) 또는 12개다', () => {
  const all = f.zodiacTable(DAY);
  assert.equal(all.length, 12);
  assert.deepEqual(all.map(z => z.zodiac),
    ['쥐', '소', '호랑이', '토끼', '용', '뱀', '말', '양', '원숭이', '닭', '개', '돼지']);
  const mine = f.zodiacTable(DAY, '용');
  assert.equal(mine.length, 11);
  assert.ok(!mine.some(z => z.zodiac === '용'));
  for (const z of all) {
    assert.ok(z.grade >= 1 && z.grade <= 5);
    assert.equal(z.numbers.length, 2);
    assert.deepEqual(f.forbiddenHits(z.short), []);
    assert.ok(z.short.endsWith('.'), '한 문장으로 잘린다');
  }
});

test('띠 표도 같은 날이면 재현된다', () => {
  assert.deepEqual(f.zodiacTable(DAY), f.zodiacTable(DAY));
});

test('추천 입력이 프로필과 오늘의 숫자로 채워진다', () => {
  const inputs = f.recommendInputs(P, DAY);
  assert.equal(inputs.birthday, '1990-05-21');
  assert.equal(inputs.zodiac, '말');
  assert.deepEqual(inputs.lucky, f.dailyFortune(P, DAY).numbers);
});
