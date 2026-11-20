import {
  requestAssessmentApi,
  type QuestionStimulus,
} from "./assessmentApi";

export type QuestionStatus = "draft" | "review" | "published" | "archived";
export type QuestionDifficulty = "easy" | "medium" | "hard";
export type AuthoringQuestionDraft = {
  question_type: "single_choice" | "multi_choice" | "numeric";
  prompt: string;
  stimulus: QuestionStimulus | null;
  topic: string;
  difficulty: QuestionDifficulty;
  options: Array<{ id: string; text: string }>;
  correct_answer: Record<string, unknown>;
  explanation: string;
  marks: number;
  negative_marks: number;
  source_reference?: string | null;
};

export type AuthoringQuestion = AuthoringQuestionDraft & {
  id: string;
  logical_id: string;
  version_number: number;
  status: QuestionStatus;
  verified_at: string | null;
  usage_count: number;
};

export type AuthoringSection = {
  id: string;
  section_key: string;
  title: string;
  position: number;
  question_count: number;
  marks_per_question: number;
  negative_marks: number;
  eligible_verified_count: number;
  ready: boolean;
  question_version_ids: string[];
};

export type AuthoringAssessment = {
  id: string;
  slug: string;
  title: string;
  description: string;
  status: "draft" | "published" | "archived";
  category?: "aptitude" | "company_mock" | "practice";
  target_role?: string | null;
  config_version_id: string | null;
  config_version_number: number | null;
  config_status: "draft" | "published" | "archived" | null;
  duration_seconds: number | null;
  show_explanations_after_submission: boolean;
  randomize_questions: boolean;
  randomize_options: boolean;
  scoring_policy: Record<string, unknown>;
  eligible_verified_count: number;
  required_question_count: number;
  ready: boolean;
  sections: AuthoringSection[];
};

export type AssessmentSectionDraft = {
  section_key: string;
  title: string;
  position: number;
  question_count: number;
  marks_per_question: number;
  negative_marks: number;
  question_version_ids: string[];
};

export type AssessmentConfigDraft = {
  duration_seconds: number;
  show_explanations_after_submission: boolean;
  randomize_questions: boolean;
  randomize_options: boolean;
  scoring_policy: Record<string, unknown>;
  sections: AssessmentSectionDraft[];
};

export type QuestionListResult = {
  items: AuthoringQuestion[];
  total: number;
  page: number;
  page_size: number;
};

export type BulkImportResult = {
  dry_run: boolean;
  imported_count: number;
  valid_count: number;
  errors: Array<{ row_index: number; field: string; message: string }>;
};

export async function listAuthoringQuestions(filters: {
  search?: string;
  topic?: string;
  difficulty?: QuestionDifficulty | "";
  status?: QuestionStatus | "";
  verified?: boolean | null;
  page?: number;
  pageSize?: number;
}): Promise<QuestionListResult> {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.topic) params.set("topic", filters.topic);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  if (filters.status) params.set("status", filters.status);
  if (filters.verified !== undefined && filters.verified !== null) {
    params.set("verified", String(filters.verified));
  }
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? 25));
  return requestAssessmentApi<QuestionListResult>(`/authoring/questions?${params}`);
}

export function createQuestion(payload: AuthoringQuestionDraft): Promise<AuthoringQuestion> {
  return requestAssessmentApi("/authoring/questions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateQuestion(
  questionId: string,
  payload: AuthoringQuestionDraft,
): Promise<AuthoringQuestion> {
  return requestAssessmentApi(`/authoring/questions/${encodeURIComponent(questionId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function verifyPublishQuestion(questionId: string): Promise<AuthoringQuestion> {
  return requestAssessmentApi(`/authoring/questions/${encodeURIComponent(questionId)}/verify-publish`, {
    method: "POST",
  });
}

export function archiveQuestion(questionId: string): Promise<{ active_pool_usage_count: number }> {
  return requestAssessmentApi(`/authoring/questions/${encodeURIComponent(questionId)}/archive`, {
    method: "POST",
  });
}

export function importQuestions(
  source: string,
  contentType: "application/json" | "text/csv",
  dryRun: boolean,
): Promise<BulkImportResult> {
  return requestAssessmentApi(`/authoring/questions/bulk-import?dry_run=${dryRun}`, {
    method: "POST",
    headers: { "Content-Type": contentType },
    body: source,
  });
}

export function listAuthoringAssessments(): Promise<AuthoringAssessment[]> {
  return requestAssessmentApi("/authoring/assessments");
}

export function createAuthoringAssessment(payload: {
  slug: string;
  title: string;
  description: string;
  category?: "aptitude" | "company_mock" | "practice";
  target_role?: string | null;
  ai_generation_enabled?: boolean;
  blueprint_topics?: string[];
} & AssessmentConfigDraft): Promise<AuthoringAssessment> {
  return requestAssessmentApi("/authoring/assessments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cloneAuthoringAssessment(
  assessmentId: string,
  slug: string,
  title: string,
): Promise<AuthoringAssessment> {
  return requestAssessmentApi(`/authoring/assessments/${encodeURIComponent(assessmentId)}/clone`, {
    method: "POST",
    body: JSON.stringify({ slug, title }),
  });
}

export function updateAuthoringAssessmentConfig(
  assessmentId: string,
  payload: AssessmentConfigDraft,
): Promise<AuthoringAssessment> {
  return requestAssessmentApi(`/authoring/assessments/${encodeURIComponent(assessmentId)}/config`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function updateAuthoringSectionPool(
  sectionId: string,
  questionVersionIds: string[],
): Promise<AuthoringSection> {
  return requestAssessmentApi(`/authoring/sections/${encodeURIComponent(sectionId)}/pool`, {
    method: "PUT",
    body: JSON.stringify({ question_version_ids: questionVersionIds }),
  });
}

export function publishAuthoringAssessment(assessmentId: string): Promise<AuthoringAssessment> {
  return requestAssessmentApi(`/authoring/assessments/${encodeURIComponent(assessmentId)}/publish`, {
    method: "POST",
  });
}
