const API_BASE_URL = `${import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1`;
const CANDIDATE_TOKEN_KEY = "mentormuni:candidate-token:v1";

export type AssessmentSummary = {
  slug: string;
  title: string;
  description: string;
  duration_seconds: number;
  question_count: number;
  sections: Array<{ title: string; question_count: number }>;
};

export type AssessmentQuestion = {
  id: string;
  position: number;
  section: string;
  topic: string;
  difficulty: "easy" | "medium" | "hard";
  question_type: "single_choice";
  prompt: string;
  stimulus: Record<string, unknown> | null;
  options: Array<{ id: string; text: string }>;
  answer: { option_id: string } | null;
  marked_for_review: boolean;
  visited: boolean;
};

export type AssessmentAttempt = {
  id: string;
  assessment_slug: string;
  title: string;
  status: "in_progress" | "submitted" | "expired";
  started_at: string;
  deadline_at: string;
  server_time: string;
  question_count: number;
  current_position: number;
  questions: AssessmentQuestion[];
};

export type SectionResult = {
  section: string;
  score: number;
  max_score: number;
  correct: number;
  incorrect: number;
  unanswered: number;
  accuracy_percent: number;
};

export type AssessmentResult = {
  attempt_id: string;
  assessment_slug: string;
  assessment_title: string;
  status: "submitted" | "expired";
  score: number;
  max_score: number;
  correct: number;
  incorrect: number;
  unanswered: number;
  accuracy_percent: number;
  attempt_rate_percent: number;
  elapsed_seconds: number;
  sections: SectionResult[];
  review: Array<{
    question_id: string;
    position: number;
    section: string;
    topic: string;
    prompt: string;
    options: Array<{ id: string; text: string }>;
    answer: { option_id: string } | null;
    correct_answer: { option_id: string } | null;
    explanation: string | null;
    is_correct: boolean | null;
  }>;
};

type APIErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown[];
  };
  request_id?: string;
};

export class AssessmentApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;

  constructor(message: string, status: number, code: string, requestId?: string) {
    super(message);
    this.name = "AssessmentApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  candidateToken?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  if (candidateToken) headers.set("X-Candidate-Token", candidateToken);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: "omit",
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "Network request failed.";
    throw new AssessmentApiError(
      `The assessment service could not be reached. ${reason}`,
      0,
      "service_unavailable",
    );
  }

  if (!response.ok) {
    let body: APIErrorBody;
    try {
      body = await response.json() as APIErrorBody;
    } catch (error) {
      const reason = error instanceof Error ? error.message : "The server returned an invalid error response.";
      throw new AssessmentApiError(reason, response.status, "invalid_error_response");
    }
    throw new AssessmentApiError(
      body.error?.message ?? `Assessment request failed with status ${response.status}.`,
      response.status,
      body.error?.code ?? "request_failed",
      body.request_id,
    );
  }

  if (response.status === 204) return undefined as T;
  try {
    return await response.json() as T;
  } catch (error) {
    const reason = error instanceof Error ? error.message : "The server returned an invalid response.";
    throw new AssessmentApiError(reason, response.status, "invalid_response");
  }
}

async function createCandidateToken(): Promise<string> {
  const response = await request<{ session_token: string }>("/candidate-sessions", {
    method: "POST",
  });
  if (!response.session_token) {
    throw new AssessmentApiError("The server did not create a candidate session.", 502, "invalid_session_response");
  }
  sessionStorage.setItem(CANDIDATE_TOKEN_KEY, response.session_token);
  return response.session_token;
}

let candidateTokenRequest: Promise<string> | null = null;

async function getCandidateToken(): Promise<string> {
  const storedToken = sessionStorage.getItem(CANDIDATE_TOKEN_KEY);
  if (storedToken) return storedToken;
  if (!candidateTokenRequest) {
    candidateTokenRequest = createCandidateToken().finally(() => {
      candidateTokenRequest = null;
    });
  }
  return candidateTokenRequest;
}

export async function listAssessments(): Promise<AssessmentSummary[]> {
  return request<AssessmentSummary[]>("/assessments");
}

export async function startAssessment(assessmentSlug: string): Promise<{ id: string }> {
  const candidateToken = await getCandidateToken();
  return request<{ id: string }>("/attempts", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ assessment_slug: assessmentSlug }),
  }, candidateToken);
}

export async function getAssessmentAttempt(attemptId: string): Promise<AssessmentAttempt> {
  const candidateToken = await getCandidateToken();
  return request<AssessmentAttempt>(`/attempts/${encodeURIComponent(attemptId)}`, {}, candidateToken);
}

export async function saveAssessmentResponse(
  attemptId: string,
  questionId: string,
  optionId: string,
  timeSpentSeconds: number,
): Promise<void> {
  const candidateToken = await getCandidateToken();
  await request(`/attempts/${encodeURIComponent(attemptId)}/responses/${encodeURIComponent(questionId)}`, {
    method: "PUT",
    body: JSON.stringify({
      answer: { option_id: optionId },
      time_spent_seconds: timeSpentSeconds,
    }),
  }, candidateToken);
}

export async function clearAssessmentResponse(attemptId: string, questionId: string): Promise<void> {
  const candidateToken = await getCandidateToken();
  await request(`/attempts/${encodeURIComponent(attemptId)}/responses/${encodeURIComponent(questionId)}`, {
    method: "DELETE",
  }, candidateToken);
}

export async function setAssessmentQuestionReview(
  attemptId: string,
  questionId: string,
  marked: boolean,
): Promise<void> {
  const candidateToken = await getCandidateToken();
  await request(`/attempts/${encodeURIComponent(attemptId)}/questions/${encodeURIComponent(questionId)}/review`, {
    method: "PATCH",
    body: JSON.stringify({ marked }),
  }, candidateToken);
}

export async function updateAssessmentQuestionPosition(
  attemptId: string,
  questionId: string,
  timeSpentSeconds: number,
): Promise<number> {
  const candidateToken = await getCandidateToken();
  const result = await request<{ current_position: number }>(
    `/attempts/${encodeURIComponent(attemptId)}/position`,
    {
      method: "PATCH",
      body: JSON.stringify({ question_id: questionId, time_spent_seconds: timeSpentSeconds }),
    },
    candidateToken,
  );
  return result.current_position;
}

export async function submitAssessment(attemptId: string): Promise<AssessmentResult> {
  const candidateToken = await getCandidateToken();
  return request<AssessmentResult>(`/attempts/${encodeURIComponent(attemptId)}/submit`, {
    method: "POST",
  }, candidateToken);
}

export async function getAssessmentResult(attemptId: string): Promise<AssessmentResult> {
  const candidateToken = await getCandidateToken();
  return request<AssessmentResult>(`/attempts/${encodeURIComponent(attemptId)}/results`, {}, candidateToken);
}
