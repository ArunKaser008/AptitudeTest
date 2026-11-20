import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { assessmentQuestionBanks } from "./data/assessmentQuestionBanks";
import { assessments, questions } from "./data/mockData";
import {
  completePreviewAttempt,
  getPreviewDurationMinutes,
  getPreviewQuestionCount,
  getSecondsRemaining,
  loadPreviewAttempt,
  loadPreviewResult,
  sampleNewQuestionSet,
  sampleQuestions,
  savePreviewAttempt,
  startPreviewAttempt,
} from "./services/previewAssessment";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

function renderApp(initialEntry = "/") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function createAssessmentApiMock({
  assessments = [{
    slug: "foundation",
    title: "Foundation Aptitude Test",
    description: "Published core aptitude assessment.",
    duration_seconds: 600,
    question_count: 10,
    sections: [{ title: "Quantitative", question_count: 10 }],
  }],
  durationSeconds = 600,
  initialIncorrectTimeSink = false,
}: {
  assessments?: Array<Record<string, unknown>>;
  durationSeconds?: number;
  initialIncorrectTimeSink?: boolean;
} = {}) {
  const questions = Array.from({ length: 10 }, (_, index) => ({
    id: `10000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    position: index,
    section: "Quantitative",
    topic: `Topic ${index + 1}`,
    difficulty: "medium" as const,
    question_type: "single_choice" as const,
    prompt: `Production assessment question ${index + 1}`,
    stimulus: null,
    options: [
      { id: "option-a", text: `Correct option ${index + 1}` },
      { id: "option-b", text: `Other option ${index + 1}` },
    ],
    answer: null as { option_id: string } | null,
    marked_for_review: false,
    visited: index === 0,
  }));
  let currentPosition = 0;
  const answers: Record<string, string> = {};
  if (initialIncorrectTimeSink) answers[questions[0].id] = "option-b";
  const marked: Record<string, boolean> = {};
  const attemptId = "20000000-0000-4000-8000-000000000001";

  const makeResult = () => {
    const correct = Object.entries(answers).filter(([, optionId]) => optionId === "option-a").length;
    const attempted = Object.keys(answers).length;
    return {
      attempt_id: attemptId,
      assessment_slug: "foundation",
      assessment_title: "Foundation Aptitude Test",
      status: "submitted",
      score: correct * 10,
      max_score: 100,
      correct,
      incorrect: attempted - correct,
      unanswered: 10 - attempted,
      accuracy_percent: attempted ? correct / attempted * 100 : 0,
      attempt_rate_percent: attempted * 10,
      elapsed_seconds: 42,
      sections: [{
        section: "Quantitative",
        score: correct * 10,
        max_score: 100,
        correct,
        incorrect: attempted - correct,
        unanswered: 10 - attempted,
        accuracy_percent: attempted ? correct / attempted * 100 : 0,
      }],
      topics: [{
        topic: "Topic 1",
        correct,
        incorrect: attempted - correct,
        unanswered: 10 - attempted,
        accuracy_percent: attempted ? correct / attempted * 100 : 0,
        avg_time_seconds: 12,
      }],
      review: questions.map((question) => ({
        question_id: question.id,
        position: question.position,
        section: question.section,
        topic: question.topic,
        prompt: question.prompt,
        stimulus: null,
        options: question.options,
        answer: answers[question.id] ? { option_id: answers[question.id] } : null,
        correct_answer: { option_id: "option-a" },
        explanation: "This answer follows from the question data.",
        is_correct: answers[question.id] ? answers[question.id] === "option-a" : null,
        time_spent_seconds: question.position === 0 ? 20 : 2,
      })),
    };
  };

  const fetcher = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const path = url.pathname.replace("/api/v1", "");
    const method = init.method ?? "GET";
    const respond = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });

    if (path === "/candidate-sessions" && method === "POST") {
      return respond({ session_token: "candidate-test-token", expires_at: new Date(Date.now() + 86_400_000).toISOString() }, 201);
    }
    if (path === "/assessments" && method === "GET") return respond(assessments);
    if (path === "/practice-weak-topics" && method === "POST") {
      return respond({ id: attemptId, title: "Focused practice", question_count: 10 }, 201);
    }
    if (path === "/attempts" && method === "POST") {
      const now = Date.now();
      currentPosition = 0;
      return respond({
        id: attemptId,
        assessment_slug: "foundation",
        title: "Foundation Aptitude Test",
        status: "in_progress",
        started_at: new Date(now).toISOString(),
        deadline_at: new Date(now + durationSeconds * 1000).toISOString(),
        server_time: new Date(now).toISOString(),
        question_count: questions.length,
        current_position: currentPosition,
      }, 201);
    }
    if (path === `/attempts/${attemptId}` && method === "GET") {
      const now = Date.now();
      return respond({
        id: attemptId,
        assessment_slug: "foundation",
        title: "Foundation Aptitude Test",
        status: "in_progress",
        started_at: new Date(now).toISOString(),
        deadline_at: new Date(now + durationSeconds * 1000).toISOString(),
        server_time: new Date(now).toISOString(),
        question_count: questions.length,
        current_position: currentPosition,
        questions: questions.map((question) => ({
          ...question,
          answer: answers[question.id] ? { option_id: answers[question.id] } : null,
          marked_for_review: Boolean(marked[question.id]),
          visited: question.position <= currentPosition,
        })),
      });
    }
    const responseMatch = path.match(/^\/attempts\/[^/]+\/responses\/([^/]+)$/);
    if (responseMatch && method === "PUT") {
      const body = JSON.parse(String(init.body)) as { answer: { option_id: string } };
      answers[responseMatch[1]] = body.answer.option_id;
      return respond({ question_id: responseMatch[1], answer: body.answer, saved_at: new Date().toISOString() });
    }
    if (responseMatch && method === "DELETE") return new Response(null, { status: 204 });
    const reviewMatch = path.match(/^\/attempts\/[^/]+\/questions\/([^/]+)\/review$/);
    if (reviewMatch && method === "PATCH") {
      const body = JSON.parse(String(init.body)) as { marked: boolean };
      marked[reviewMatch[1]] = body.marked;
      return respond({ marked: body.marked });
    }
    if (path === `/attempts/${attemptId}/position` && method === "PATCH") {
      const body = JSON.parse(String(init.body)) as { question_id: string };
      currentPosition = questions.find((question) => question.id === body.question_id)?.position ?? 0;
      return respond({ current_position: currentPosition });
    }
    if (path === `/attempts/${attemptId}/submit` && method === "POST") return respond(makeResult());
    if (path === `/attempts/${attemptId}/results` && method === "GET") return respond(makeResult());
    throw new Error(`Unexpected API request: ${method} ${path}`);
  });

  vi.stubGlobal("fetch", fetcher);
  return { fetcher, questions, attemptId };
}

describe("student workspace preview", () => {
  it("creates distinct questions without duplicates within each preview set", () => {
    sessionStorage.clear();
    const first = sampleNewQuestionSet("distinct-set-test", questions, 10, () => 0.5);
    const second = sampleNewQuestionSet("distinct-set-test", questions, 10, () => 0.5);

    expect(new Set(first.map((question) => question.id)).size).toBe(10);
    expect(new Set(second.map((question) => question.id)).size).toBe(10);
    expect(first.map((question) => question.id).some((id) => second.some((question) => question.id === id))).toBe(false);
  });

  it("caps a requested set at the available question count", () => {
    expect(sampleQuestions(questions.slice(0, 3), 10)).toHaveLength(3);
    expect(assessments.every((assessment) => getPreviewQuestionCount(assessment, questions) === 10)).toBe(true);
    expect(getPreviewQuestionCount(assessments[0], questions.slice(0, 3))).toBe(3);
  });

  it("uses validated, distinct assessment banks and rotates fresh section-balanced sets", () => {
    const bankIds = assessments.map((assessment) => {
      const bank = assessmentQuestionBanks[assessment.id];
      expect(bank).toHaveLength(20);
      expect(new Set(bank.map((question) => question.id)).size).toBe(bank.length);
      for (const question of bank) {
        expect(question.options.length).toBeGreaterThan(1);
        expect(question.answer).toBeGreaterThanOrEqual(0);
        expect(question.answer).toBeLessThan(question.options.length);
        expect(question.prompt.trim()).not.toBe("");
        expect(question.explanation.trim()).not.toBe("");
        expect(question.section).toBeTruthy();
      }
      return bank.map((question) => question.id);
    });

    expect(bankIds[0].some((id) => bankIds[1].includes(id))).toBe(false);
    expect(bankIds[0].some((id) => bankIds[2].includes(id))).toBe(false);
    expect(bankIds[1].some((id) => bankIds[2].includes(id))).toBe(false);

    for (const assessment of assessments) {
      sessionStorage.clear();
      const bank = assessmentQuestionBanks[assessment.id];
      const first = sampleNewQuestionSet(assessment.id, bank, 10, () => 0.5, assessment.previewDistribution);
      const second = sampleNewQuestionSet(assessment.id, bank, 10, () => 0.5, assessment.previewDistribution);
      const sectionCounts = Object.fromEntries(Object.keys(assessment.previewDistribution).map((section) => [
        section,
        first.filter((question) => question.section === section).length,
      ]));

      expect(first).toHaveLength(10);
      expect(second).toHaveLength(10);
      expect(first.every((question) => !second.some((next) => next.id === question.id))).toBe(true);
      expect(sectionCounts).toEqual(assessment.previewDistribution);
    }
  });

  it("scales each 10-question preview to a realistic duration", () => {
    expect(assessments.map((assessment) => getPreviewDurationMinutes(
      assessment,
      assessmentQuestionBanks[assessment.id],
    ))).toEqual([10, 15, 15]);
  });

  it("restores an in-progress attempt and stores the matching result after submission", () => {
    const assessment = assessments[0];
    const bank = assessmentQuestionBanks[assessment.id];
    const attempt = startPreviewAttempt(assessment, bank, () => 0.5);
    const savedAttempt = { ...attempt, currentQuestion: 2, responses: { [attempt.questionIds[0]]: 1 } };
    savePreviewAttempt(savedAttempt);

    expect(loadPreviewAttempt(assessment, bank)).toEqual(savedAttempt);

    const result = {
      assessmentId: assessment.id,
      questionIds: savedAttempt.questionIds,
      responses: savedAttempt.responses,
      elapsedSeconds: 30,
    };
    completePreviewAttempt(result);

    expect(loadPreviewAttempt(assessment, bank)).toBeNull();
    expect(loadPreviewResult(assessment.id)).toEqual(result);
  });

  it("uses an absolute deadline for every assessment and restores remaining time after elapsed time", () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000);

    for (const assessment of assessments) {
      const bank = assessmentQuestionBanks[assessment.id];
      const attempt = startPreviewAttempt(assessment, bank, () => 0.5);
      const durationSeconds = getPreviewDurationMinutes(assessment, bank) * 60;
      expect(attempt.durationSeconds).toBe(durationSeconds);
      expect(attempt.deadlineAt - Date.now()).toBe(durationSeconds * 1000);
      expect(getSecondsRemaining(attempt.deadlineAt)).toBe(durationSeconds);
    }

    const attempt = loadPreviewAttempt(assessments[0], assessmentQuestionBanks[assessments[0].id]);
    expect(attempt).not.toBeNull();
    if (!attempt) throw new Error("The assessment attempt was not restored.");
    vi.setSystemTime(Date.now() + 20_000);
    expect(getSecondsRemaining(attempt.deadlineAt)).toBe(attempt.durationSeconds - 20);
  });

  it("migrates a stored remaining-time attempt to a persistent deadline", () => {
    vi.useFakeTimers();
    vi.setSystemTime(2_000_000);
    const assessment = assessments[0];
    const bank = assessmentQuestionBanks[assessment.id];
    const attempt = startPreviewAttempt(assessment, bank, () => 0.5);
    const legacyAttempt = { ...attempt, remainingSeconds: 30 } as typeof attempt & { remainingSeconds: number };
    delete (legacyAttempt as Partial<typeof legacyAttempt>).deadlineAt;
    sessionStorage.setItem(`mentormuni:preview:attempt:${assessments[0].id}`, JSON.stringify(legacyAttempt));

    const restored = loadPreviewAttempt(assessment, bank);
    expect(restored?.deadlineAt).toBe(2_030_000);
    expect(restored).not.toHaveProperty("remainingSeconds");
  });

  it("shows readiness and provides a route to assessment discovery", () => {
    renderApp();

    expect(screen.getByRole("heading", { name: /good afternoon, arun/i })).toBeInTheDocument();
    expect(screen.getAllByText("68")).toHaveLength(2);
    expect(screen.getByRole("link", { name: /take an assessment/i })).toHaveAttribute("href", "/aptitude");
  });

  it("checks practice answers and reveals an explanation", async () => {
    const user = userEvent.setup();
    renderApp("/practice");

    await user.click(screen.getByRole("button", { name: /start timed practice/i }));
    const prompt = screen.getByRole("heading", { level: 2 }).textContent;
    const question = questions.find((item) => item.prompt === prompt);
    expect(question).toBeDefined();
    if (!question) throw new Error("The practice question was not found in the question bank.");
    await user.click(screen.getByRole("button", {
      name: `${String.fromCharCode(65 + question.answer)} ${question.options[question.answer]}`,
    }));
    await user.click(screen.getByRole("button", { name: /check answer/i }));

    expect(screen.getByText("That’s right!")).toBeInTheDocument();
    expect(screen.getByText(question.explanation)).toBeInTheDocument();
  });

  it("submits a server-backed assessment when its server deadline expires", async () => {
    const user = userEvent.setup();
    const now = 6_000_000;
    vi.spyOn(Date, "now").mockReturnValue(now);
    createAssessmentApiMock({ durationSeconds: 2 });
    renderApp("/aptitude");

    await user.click(await screen.findByRole("button", { name: /start assessment/i }));
    expect(await screen.findByLabelText("Time remaining 00:00:02")).toBeInTheDocument();
    vi.spyOn(Date, "now").mockReturnValue(now + 2_000);
    act(() => {
      window.dispatchEvent(new Event("focus"));
    });
    expect(await screen.findByRole("heading", { name: "Your results" }, { timeout: 5000 })).toBeInTheDocument();
  });

  it("ends timed practice when its one-minute-per-question deadline passes", () => {
    vi.useFakeTimers();
    vi.setSystemTime(4_000_000);
    renderApp("/practice");
    fireEvent.click(screen.getByRole("button", { name: /start timed practice/i }));

    expect(screen.getByLabelText("Time remaining 10:00")).toBeInTheDocument();
    act(() => {
      vi.setSystemTime(Date.now() + 10 * 60 * 1000);
      window.dispatchEvent(new Event("focus"));
    });

    expect(screen.getByText("Time’s up")).toBeInTheDocument();
    expect(screen.getByText(/timed preview ended after 0 of 10 questions/i)).toBeInTheDocument();
    expect(screen.getByText("0", { selector: ".practice-progress-stat strong" })).toBeInTheDocument();
  });

  it("restores timed practice without resetting its deadline after refresh", () => {
    vi.useFakeTimers();
    vi.setSystemTime(5_000_000);
    renderApp("/practice");
    fireEvent.click(screen.getByRole("button", { name: /start timed practice/i }));
    expect(screen.getByLabelText("Time remaining 10:00")).toBeInTheDocument();

    act(() => {
      vi.setSystemTime(Date.now() + 20_000);
      window.dispatchEvent(new Event("focus"));
    });
    expect(screen.getByLabelText("Time remaining 09:40")).toBeInTheDocument();

    cleanup();
    renderApp("/practice");
    expect(screen.getByLabelText("Time remaining 09:40")).toBeInTheDocument();
    expect(screen.getByText("Question 1 of 10")).toBeInTheDocument();
  });

  it("persists responses and question navigation through the assessment API", async () => {
    const user = userEvent.setup();
    const api = createAssessmentApiMock();
    renderApp(`/exam/${api.attemptId}`);

    const option = await screen.findByRole("button", { name: "A Correct option 1" });
    await user.click(option);
    expect(option).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: /next question/i }));
    await user.click(screen.getByRole("button", { name: /previous/i }));

    expect(await screen.findByRole("heading", { name: "Production assessment question 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "A Correct option 1" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows a real empty state when no verified assessments are published", async () => {
    createAssessmentApiMock({ assessments: [] });
    renderApp("/aptitude");

    expect(await screen.findByRole("heading", { name: "No assessments are published yet" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start assessment/i })).not.toBeInTheDocument();
  });

  it("uses the server assessment total from start through submitted results", async () => {
    sessionStorage.clear();
    const user = userEvent.setup();
    const { fetcher } = createAssessmentApiMock();
    renderApp("/aptitude");

    await user.click(await screen.findByRole("button", { name: /start assessment/i }));
    expect(await screen.findByText("Question 1 of 10")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Question \d+$/ })).toHaveLength(10);

    await user.click(screen.getByRole("button", { name: "A Correct option 1" }));
    await user.click(screen.getByRole("button", { name: "Submit assessment" }));
    expect(screen.getByText(/You’ve answered 1 of 10 questions/)).toBeInTheDocument();
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Submit assessment" }));

    expect(await screen.findByText(/Foundation Aptitude Test · 10 questions/)).toBeInTheDocument();
    const submitCall = fetcher.mock.calls.find(([input]) => new URL(String(input)).pathname.endsWith("/submit"));
    const submitBody = JSON.parse(String(submitCall?.[1]?.body)) as {
      question_id: string;
      time_spent_seconds: number;
    };
    expect(submitBody.question_id).toBe("10000000-0000-4000-8000-000000000001");
    expect(submitBody.time_spent_seconds).toBeGreaterThanOrEqual(0);
    expect(screen.getByText("10", { selector: ".donut-center strong" })).toBeInTheDocument();
    expect(screen.getByText("100%", { selector: ".results-stats strong" })).toBeInTheDocument();
    expect(screen.getAllByText("Unanswered").length).toBeGreaterThan(0);
    expect(screen.getByText("1", { selector: ".breakdown-legend strong" })).toBeInTheDocument();
    expect(screen.getByText("9", { selector: ".breakdown-legend strong" })).toBeInTheDocument();
    expect(screen.getAllByText(/Correct answer:/)).toHaveLength(10);
  });

  it("renders topic diagnostics and flags slow incorrect answers as time sinks", async () => {
    createAssessmentApiMock({ initialIncorrectTimeSink: true });
    renderApp("/results/20000000-0000-4000-8000-000000000001");

    expect(await screen.findByRole("heading", { name: "Topic performance & speed" })).toBeInTheDocument();
    expect(screen.getByText("Time sink · 20s")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /practice my weakest topics/i }));
    expect(await screen.findByRole("heading", { name: "Production assessment question 1" })).toBeInTheDocument();
  });
});
