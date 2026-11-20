import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileQuestion,
  Flag,
  Gauge,
  RotateCcw,
  ShieldCheck,
  X,
} from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PageHeading } from "./components/PageHeading";
import { StimulusBlock } from "./components/exam/StimulusBlock";
import {
  type AssessmentAnswer,
  AssessmentApiError,
  clearAssessmentResponse,
  getAssessmentAttempt,
  getAssessmentResult,
  listAssessments,
  saveAssessmentResponse,
  setAssessmentQuestionReview,
  startAssessment,
  submitAssessment,
  startWeakTopicPractice,
  updateAssessmentQuestionPosition,
  type AssessmentAttempt,
  type AssessmentQuestion,
  type AssessmentSummary,
} from "./services/assessmentApi";

function errorMessage(error: unknown): string {
  if (error instanceof AssessmentApiError) {
    return error.requestId ? `${error.message} Reference: ${error.requestId}` : error.message;
  }
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}

function LoadingPanel({ message }: { message: string }) {
  return <div className="panel assessment-state" role="status"><span className="loading-spinner" />{message}</div>;
}

function ErrorPanel({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="panel assessment-state error-state" role="alert">
      <strong>We couldn’t load this assessment.</strong>
      <span>{errorMessage(error)}</span>
      {onRetry && <button className="button button-outline" onClick={onRetry}>Try again</button>}
      <Link to="/aptitude" className="button button-outline">Return to assessments</Link>
    </div>
  );
}

export function AssessmentCatalogPage() {
  const navigate = useNavigate();
  const assessmentsQuery = useQuery({
    queryKey: ["available-assessments"],
    queryFn: listAssessments,
  });
  const [startingSlug, setStartingSlug] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sectionFilter, setSectionFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState<"easy" | "medium" | "hard" | "">("");
  const [durationFilter, setDurationFilter] = useState("");

  const visibleAssessments = assessmentsQuery.data?.filter((assessment) => {
    const searchText = `${assessment.title} ${assessment.description} ${assessment.sections.map((section) => section.title).join(" ")}`.toLowerCase();
    const matchesSearch = searchText.includes(search.trim().toLowerCase());
    const matchesSection = !sectionFilter || assessment.sections.some((section) => section.title === sectionFilter);
    const matchesDifficulty = !difficultyFilter || (assessment.difficulties ?? []).some((value) => value === difficultyFilter);
    const durationMinutes = assessment.duration_seconds / 60;
    const matchesDuration = !durationFilter
      || (durationFilter === "short" && durationMinutes <= 15)
      || (durationFilter === "medium" && durationMinutes > 15 && durationMinutes <= 45)
      || (durationFilter === "long" && durationMinutes > 45);
    return matchesSearch && matchesSection && matchesDifficulty && matchesDuration;
  });
  const sections = [...new Set((assessmentsQuery.data ?? []).flatMap((assessment) => assessment.sections.map((section) => section.title)))].sort();
  const difficulties = [...new Set((assessmentsQuery.data ?? []).flatMap((assessment) => assessment.difficulties ?? []))].sort();

  const begin = async (assessment: AssessmentSummary) => {
    setStartingSlug(assessment.slug);
    setStartError(null);
    try {
      const attempt = await startAssessment(assessment.slug);
      navigate(`/exam/${attempt.id}`);
    } catch (error) {
      setStartError(errorMessage(error));
    } finally {
      setStartingSlug(null);
    }
  };

  return (
    <>
      <PageHeading
        eyebrow="MEASURE YOUR READINESS"
        title="Aptitude assessments"
        description="Choose a published assessment. Your answers and timer are saved securely by the assessment service."
      />
      <div className="callout callout-blue">
        <span className="callout-icon"><ShieldCheck size={18} /></span>
        <span>
          <strong>Company-style assessments are MentorMuni practice simulations.</strong>
          <small>They are not official company tests and do not guarantee a hiring outcome.</small>
        </span>
      </div>
      <div className="catalog-toolbar">
        <div><h2>Published assessments</h2><p>Only assessments with reviewed and verified questions are available here.</p></div>
        {visibleAssessments && <span className="catalog-count">{visibleAssessments.length} available</span>}
      </div>
      {assessmentsQuery.data && assessmentsQuery.data.length > 0 && (
        <div className="catalog-filters" aria-label="Filter published assessments">
          <label className="catalog-search">
            <span className="sr-only">Search assessments and topics</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search assessments or sections" />
          </label>
          <label className="catalog-filter-select">
            <span className="sr-only">Filter by section</span>
            <select value={sectionFilter} onChange={(event) => setSectionFilter(event.target.value)}>
              <option value="">All sections</option>
              {sections.map((section) => <option key={section}>{section}</option>)}
            </select>
          </label>
          <div className="catalog-filter-chips" aria-label="Difficulty">
            <button className={!difficultyFilter ? "active" : ""} onClick={() => setDifficultyFilter("")}>Any difficulty</button>
            {difficulties.map((difficulty) => (
              <button
                key={difficulty}
                className={difficultyFilter === difficulty ? "active" : ""}
                onClick={() => setDifficultyFilter(difficultyFilter === difficulty ? "" : difficulty)}
              >
                {difficulty}
              </button>
            ))}
          </div>
          <div className="catalog-filter-chips" aria-label="Duration">
            {[
              ["", "Any duration"],
              ["short", "Up to 15 min"],
              ["medium", "16-45 min"],
              ["long", "> 45 min"],
            ].map(([value, label]) => (
              <button
                key={value}
                className={durationFilter === value ? "active" : ""}
                onClick={() => setDurationFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      {startError && <p className="assessment-inline-error" role="alert">{startError}</p>}
      {assessmentsQuery.isLoading && <LoadingPanel message="Loading published assessments…" />}
      {assessmentsQuery.isError && <ErrorPanel error={assessmentsQuery.error} onRetry={() => void assessmentsQuery.refetch()} />}
      {assessmentsQuery.data?.length === 0 && (
        <div className="panel empty-assessments">
          <span className="empty-assessment-icon"><ShieldCheck size={22} /></span>
          <h2>No assessments are published yet</h2>
          <p>Assessments appear here after verified questions and assessment rules are approved and published.</p>
        </div>
      )}
      {visibleAssessments && visibleAssessments.length === 0 && assessmentsQuery.data && assessmentsQuery.data.length > 0 && (
        <div className="panel empty-assessments"><h2>No assessments match those filters</h2><p>Try clearing one or more filters.</p></div>
      )}
      {visibleAssessments && visibleAssessments.length > 0 && (
        <div className="assessment-grid">
          {visibleAssessments.map((assessment, index) => (
            <article className="assessment-card" key={assessment.slug}>
              <div className="assessment-card-top">
                <span className={`assessment-icon assessment-icon-${index % 3}`}><FileQuestion size={20} /></span>
                <span className="badge badge-green">Published</span>
              </div>
              <h3>{assessment.title}</h3>
              <p className="assessment-description">{assessment.description}</p>
              <div className="assessment-meta">
                <span><FileQuestion size={15} />{assessment.question_count} questions</span>
                <span><Clock3 size={15} />{Math.ceil(assessment.duration_seconds / 60)} min</span>
                <span><Gauge size={15} />Timed assessment</span>
              </div>
              <div className="chip-list">
                {assessment.sections.map((section) => (
                  <span className="topic-chip" key={section.title}>{section.title}</span>
                ))}
              </div>
              <button
                className="button button-primary full-button"
                disabled={startingSlug !== null}
                onClick={() => void begin(assessment)}
              >
                {startingSlug === assessment.slug ? "Starting…" : "Start assessment"}
                <ArrowRight size={16} />
              </button>
            </article>
          ))}
        </div>
      )}
      <div className="catalog-footer"><ShieldCheck size={17} /><span>Assessment responses are bound to an anonymous candidate session and are not linked to a student profile.</span></div>
    </>
  );
}

export function AssessmentExamPage() {
  const { assessmentId: attemptId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const queryKey = ["assessment-attempt", attemptId];
  const attemptQuery = useQuery({
    queryKey,
    queryFn: () => getAssessmentAttempt(attemptId),
    enabled: Boolean(attemptId),
    retry: false,
  });
  const attempt = attemptQuery.data;
  const [clockNow, setClockNow] = useState(Date.now);
  const [serverOffset, setServerOffset] = useState(0);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [numericDrafts, setNumericDrafts] = useState<Record<string, string>>({});
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const questionEnteredAt = useRef(Date.now());
  const submitInFlight = useRef(false);
  const autoSubmitAttempted = useRef(false);
  const currentQuestion = attempt?.questions[attempt.current_position];

  useEffect(() => {
    if (attempt) {
      setServerOffset(Date.parse(attempt.server_time) - Date.now());
      questionEnteredAt.current = Date.now();
    }
  }, [attempt?.id, attempt?.server_time]);

  useEffect(() => {
    const syncClock = () => setClockNow(Date.now());
    const timerId = window.setInterval(syncClock, 1000);
    window.addEventListener("focus", syncClock);
    document.addEventListener("visibilitychange", syncClock);
    return () => {
      window.clearInterval(timerId);
      window.removeEventListener("focus", syncClock);
      document.removeEventListener("visibilitychange", syncClock);
    };
  }, []);

  const remainingSeconds = attempt
    ? Math.max(0, Math.ceil((Date.parse(attempt.deadline_at) - (clockNow + serverOffset)) / 1000))
    : 0;
  const formattedTime = `${String(Math.floor(remainingSeconds / 3600)).padStart(2, "0")}:${String(Math.floor((remainingSeconds % 3600) / 60)).padStart(2, "0")}:${String(remainingSeconds % 60).padStart(2, "0")}`;

  const patchAttempt = (update: (current: AssessmentAttempt) => AssessmentAttempt) => {
    queryClient.setQueryData<AssessmentAttempt>(queryKey, (current) => current ? update(current) : current);
  };

  const submit = async () => {
    if (!attempt || submitInFlight.current) return;
    submitInFlight.current = true;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const elapsed = Math.max(0, Math.floor((Date.now() - questionEnteredAt.current) / 1000));
      await submitAssessment(attempt.id, currentQuestion?.id, currentQuestion ? elapsed : 0);
      navigate(`/results/${attempt.id}`, { replace: true });
    } catch (error) {
      setSubmitError(errorMessage(error));
    } finally {
      submitInFlight.current = false;
      setSubmitting(false);
    }
  };

  useEffect(() => {
    if (attempt?.status === "submitted" || attempt?.status === "expired") {
      navigate(`/results/${attempt.id}`, { replace: true });
    }
  }, [attempt?.id, attempt?.status, navigate]);

  useEffect(() => {
    if (
      attempt?.status === "in_progress"
      && remainingSeconds === 0
      && !autoSubmitAttempted.current
    ) {
      autoSubmitAttempted.current = true;
      void submit();
    }
  }, [attempt?.id, attempt?.status, remainingSeconds]);

  useEffect(() => {
    autoSubmitAttempted.current = false;
  }, [attemptId]);

  const saveAnswer = async (question: AssessmentQuestion, answer: AssessmentAnswer | null) => {
    if (!attempt || saving) return;
    setSaving(true);
    setSaveError(null);
    const elapsed = Math.max(0, Math.floor((Date.now() - questionEnteredAt.current) / 1000));
    try {
      if (answer === null) {
        await clearAssessmentResponse(attempt.id, question.id);
      } else {
        await saveAssessmentResponse(attempt.id, question.id, answer, elapsed);
      }
      patchAttempt((current) => ({
        ...current,
        questions: current.questions.map((item) => item.id === question.id
          ? { ...item, answer }
          : item),
      }));
      questionEnteredAt.current = Date.now();
    } catch (error) {
      setSaveError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const selectOption = (question: AssessmentQuestion, optionId: string) => {
    if (question.question_type === "single_choice") {
      void saveAnswer(question, { option_id: optionId });
      return;
    }
    if (question.question_type === "multi_choice") {
      const current = question.answer && "option_ids" in question.answer
        ? question.answer.option_ids
        : [];
      const selected = current.includes(optionId)
        ? current.filter((id) => id !== optionId)
        : [...current, optionId];
      void saveAnswer(question, selected.length > 0 ? { option_ids: selected } : null);
    }
  };

  const submitNumeric = (question: AssessmentQuestion) => {
    const raw = numericDrafts[question.id] ?? (
      question.answer && "value" in question.answer ? String(question.answer.value) : ""
    );
    const value = Number(raw);
    if (!raw.trim() || !Number.isFinite(value)) {
      setSaveError("Enter a valid numeric answer before saving.");
      return;
    }
    void saveAnswer(question, { value });
  };

  const navigateToQuestion = async (nextPosition: number) => {
    if (!attempt || saving || nextPosition < 0 || nextPosition >= attempt.questions.length) return;
    if (nextPosition === attempt.current_position) return;
    setSaving(true);
    setSaveError(null);
    const elapsed = Math.max(0, Math.floor((Date.now() - questionEnteredAt.current) / 1000));
    try {
      await updateAssessmentQuestionPosition(
        attempt.id,
        attempt.questions[nextPosition].id,
        elapsed,
      );
      patchAttempt((current) => ({
        ...current,
        current_position: nextPosition,
        questions: current.questions.map((item, index) => index === nextPosition
          ? { ...item, visited: true }
          : item),
      }));
      questionEnteredAt.current = Date.now();
    } catch (error) {
      setSaveError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const toggleReview = async (question: AssessmentQuestion) => {
    if (!attempt || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      const marked = !question.marked_for_review;
      await setAssessmentQuestionReview(attempt.id, question.id, marked);
      patchAttempt((current) => ({
        ...current,
        questions: current.questions.map((item) => item.id === question.id
          ? { ...item, marked_for_review: marked }
          : item),
      }));
    } catch (error) {
      setSaveError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const clearAnswer = async (question: AssessmentQuestion) => {
    if (!attempt || saving || question.answer === null) return;
    setSaving(true);
    setSaveError(null);
    try {
      await clearAssessmentResponse(attempt.id, question.id);
      patchAttempt((current) => ({
        ...current,
        questions: current.questions.map((item) => item.id === question.id
          ? { ...item, answer: null }
          : item),
      }));
    } catch (error) {
      setSaveError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLElement
        && (target.isContentEditable || target.closest("input, textarea, select, [contenteditable='true']"))
      ) return;
      if (!attempt || !currentQuestion || saving || remainingSeconds === 0) return;

      if (event.key === "ArrowLeft") {
        event.preventDefault();
        void navigateToQuestion(attempt.current_position - 1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        void navigateToQuestion(attempt.current_position + 1);
      } else if (event.key.toLowerCase() === "m") {
        event.preventDefault();
        void toggleReview(currentQuestion);
      } else if (currentQuestion.question_type !== "numeric") {
        const index = /^[1-4]$/.test(event.key)
          ? Number(event.key) - 1
          : /^[a-d]$/i.test(event.key)
            ? event.key.toUpperCase().charCodeAt(0) - 65
            : -1;
        const option = currentQuestion.options[index];
        if (option) {
          event.preventDefault();
          selectOption(currentQuestion, option.id);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [attempt, currentQuestion, remainingSeconds, saving]);

  if (attemptQuery.isLoading) return <div className="exam-shell"><LoadingPanel message="Restoring your saved assessment…" /></div>;
  if (attemptQuery.isError) {
    return <div className="exam-shell"><ErrorPanel error={attemptQuery.error} onRetry={() => void attemptQuery.refetch()} /></div>;
  }
  if (!attempt || !currentQuestion) {
    return <div className="exam-shell"><ErrorPanel error={new Error("This attempt has no available questions.")} /></div>;
  }

  const answeredCount = attempt.questions.filter((question) => question.answer !== null).length;

  return (
    <div className="exam-shell">
      <div className="exam-top">
        <Link to="/aptitude" className="exam-brand">
          <span className="brand-mark"><img src="/mentormuni-logo.png" alt="" /></span>
          MentorMuni <span className="exam-divider">/</span> {attempt.title}
        </Link>
        <span className="exam-candidate">Anonymous candidate</span>
      </div>
      <div className="exam-status">
        <span><span className="live-dot" /> Timed assessment</span>
        <span className="exam-progress-copy">Question {attempt.current_position + 1} of {attempt.question_count}</span>
        <div className="exam-progress"><div style={{ width: `${((attempt.current_position + 1) / attempt.question_count) * 100}%` }} /></div>
        <span className={`exam-timer ${remainingSeconds <= 300 ? "urgent" : ""}`} aria-label={`Time remaining ${formattedTime}`}>
          <Clock3 size={17} /> {formattedTime}
        </span>
      </div>
      <div className="exam-content">
        <div className="exam-question-panel">
          <div className="question-overline">
            <span>QUESTION {String(attempt.current_position + 1).padStart(2, "0")}</span>
            <span className="badge badge-green">{currentQuestion.difficulty}</span>
            <span className="question-topic">{currentQuestion.topic}</span>
          </div>
          <h1>{currentQuestion.prompt}</h1>
          <StimulusBlock stimulus={currentQuestion.stimulus} />
          {currentQuestion.question_type === "numeric" ? (
            <div className="numeric-answer">
              <label htmlFor="numeric-response">Your numeric answer</label>
              <div>
                <input
                  id="numeric-response"
                  inputMode="decimal"
                  value={numericDrafts[currentQuestion.id] ?? (
                    currentQuestion.answer && "value" in currentQuestion.answer
                      ? String(currentQuestion.answer.value)
                      : ""
                  )}
                  disabled={saving || submitting || remainingSeconds === 0}
                  onChange={(event) => setNumericDrafts((drafts) => ({
                    ...drafts,
                    [currentQuestion.id]: event.target.value,
                  }))}
                />
                <button
                  className="button button-primary"
                  disabled={saving || submitting || remainingSeconds === 0}
                  onClick={() => submitNumeric(currentQuestion)}
                >
                  Save answer
                </button>
              </div>
            </div>
          ) : (
            <>
              <p className="question-hint">
                {currentQuestion.question_type === "multi_choice"
                  ? "Select all answers that apply."
                  : "Choose one answer from the options below."}
              </p>
              <div className="answer-options" role="group" aria-label="Answer options">
                {currentQuestion.options.map((option, index) => {
                  const selected = currentQuestion.answer && "option_id" in currentQuestion.answer
                    ? currentQuestion.answer.option_id === option.id
                    : currentQuestion.answer && "option_ids" in currentQuestion.answer
                      ? currentQuestion.answer.option_ids.includes(option.id)
                      : false;
                  return (
                    <button
                      key={option.id}
                      aria-pressed={selected}
                      className={`answer-option ${selected ? "selected" : ""}`}
                      disabled={saving || submitting || remainingSeconds === 0}
                      onClick={() => selectOption(currentQuestion, option.id)}
                    >
                      <span className="option-key">{String.fromCharCode(65 + index)}</span>
                      <span>{option.text}</span>
                      {selected && <Check size={17} className="option-check" />}
                    </button>
                  );
                })}
              </div>
            </>
          )}
          {saving && <p className="assessment-save-status" role="status">Saving your response…</p>}
          {saveError && <p className="assessment-inline-error" role="alert">{saveError}</p>}
          <div className="question-actions">
            <button
              className={`button button-outline ${currentQuestion.marked_for_review ? "marked-button" : ""}`}
              disabled={saving || remainingSeconds === 0}
              onClick={() => void toggleReview(currentQuestion)}
            >
              <Flag size={16} /> {currentQuestion.marked_for_review ? "Marked for review" : "Mark for review"}
            </button>
            <button
              className="clear-button"
              disabled={saving || currentQuestion.answer === null || remainingSeconds === 0}
              onClick={() => void clearAnswer(currentQuestion)}
            >
              <RotateCcw size={15} /> Clear response
            </button>
          </div>
          <div className="exam-navigation">
            <button className="button button-outline" disabled={saving || attempt.current_position === 0} onClick={() => void navigateToQuestion(attempt.current_position - 1)}>
              <ChevronLeft size={16} /> Previous
            </button>
            {attempt.current_position < attempt.question_count - 1
              ? <button className="button button-primary" disabled={saving || remainingSeconds === 0} onClick={() => void navigateToQuestion(attempt.current_position + 1)}>Next question <ChevronRight size={16} /></button>
              : <button className="button button-primary" disabled={saving || remainingSeconds === 0} onClick={() => setConfirmSubmit(true)}>Review and submit <ChevronRight size={16} /></button>}
          </div>
        </div>
        <aside className="exam-palette-panel">
          <h2>Question palette</h2>
          <p>Navigate through your assessment</p>
          <div className="palette-legend">
            <span><i className="palette-dot answered" /> Answered</span>
            <span><i className="palette-dot review" /> Review</span>
            <span><i className="palette-dot" /> Not visited</span>
          </div>
          <div className="question-palette">
            {attempt.questions.map((question, index) => (
              <button
                key={question.id}
                aria-label={`Question ${index + 1}`}
                className={`${index === attempt.current_position ? "current" : ""} ${question.marked_for_review ? "review" : question.answer !== null ? "answered" : ""}`}
                disabled={saving || remainingSeconds === 0}
                onClick={() => void navigateToQuestion(index)}
              >
                {index + 1}
              </button>
            ))}
          </div>
          <div className="palette-note"><ShieldCheck size={16} /><span>Your answers and remaining time are saved by the assessment service.</span></div>
          {submitError && <p className="assessment-inline-error" role="alert">{submitError}</p>}
          <button className="submit-assessment" disabled={submitting} onClick={() => setConfirmSubmit(true)}>
            Submit assessment <ArrowRight size={16} />
          </button>
          {remainingSeconds === 0 && <button className="button button-outline full-button" disabled={submitting} onClick={() => void submit()}>Retry final submission</button>}
          <span className="palette-answered-count">{answeredCount} of {attempt.question_count} answered</span>
        </aside>
      </div>
      {confirmSubmit && (
        <div className="modal-backdrop" role="presentation">
          <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <button className="modal-close" aria-label="Close" onClick={() => setConfirmSubmit(false)}><X size={19} /></button>
            <span className="modal-symbol"><Flag size={21} /></span>
            <h2 id="confirm-title">Submit your assessment?</h2>
            <p>You’ve answered {answeredCount} of {attempt.question_count} questions. You can still go back and review your responses.</p>
            {submitError && <p className="assessment-inline-error" role="alert">{submitError}</p>}
            <div className="modal-actions">
              <button className="button button-outline" disabled={submitting} onClick={() => setConfirmSubmit(false)}>Keep reviewing</button>
              <button className="button button-primary" disabled={submitting} onClick={() => void submit()}>{submitting ? "Submitting…" : "Submit assessment"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function AssessmentResultsPage() {
  const { assessmentId: attemptId = "" } = useParams();
  const navigate = useNavigate();
  const [startingPractice, setStartingPractice] = useState(false);
  const [practiceError, setPracticeError] = useState<string | null>(null);
  const resultQuery = useQuery({
    queryKey: ["assessment-result", attemptId],
    queryFn: () => getAssessmentResult(attemptId),
    enabled: Boolean(attemptId),
    retry: false,
  });
  if (resultQuery.isLoading) return <LoadingPanel message="Calculating your verified assessment results…" />;
  if (resultQuery.isError) return <ErrorPanel error={resultQuery.error} onRetry={() => void resultQuery.refetch()} />;
  const result = resultQuery.data;
  if (!result) return <ErrorPanel error={new Error("No submitted result was returned.")} />;

  const total = result.correct + result.incorrect + result.unanswered;
  const scorePercent = result.max_score <= 0
    ? 0
    : Math.max(0, Math.min(100, Math.round((result.score / result.max_score) * 100)));
  const minutesUsed = Math.floor(result.elapsed_seconds / 60);
  const secondsUsed = result.elapsed_seconds % 60;
  const breakdown = [
    { name: "Correct", value: result.correct },
    { name: "Incorrect", value: result.incorrect },
    { name: "Unanswered", value: result.unanswered },
  ];
  const averageQuestionTime = total > 0
    ? result.review.reduce((sum, question) => sum + question.time_spent_seconds, 0) / total
    : 0;
  const startWeakPractice = async () => {
    setStartingPractice(true);
    setPracticeError(null);
    try {
      const attempt = await startWeakTopicPractice(result.attempt_id);
      navigate(`/exam/${attempt.id}`);
    } catch (error) {
      setPracticeError(errorMessage(error));
    } finally {
      setStartingPractice(false);
    }
  };

  return (
    <>
      <PageHeading
        eyebrow="YOUR ASSESSMENT REPORT"
        title="Your results"
        description={`${result.assessment_title} · ${total} questions`}
        action={<Link className="button button-outline" to="/aptitude">Choose an assessment <ArrowRight size={15} /></Link>}
      />
      <div className="results-hero">
        <div className="results-score"><span>ASSESSMENT SCORE</span><strong>{scorePercent}<small>/100</small></strong><em><ShieldCheck size={14} /> Based on this submitted attempt</em></div>
        <div className="results-divider" />
        <div className="results-stats">
          <div><span>Accuracy</span><strong>{result.accuracy_percent}%</strong></div>
          <div><span>Attempt rate</span><strong>{result.attempt_rate_percent}%</strong></div>
          <div><span>Correct</span><strong>{result.correct} <small>of {total}</small></strong></div>
          <div><span>Time used</span><strong>{minutesUsed}<small>m {secondsUsed}s</small></strong></div>
        </div>
      </div>
      <div className="content-grid results-grid">
        <section className="panel">
          <div className="panel-heading"><div><h2>Section performance</h2><p>Scores calculated using the published marking policy</p></div></div>
          <div className="results-section-list">
            {result.sections.map((section) => {
              const sectionScore = section.max_score <= 0
                ? 0
                : Math.max(0, Math.min(100, Math.round(100 * section.score / section.max_score)));
              return (
                <div className="results-section-row" key={section.section}>
                  <div className="results-section-name">
                    <span className="section-color" style={{ backgroundColor: sectionScore >= 70 ? "#52b788" : "#f0a64b" }} />
                    {section.section}
                    <strong>{sectionScore}%</strong>
                  </div>
                  <div className="progress-track"><div className="progress-fill" style={{ width: `${sectionScore}%` }} /></div>
                </div>
              );
            })}
          </div>
        </section>
        <section className="panel breakdown-panel">
          <div className="panel-heading"><div><h2>Your answer breakdown</h2><p>{total} questions in this submitted attempt</p></div></div>
          <div className="breakdown-layout">
            <div className="donut-wrap" role="img" aria-label={`Out of ${total} questions: ${result.correct} correct, ${result.incorrect} incorrect, ${result.unanswered} unanswered`}>
              <div className="donut-chart"><ResponsiveResultChart data={breakdown} /></div>
              <div className="donut-center"><strong>{total}</strong><span>QUESTIONS</span></div>
            </div>
            <div className="breakdown-legend" aria-label="Question outcomes">
              <BreakdownRow label="Correct" count={result.correct} color="green-dot" />
              <BreakdownRow label="Incorrect" count={result.incorrect} color="red-dot" />
              <BreakdownRow label="Unanswered" count={result.unanswered} color="unanswered-dot" />
            </div>
          </div>
        </section>
      </div>
      {result.topics.length > 0 && (
        <section className="panel topic-performance-panel">
          <div className="panel-heading">
            <div><h2>Topic performance &amp; speed</h2><p>Accuracy and time spent, based on the saved question timings</p></div>
          </div>
          <div className="topic-matrix-wrap">
            <table className="topic-matrix">
              <thead><tr><th>Topic</th><th>Accuracy</th><th>Correct</th><th>Incorrect</th><th>Unanswered</th><th>Avg. time</th></tr></thead>
              <tbody>
                {result.topics.map((topic) => (
                  <tr key={topic.topic}>
                    <th scope="row">{topic.topic}</th>
                    <td>{topic.accuracy_percent}%</td>
                    <td>{topic.correct}</td>
                    <td>{topic.incorrect}</td>
                    <td>{topic.unanswered}</td>
                    <td>{Math.round(topic.avg_time_seconds)} sec</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {practiceError && <p className="assessment-inline-error" role="alert">{practiceError}</p>}
          <button
            className="button button-primary weak-topics-cta"
            disabled={startingPractice}
            onClick={() => void startWeakPractice()}
          >
            {startingPractice ? "Preparing focused practice…" : "Practice my weakest topics"}
            <ArrowRight size={16} />
          </button>
        </section>
      )}
      <section className="panel answer-review-panel">
        <div className="panel-heading"><div><h2>Review your answers</h2><p>See released answers and explanations for this submitted attempt</p></div></div>
        <div className="answer-review-list">
          {result.review.map((question, index) => {
            const selectedText = formatAnswer(question.answer, question.options);
            const correctText = formatAnswer(question.correct_answer, question.options);
            const status = question.is_correct === null
              ? question.answer ? "Answered" : "Unanswered"
              : question.is_correct ? "Correct" : "Incorrect";
            return (
              <article className="answer-review-item" key={question.question_id}>
                <div className="answer-review-heading">
                  <span>Q{index + 1} · {question.topic}</span>
                  <strong>{status}</strong>
                  {question.is_correct === false && question.time_spent_seconds > averageQuestionTime && (
                    <span className="time-sink-badge">Time sink · {question.time_spent_seconds}s</span>
                  )}
                </div>
                <p>{question.prompt}</p>
                <StimulusBlock stimulus={question.stimulus} />
                {question.answer && <small>Your answer: {selectedText}</small>}
                {question.correct_answer && <small>Correct answer: {correctText}</small>}
                {question.explanation && <div className="answer-review-explanation">{question.explanation}</div>}
              </article>
            );
          })}
        </div>
      </section>
      <div className="action-card"><div><h2>Ready to keep improving?</h2><p>Choose another verified assessment when you’re ready.</p></div><Link to="/aptitude" className="button button-primary">Browse assessments <ArrowRight size={16} /></Link></div>
      <p className="simulation-note"><ShieldCheck size={15} /> Your score is calculated by the assessment service and is not a prediction of placement or hiring outcomes.</p>
    </>
  );
}

function formatAnswer(
  answer: AssessmentAnswer | null,
  options: Array<{ id: string; text: string }>,
): string {
  if (!answer) return "";
  if ("value" in answer) return String(answer.value);
  const selectedIds = "option_id" in answer ? [answer.option_id] : answer.option_ids;
  return selectedIds
    .map((id) => options.find((option) => option.id === id)?.text ?? "Response saved")
    .join(", ");
}

function BreakdownRow({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="breakdown-item">
      <span className="breakdown-label"><i className={`legend-dot ${color}`} />{label}</span>
      <span className="breakdown-count"><strong>{count}</strong><small>questions</small></span>
    </div>
  );
}

function ResponsiveResultChart({ data }: { data: Array<{ name: string; value: number }> }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={data} dataKey="value" innerRadius="58%" outerRadius="78%" paddingAngle={3} stroke="#101b2a" strokeWidth={3}>
          <Cell fill="#61c98d" />
          <Cell fill="#f07f79" />
          <Cell fill="#60758b" />
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  );
}
