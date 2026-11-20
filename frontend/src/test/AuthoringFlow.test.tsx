import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssessmentBuilderTab } from "../components/authoring/AssessmentBuilderTab";
import { QuestionBankTab } from "../components/authoring/QuestionBankTab";
import { StimulusBlock } from "../components/exam/StimulusBlock";
import type { AuthoringAssessment, AuthoringQuestion } from "../services/authoringApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderWithQuery(component: React.ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {component}
    </QueryClientProvider>,
  );
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("authoring studio", () => {
  it("renders a structured data stimulus as a readable table", () => {
    render(
      <StimulusBlock stimulus={{
        kind: "table",
        title: "Quarterly revenue",
        headers: ["Quarter", "Revenue"],
        rows: [["Q1", 125], ["Q2", 150]],
      }} />,
    );

    expect(screen.getByRole("heading", { name: "Quarterly revenue" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
  });

  it("validates and saves a question draft from the authoring form", async () => {
    const user = userEvent.setup();
    let createdQuestion: AuthoringQuestion | null = null;
    const fetcher = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      const method = init.method ?? "GET";
      if (url.pathname === "/api/v1/authoring/questions" && method === "GET") {
        return jsonResponse({
          items: createdQuestion ? [createdQuestion] : [],
          total: createdQuestion ? 1 : 0,
          page: 1,
          page_size: 100,
        });
      }
      if (url.pathname === "/api/v1/authoring/questions" && method === "POST") {
        const draft = JSON.parse(String(init.body)) as Omit<AuthoringQuestion, "id" | "logical_id" | "version_number" | "status" | "verified_at" | "usage_count">;
        createdQuestion = {
          ...draft,
          id: "30000000-0000-4000-8000-000000000001",
          logical_id: "40000000-0000-4000-8000-000000000001",
          version_number: 1,
          status: "draft",
          verified_at: null,
          usage_count: 0,
        };
        return jsonResponse(createdQuestion, 201);
      }
      throw new Error(`Unexpected request ${method} ${url.pathname}`);
    });
    vi.stubGlobal("fetch", fetcher);
    renderWithQuery(<QuestionBankTab />);

    await user.click(await screen.findByRole("button", { name: /new question/i }));
    const saveButton = screen.getByRole("button", { name: "Save as draft" });
    expect(saveButton).toBeDisabled();
    await user.type(screen.getByLabelText("Question text"), "What is 2 + 2?");
    await user.type(screen.getByLabelText("Topic"), "Arithmetic");
    fireEvent.change(screen.getByLabelText("Options JSON"), {
      target: { value: JSON.stringify([{ id: "four", text: "4" }, { id: "five", text: "5" }]) },
    });
    fireEvent.change(screen.getByLabelText("Correct answer JSON"), {
      target: { value: JSON.stringify({ option_id: "four" }) },
    });
    await user.type(screen.getByLabelText("Verified explanation"), "Add the two values.");

    expect(saveButton).toBeEnabled();
    await user.click(saveButton);

    expect(await screen.findByRole("button", { name: "Edit What is 2 + 2?" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Create question" })).not.toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining("/authoring/questions"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("updates readiness after adding a verified question to a section pool", async () => {
    const user = userEvent.setup();
    let ready = false;
    const question: AuthoringQuestion = {
      id: "30000000-0000-4000-8000-000000000001",
      logical_id: "40000000-0000-4000-8000-000000000001",
      version_number: 1,
      status: "published",
      verified_at: "2026-11-20T00:00:00Z",
      usage_count: 0,
      question_type: "single_choice",
      prompt: "What is 2 + 2?",
      stimulus: null,
      topic: "Arithmetic",
      difficulty: "easy",
      options: [{ id: "four", text: "4" }, { id: "five", text: "5" }],
      correct_answer: { option_id: "four" },
      explanation: "Add the two values.",
      marks: 1,
      negative_marks: 0,
    };
    const assessment = (): AuthoringAssessment => ({
      id: "50000000-0000-4000-8000-000000000001",
      slug: "foundation",
      title: "Foundation Aptitude Test",
      description: "",
      status: "draft",
      config_version_id: "60000000-0000-4000-8000-000000000001",
      config_version_number: 1,
      config_status: "draft",
      duration_seconds: 600,
      show_explanations_after_submission: true,
      randomize_questions: true,
      randomize_options: true,
      scoring_policy: { minimum_score_zero: true },
      eligible_verified_count: ready ? 1 : 0,
      required_question_count: 1,
      ready,
      sections: [{
        id: "70000000-0000-4000-8000-000000000001",
        section_key: "quantitative",
        title: "Quantitative",
        position: 0,
        question_count: 1,
        marks_per_question: 1,
        negative_marks: 0,
        eligible_verified_count: ready ? 1 : 0,
        ready,
        question_version_ids: ready ? [question.id] : [],
      }],
    });
    const fetcher = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      const method = init.method ?? "GET";
      if (url.pathname === "/api/v1/authoring/assessments" && method === "GET") return jsonResponse([assessment()]);
      if (url.pathname === "/api/v1/authoring/questions" && method === "GET") {
        return jsonResponse({ items: [question], total: 1, page: 1, page_size: 100 });
      }
      if (url.pathname.includes("/pool") && method === "PUT") {
        ready = true;
        return jsonResponse(assessment().sections[0]);
      }
      if (url.pathname.endsWith("/publish") && method === "POST") {
        ready = true;
        return jsonResponse(assessment());
      }
      throw new Error(`Unexpected request ${method} ${url.pathname}`);
    });
    vi.stubGlobal("fetch", fetcher);
    renderWithQuery(<AssessmentBuilderTab />);

    const publishButton = await screen.findByRole("button", { name: /publish/i });
    expect(publishButton).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Manage pool" }));
    const picker = await screen.findByRole("dialog", { name: "Quantitative" });
    await user.click(within(picker).getByLabelText(/What is 2 \+ 2/));
    await user.click(within(picker).getByRole("button", { name: "Save question pool" }));

    expect(await screen.findByText("1 / 1 verified pool questions")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /publish/i })).toBeEnabled();
  });
});
