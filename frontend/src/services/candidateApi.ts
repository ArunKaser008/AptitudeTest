import {
  AssessmentApiError,
  requestCandidateApi,
  type AssessmentSummary,
} from "./assessmentApi";

export function candidateApiErrorMessage(error: unknown): string {
  if (error instanceof AssessmentApiError) {
    return error.requestId ? `${error.message} Reference: ${error.requestId}` : error.message;
  }
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}

export type PracticeTopic = {
  topic: string;
  easy_count: number;
  medium_count: number;
  hard_count: number;
  total_count: number;
};

export type CandidatePerformance = {
  completed_attempts: number;
  readiness_score: number;
  average_accuracy_percent: number;
  average_time_seconds: number;
  practice_time_seconds: number;
  trend: Array<{
    attempt_id: string;
    assessment_slug: string;
    assessment_title: string;
    category: AssessmentSummary["category"];
    submitted_at: string;
    score_percent: number;
    accuracy_percent: number;
  }>;
  topics: Array<{
    topic: string;
    total_questions: number;
    correct: number;
    incorrect: number;
    unanswered: number;
    accuracy_percent: number;
    avg_time_seconds: number;
  }>;
};

export type CandidateRecommendation = {
  id: string;
  kind: "weak_topic" | "time_management" | "progression" | "baseline";
  title: string;
  description: string;
  topic: string | null;
  assessment_slug: string | null;
  action_label: string;
  estimated_minutes: number | null;
};

export type CandidateRecommendations = {
  count: number;
  items: CandidateRecommendation[];
};

export async function getPracticeTopics(): Promise<PracticeTopic[]> {
  return requestCandidateApi("/practice/topics");
}

export async function startPracticeSession(input: {
  topics: string[];
  question_count: number;
}): Promise<{ id: string; title: string; question_count: number }> {
  return requestCandidateApi("/practice/session", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(input),
  });
}

export async function startSimilarPractice(input: {
  source_attempt_id?: string;
  question_id?: string;
  topics: string[];
  question_count: number;
}): Promise<{ id: string; title: string; question_count: number }> {
  return requestCandidateApi("/practice/similar", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(input),
  });
}

export async function getCandidatePerformance(): Promise<CandidatePerformance> {
  return requestCandidateApi("/candidate/performance");
}

export async function getCandidateRecommendations(): Promise<CandidateRecommendations> {
  return requestCandidateApi("/candidate/recommendations");
}
