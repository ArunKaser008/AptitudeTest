const API_BASE_URL = `${import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1/placement`;
const TOKEN_KEY = "mentormuni:placement-token:v1";

export type PlacementUser = {
  id: string;
  email: string;
  display_name: string;
  role: "platform_admin" | "college_admin" | "student";
  college_id: string | null;
  batch_id: string | null;
};

export type PlacementQuestion = {
  id: string;
  college_id: string | null;
  scope: "global" | "college";
  status: "draft" | "active" | "archived";
  topic_slug: string;
  topic_name: string;
  subtopic: string;
  question_type: "mcq_single" | "data_interpretation" | "pseudocode" | "logical_reasoning" | "verbal";
  payload: {
    stem: string;
    options: Array<{ id: string; text: string }>;
    correct_option_id: string;
    shortcut_solution: string;
    concept_solution: string;
    estimated_seconds: number;
    difficulty: "easy" | "medium" | "hard";
    company_tags: string[];
    stimulus: Record<string, unknown> | null;
    latex: string | null;
    code_language: string | null;
  };
  difficulty: "easy" | "medium" | "hard";
  estimated_seconds: number;
  company_tags: string[];
  source_type: "manual" | "parametric" | "ai_generated" | "imported";
};

export type PlacementTest = {
  id: string;
  college_id: string | null;
  title: string;
  description: string;
  scope: "global" | "college";
  duration_minutes: number;
  negative_marks: number;
  passing_cutoff_percent: number;
  status: "draft" | "published" | "archived";
  question_count: number;
};

export type PlacementAssignment = {
  id: string;
  test_id: string;
  college_id: string;
  batch_ids: string[];
  branches: string[];
  graduation_year: number | null;
  starts_at: string;
  ends_at: string | null;
  max_attempts: number;
  status: string;
  test_title: string;
};

export type AttemptQuestion = {
  position: number;
  section_name: string;
  question_id: string;
  topic_slug: string;
  subtopic: string;
  question_type: PlacementQuestion["question_type"];
  stem: string;
  stimulus: Record<string, unknown> | null;
  latex: string | null;
  code_language: string | null;
  options: Array<{ id: string; text: string }>;
  difficulty: "easy" | "medium" | "hard";
  estimated_seconds: number;
  selected_option_id: string | null;
  marked_for_review: boolean;
};

export type PlacementAttempt = {
  id: string;
  test_id: string;
  title: string;
  status: "in_progress" | "submitted" | "expired";
  started_at: string;
  deadline_at: string;
  server_time: string;
  questions: AttemptQuestion[];
};

export type AttemptResult = {
  attempt_id: string;
  test_id: string;
  score: number;
  max_score: number;
  accuracy_percent: number;
  passed: boolean;
  correct: number;
  incorrect: number;
  unanswered: number;
  topic_breakdown: Array<Record<string, string | number>>;
  answers: Array<{
    question_id: string;
    position: number;
    topic_slug: string;
    stem: string;
    options: Array<{ id: string; text: string }>;
    selected_option_id: string | null;
    correct_option_id: string;
    is_correct: boolean | null;
    time_spent_seconds: number;
    mistake_tag: string;
    shortcut_solution: string;
    concept_solution: string;
    estimated_seconds: number;
  }>;
};

export type PracticeQuestion = {
  topic_slug: string;
  subtopic: string;
  question_type: PlacementQuestion["question_type"];
  stem: string;
  options: Array<{ id: string; text: string }>;
  correct_option_id: string;
  shortcut_solution: string;
  concept_solution: string;
  estimated_seconds: number;
  difficulty: "easy" | "medium" | "hard";
  stimulus: Record<string, unknown> | null;
  latex: string | null;
  code_language: string | null;
};

export function getPlacementToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setPlacementToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearPlacementToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export async function placementRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getPlacementToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const body: unknown = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) clearPlacementToken();
    const detail = typeof body === "object" && body !== null && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : `Request failed (${response.status}).`;
    throw new Error(detail);
  }
  return body as T;
}

export function placementJson(method: string, value: unknown): RequestInit {
  return { method, body: JSON.stringify(value) };
}
