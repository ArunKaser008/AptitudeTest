import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  PlacementLoginForm,
  PlacementResult,
  PlacementRunner,
  QuestionEditor,
} from "./PlacementPortal";
import type { AttemptResult, PlacementAttempt, PlacementUser } from "./services/placementApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

const user: PlacementUser = {
  id: "user-1",
  email: "student@example.com",
  display_name: "Student",
  role: "student",
  college_id: "college-1",
  batch_id: "batch-1",
};

const attempt: PlacementAttempt = {
  id: "attempt-1",
  test_id: "test-1",
  title: "Placement readiness",
  status: "in_progress",
  started_at: "2026-01-01T10:00:00Z",
  deadline_at: "2026-01-01T10:30:00Z",
  server_time: "2026-01-01T10:00:00Z",
  questions: [{
    position: 0,
    section_name: "Quant",
    question_id: "question-1",
    topic_slug: "percentages",
    subtopic: "discounts",
    question_type: "mcq_single",
    stem: "A placement question stem?",
    stimulus: {
      kind: "table",
      title: "Campus hiring dashboard",
      headers: ["Cohort", "Candidates"],
      rows: [["A", 120]],
    },
    latex: null,
    code_language: null,
    options: [
      { id: "a", text: "Option A" },
      { id: "b", text: "Option B" },
      { id: "c", text: "Option C" },
      { id: "d", text: "Option D" },
    ],
    difficulty: "medium",
    estimated_seconds: 60,
    selected_option_id: null,
    marked_for_review: false,
  }],
};

const result: AttemptResult = {
  attempt_id: "attempt-1",
  test_id: "test-1",
  score: 1,
  max_score: 1,
  accuracy_percent: 100,
  passed: true,
  correct: 1,
  incorrect: 0,
  unanswered: 0,
  topic_breakdown: [{
    topic_slug: "percentages",
    correct: 1,
    incorrect: 0,
    unanswered: 0,
    accuracy_percent: 100,
    avg_time_seconds: 25,
  }],
  answers: [{
    question_id: "question-1",
    position: 0,
    topic_slug: "percentages",
    stem: "A placement question stem?",
    options: attempt.questions[0].options,
    selected_option_id: "b",
    correct_option_id: "b",
    is_correct: true,
    time_spent_seconds: 25,
    mistake_tag: "fast_accurate",
    shortcut_solution: "Use the percentage change formula.",
    concept_solution: "Compare the change with the original amount.",
    estimated_seconds: 60,
  }],
};

describe("placement portal", () => {
  it("authenticates through the placement endpoint and keeps its token separate", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
      access_token: "placement-token",
      user,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const onLogin = vi.fn();
    render(<PlacementLoginForm onLogin={onLogin} />);

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "student@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(onLogin).toHaveBeenCalledWith(user, "placement-token"));
    expect(sessionStorage.getItem("mentormuni:placement-token:v1")).toBe("placement-token");
    expect(sessionStorage.getItem("mentormuni:candidate-token:v1")).toBeNull();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/placement/login");
  });

  it("renders a safe active attempt without exposing answer keys or solutions", async () => {
    const savedAttempt = {
      ...attempt,
      questions: [{ ...attempt.questions[0], selected_option_id: "b" }],
    };
    vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify(savedAttempt), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })));
    render(<PlacementRunner
      attempt={attempt}
      onAttemptChange={vi.fn()}
      onResult={vi.fn()}
      onExit={vi.fn()}
      result={null}
    />);

    fireEvent.click(screen.getByRole("button", { name: /Option B/ }));
    await waitFor(() => expect(screen.getByText("Answer saved")).toBeInTheDocument());
    expect(screen.getByText("Campus hiring dashboard")).toBeInTheDocument();
    expect(screen.getByText("Candidates")).toBeInTheDocument();
    expect(screen.getByText("Option A")).toBeInTheDocument();
    expect(screen.queryByText(/correct answer/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/shortcut solution/i)).not.toBeInTheDocument();
  });

  it("shows topic speed diagnostics and both solutions only in submitted review", () => {
    render(<PlacementResult attempt={attempt} result={result} onExit={vi.fn()} />);
    expect(screen.getByText("Accuracy & speed matrix")).toBeInTheDocument();
    expect(screen.getAllByText("percentages").length).toBeGreaterThan(0);
    expect(screen.getByText("Review solutions")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Review solutions" }));
    expect(screen.getByText("Use the percentage change formula.")).toBeInTheDocument();
    expect(screen.getByText("Compare the change with the original amount.")).toBeInTheDocument();
  });

  it("generates weak-topic drills and reveals their solutions after an answer", async () => {
    const drill = {
      topic_slug: "percentages",
      subtopic: "discounts",
      question_type: "mcq_single",
      stem: "A platform fee changes by 10%. What is the change?",
      options: [
        { id: "a", text: "10" },
        { id: "b", text: "20" },
        { id: "c", text: "30" },
        { id: "d", text: "40" },
      ],
      correct_option_id: "a",
      shortcut_solution: "Take ten percent of the original value.",
      concept_solution: "A percentage is the change divided by the original value.",
      estimated_seconds: 60,
      difficulty: "medium",
      stimulus: null,
      latex: null,
      code_language: null,
    };
    vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify([drill]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })));
    render(<PlacementResult attempt={attempt} result={result} onExit={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /practice weak topics/i }));

    expect(await screen.findByText(drill.stem)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "10" }));
    expect(screen.getByText(drill.shortcut_solution)).toBeInTheDocument();
    expect(screen.getByText(drill.concept_solution)).toBeInTheDocument();
  });

  it("rejects duplicate answer choices before creating a question", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<QuestionEditor collegeId="college-1" onCreated={vi.fn(async () => undefined)} />);
    fireEvent.change(screen.getByLabelText("Question stem"), { target: { value: "Question with duplicate answers?" } });
    fireEvent.change(screen.getByLabelText("Topic slug"), { target: { value: "percentages" } });
    fireEvent.change(screen.getByLabelText("Shortcut solution"), { target: { value: "Calculate the percentage." } });
    fireEvent.change(screen.getByLabelText("Concept solution"), { target: { value: "Compare both values." } });
    fireEvent.change(screen.getByLabelText("Option 1"), { target: { value: "Same" } });
    fireEvent.change(screen.getByLabelText("Option 2"), { target: { value: "Same" } });
    fireEvent.change(screen.getByLabelText("Option 3"), { target: { value: "Different 3" } });
    fireEvent.change(screen.getByLabelText("Option 4"), { target: { value: "Different 4" } });
    fireEvent.click(screen.getByRole("button", { name: /save as draft/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("four non-empty, distinct answer options");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
