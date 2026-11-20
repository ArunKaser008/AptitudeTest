import type { AssessmentDefinition, AssessmentQuestion } from "../data/mockData";

export type PreviewAttempt = {
  id: string;
  assessmentId: string;
  questionIds: number[];
  currentQuestion: number;
  responses: Record<number, number>;
  marked: number[];
  durationSeconds: number;
  deadlineAt: number;
};

export type PreviewAttemptResult = {
  assessmentId: string;
  questionIds: number[];
  responses: Record<number, number>;
  elapsedSeconds: number;
};

export type PreviewPracticeSession = {
  questionIds: number[];
  topic: string;
  difficulty: string;
  questionLimit: number;
  activeIndex: number;
  choice: number | null;
  checked: boolean;
  bookmarked: number[];
  deadlineAt: number;
  finished: boolean;
  timedOut: boolean;
};

const HISTORY_LIMIT = 25;
const PRACTICE_SESSION_KEY = "mentormuni:preview:practice";

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function getAttemptStorageKey(assessmentId: string): string {
  return `mentormuni:preview:attempt:${assessmentId}`;
}

export function getHistoryStorageKey(assessmentId: string): string {
  return `mentormuni:preview:history:${assessmentId}`;
}

export function getResultStorageKey(assessmentId: string): string {
  return `mentormuni:preview:result:${assessmentId}`;
}

export function loadPreviewPracticeSession(): PreviewPracticeSession | null {
  const session = readJson<PreviewPracticeSession | null>(PRACTICE_SESSION_KEY, null);
  if (
    !session
    || !Array.isArray(session.questionIds)
    || session.questionIds.length === 0
    || typeof session.topic !== "string"
    || typeof session.difficulty !== "string"
    || !Number.isInteger(session.questionLimit)
    || !Number.isInteger(session.activeIndex)
    || session.activeIndex < 0
    || session.activeIndex >= session.questionIds.length
    || !Number.isFinite(session.deadlineAt)
  ) {
    return null;
  }
  return session;
}

export function savePreviewPracticeSession(session: PreviewPracticeSession): void {
  sessionStorage.setItem(PRACTICE_SESSION_KEY, JSON.stringify(session));
}

export function getPreviewQuestionCount(
  assessment: AssessmentDefinition,
  bank: AssessmentQuestion[],
): number {
  return Math.min(assessment.previewQuestionCount, bank.length);
}

export function getPreviewDurationMinutes(
  assessment: AssessmentDefinition,
  bank: AssessmentQuestion[],
): number {
  const questionCount = getPreviewQuestionCount(assessment, bank);
  if (questionCount === 0) return 0;
  return Math.max(1, Math.ceil(assessment.durationMinutes * questionCount / assessment.questions));
}

export function getSecondsRemaining(deadlineAt: number, now = Date.now()): number {
  return Math.max(0, Math.ceil((deadlineAt - now) / 1000));
}

function shuffleQuestions(
  bank: AssessmentQuestion[],
  random: () => number,
): AssessmentQuestion[] {
  const shuffled = [...bank];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
  }
  return shuffled;
}

export function sampleQuestions(
  bank: AssessmentQuestion[],
  requestedCount: number,
  previousSets: number[][] = [],
  random: () => number = Math.random,
): AssessmentQuestion[] {
  const count = Math.min(Math.max(0, Math.floor(requestedCount)), bank.length);
  if (count === 0) return [];

  const shuffled = shuffleQuestions(bank, random);

  let selected = shuffled.slice(0, count);
  const hasSameSet = (candidate: AssessmentQuestion[]) => previousSets.some((set) => (
    set.length === candidate.length
    && set.every((id) => candidate.some((question) => question.id === id))
  ));

  if (hasSameSet(selected) && count < bank.length) {
    const selectedIds = new Set(selected.map((question) => question.id));
    const replacement = shuffled.find((question) => !selectedIds.has(question.id));
    if (replacement) selected = [...selected.slice(0, count - 1), replacement];
  }

  return selected;
}

function sampleDistributedQuestions(
  bank: AssessmentQuestion[],
  requestedCount: number,
  distribution: Record<string, number>,
  random: () => number,
): AssessmentQuestion[] {
  const selected: AssessmentQuestion[] = [];
  for (const [section, target] of Object.entries(distribution)) {
    const sectionQuestions = bank.filter((item) => item.section === section);
    selected.push(...sampleQuestions(sectionQuestions, target, [], random));
  }

  const selectedIds = new Set(selected.map((item) => item.id));
  const remaining = bank.filter((item) => !selectedIds.has(item.id));
  if (selected.length < requestedCount) {
    selected.push(...sampleQuestions(remaining, requestedCount - selected.length, [], random));
  }
  return shuffleQuestions(selected.slice(0, requestedCount), random);
}

export function sampleNewQuestionSet(
  historyName: string,
  bank: AssessmentQuestion[],
  requestedCount: number,
  random: () => number = Math.random,
  distribution?: Record<string, number>,
): AssessmentQuestion[] {
  const count = Math.min(Math.max(0, Math.floor(requestedCount)), bank.length);
  if (count === 0) return [];

  const historyKey = getHistoryStorageKey(historyName);
  const history = readJson<number[][]>(historyKey, []);
  const usedQuestionIds = new Set(history.flat());
  const unseenQuestions = bank.filter((question) => !usedQuestionIds.has(question.id));
  const exhausted = unseenQuestions.length === 0;
  let selected: AssessmentQuestion[];

  if (unseenQuestions.length >= count) {
    selected = distribution
      ? sampleDistributedQuestions(unseenQuestions, count, distribution, random)
      : sampleQuestions(unseenQuestions, count, [], random);
  } else if (unseenQuestions.length > 0) {
    const fresh = sampleQuestions(unseenQuestions, unseenQuestions.length, [], random);
    const freshIds = new Set(fresh.map((item) => item.id));
    const usedQuestions = bank.filter((item) => !freshIds.has(item.id));
    const fill = distribution
      ? sampleDistributedQuestions(usedQuestions, count - fresh.length, distribution, random)
      : sampleQuestions(usedQuestions, count - fresh.length, [], random);
    selected = shuffleQuestions([...fresh, ...fill], random);
  } else {
    selected = distribution
      ? sampleDistributedQuestions(bank, count, distribution, random)
      : sampleQuestions(bank, count, history, random);
  }

  const historyToKeep = exhausted ? [] : history;
  sessionStorage.setItem(
    historyKey,
    JSON.stringify([...historyToKeep, selected.map((question) => question.id)].slice(-HISTORY_LIMIT)),
  );
  return selected;
}

export function startPreviewAttempt(
  assessment: AssessmentDefinition,
  bank: AssessmentQuestion[],
  random: () => number = Math.random,
): PreviewAttempt {
  const selected = sampleNewQuestionSet(
    assessment.id,
    bank,
    getPreviewQuestionCount(assessment, bank),
    random,
    assessment.previewDistribution,
  );
  const selectedIds = selected.map((question) => question.id);
  const durationSeconds = getPreviewDurationMinutes(assessment, bank) * 60;

  const attempt: PreviewAttempt = {
    id: crypto.randomUUID(),
    assessmentId: assessment.id,
    questionIds: selectedIds,
    currentQuestion: 0,
    responses: {},
    marked: [],
    durationSeconds,
    deadlineAt: Date.now() + durationSeconds * 1000,
  };
  sessionStorage.removeItem(getResultStorageKey(assessment.id));
  sessionStorage.setItem(getAttemptStorageKey(assessment.id), JSON.stringify(attempt));
  return attempt;
}

export function loadPreviewAttempt(
  assessment: AssessmentDefinition,
  bank: AssessmentQuestion[],
): PreviewAttempt | null {
  const storedAttempt = readJson<(PreviewAttempt & { remainingSeconds?: number }) | null>(
    getAttemptStorageKey(assessment.id),
    null,
  );
  const durationSeconds = getPreviewDurationMinutes(assessment, bank) * 60;
  const storedDeadlineAt = storedAttempt?.deadlineAt
    ?? (typeof storedAttempt?.remainingSeconds === "number"
      ? Date.now() + Math.max(0, storedAttempt.remainingSeconds) * 1000
      : undefined);
  if (
    !storedAttempt
    || storedAttempt.assessmentId !== assessment.id
    || !Array.isArray(storedAttempt.questionIds)
    || storedAttempt.questionIds.length === 0
    || !storedAttempt.questionIds.every((id) => bank.some((question) => question.id === id))
    || typeof storedDeadlineAt !== "number"
    || !Number.isFinite(storedDeadlineAt)
  ) {
    return null;
  }

  const oldRemainingSeconds = getSecondsRemaining(storedDeadlineAt);
  const deadlineAt = storedAttempt.durationSeconds === durationSeconds
    ? storedDeadlineAt
    : Math.min(storedDeadlineAt, Date.now() + Math.min(durationSeconds, oldRemainingSeconds) * 1000);
  const attempt: PreviewAttempt = { ...storedAttempt, durationSeconds, deadlineAt };
  delete (attempt as Partial<PreviewAttempt & { remainingSeconds?: number }>).remainingSeconds;
  sessionStorage.setItem(getAttemptStorageKey(assessment.id), JSON.stringify(attempt));
  return attempt;
}

export function savePreviewAttempt(attempt: PreviewAttempt): void {
  sessionStorage.setItem(getAttemptStorageKey(attempt.assessmentId), JSON.stringify(attempt));
}

export function completePreviewAttempt(result: PreviewAttemptResult): void {
  sessionStorage.setItem(getResultStorageKey(result.assessmentId), JSON.stringify(result));
  sessionStorage.removeItem(getAttemptStorageKey(result.assessmentId));
}

export function loadPreviewResult(assessmentId: string): PreviewAttemptResult | null {
  const result = readJson<PreviewAttemptResult | null>(getResultStorageKey(assessmentId), null);
  return result?.assessmentId === assessmentId ? result : null;
}
