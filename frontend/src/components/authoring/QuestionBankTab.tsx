import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BookOpenCheck, Check, CirclePlus, FileUp, Pencil, Search, X } from "lucide-react";
import { StimulusBlock } from "../exam/StimulusBlock";
import {
  archiveQuestion,
  createQuestion,
  importQuestions,
  listAuthoringQuestions,
  updateQuestion,
  verifyPublishQuestion,
  type AuthoringQuestion,
  type AuthoringQuestionDraft,
  type QuestionDifficulty,
  type QuestionStatus,
} from "../../services/authoringApi";
import type { QuestionStimulus } from "../../services/assessmentApi";

type Props = {
  question?: AuthoringQuestion;
  onClose: () => void;
  onSaved: (question: AuthoringQuestion, keepOpen: boolean) => void;
};

const emptyDraft: AuthoringQuestionDraft = {
  question_type: "single_choice",
  prompt: "",
  stimulus: null,
  topic: "",
  difficulty: "medium",
  options: [
    { id: "option-a", text: "" },
    { id: "option-b", text: "" },
  ],
  correct_answer: { option_id: "option-a" },
  explanation: "",
  marks: 1,
  negative_marks: 0,
  source_reference: "",
};

function isStimulus(value: unknown): value is QuestionStimulus {
  if (!value || typeof value !== "object" || !("kind" in value)) return false;
  const stimulus = value as Record<string, unknown>;
  if (stimulus.kind === "passage") return typeof stimulus.content === "string" && Boolean(stimulus.content.trim());
  if (stimulus.kind === "code") {
    return typeof stimulus.content === "string" && Boolean(stimulus.content.trim())
      && typeof stimulus.language === "string" && Boolean(stimulus.language.trim());
  }
  if (stimulus.kind === "table") {
    const headers = stimulus.headers;
    const rows = stimulus.rows;
    return Array.isArray(headers) && headers.length > 0
      && headers.every((header) => typeof header === "string")
      && Array.isArray(rows)
      && rows.every((row) => Array.isArray(row) && row.length === headers.length);
  }
  return false;
}

function parseDraft(fields: {
  questionType: AuthoringQuestionDraft["question_type"];
  prompt: string;
  topic: string;
  difficulty: QuestionDifficulty;
  optionsJson: string;
  correctJson: string;
  stimulusJson: string;
  explanation: string;
  marks: string;
  negativeMarks: string;
  source: string;
}): { draft?: AuthoringQuestionDraft; errors: string[] } {
  const errors: string[] = [];
  let options: AuthoringQuestionDraft["options"] = [];
  let correctAnswer: Record<string, unknown> = {};
  let stimulus: QuestionStimulus | null = null;
  try {
    const parsed: unknown = JSON.parse(fields.optionsJson);
    if (!Array.isArray(parsed) || parsed.some((item) => !item || typeof item.id !== "string" || typeof item.text !== "string")) {
      errors.push("Options must be a JSON array with non-empty id and text fields.");
    } else {
      options = parsed as AuthoringQuestionDraft["options"];
    }
  } catch {
    errors.push("Options must be valid JSON.");
  }
  try {
    const parsed: unknown = JSON.parse(fields.correctJson);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      errors.push("The correct answer must be a JSON object.");
    } else {
      correctAnswer = parsed as Record<string, unknown>;
    }
  } catch {
    errors.push("The correct answer must be valid JSON.");
  }
  if (fields.stimulusJson.trim()) {
    try {
      const parsed: unknown = JSON.parse(fields.stimulusJson);
      if (!isStimulus(parsed)) errors.push("Stimulus must be a valid passage, table, or code block.");
      else stimulus = parsed;
    } catch {
      errors.push("Stimulus must be valid JSON.");
    }
  }
  const optionIds = options.map((option) => option.id);
  if (new Set(optionIds).size !== optionIds.length) errors.push("Option IDs must be unique.");
  if (fields.questionType === "single_choice" && (
    options.length < 2
    || typeof correctAnswer.option_id !== "string"
    || !optionIds.includes(correctAnswer.option_id)
  )) errors.push("Single-choice questions need two or more options and one matching correct option_id.");
  if (fields.questionType === "multi_choice") {
    const ids = correctAnswer.option_ids;
    if (
      options.length < 2
      || !Array.isArray(ids)
      || ids.length === 0
      || ids.some((id) => typeof id !== "string" || !optionIds.includes(id))
      || new Set(ids).size !== ids.length
    ) errors.push("Multiple-choice questions need valid, unique correct option_ids.");
  }
  if (fields.questionType === "numeric") {
    const answerValue = correctAnswer.value;
    const tolerance = correctAnswer.tolerance ?? 0;
    if (
      options.length > 0
      || typeof answerValue !== "number"
      || !Number.isFinite(answerValue)
      || typeof tolerance !== "number"
      || !Number.isFinite(tolerance)
      || tolerance < 0
    ) errors.push("Numeric questions need a finite value, optional non-negative tolerance, and no options.");
  }
  const marks = Number(fields.marks);
  const negativeMarks = Number(fields.negativeMarks);
  if (!fields.prompt.trim()) errors.push("Question text is required.");
  if (!fields.topic.trim()) errors.push("Topic is required.");
  if (!fields.explanation.trim()) errors.push("A verified explanation is required.");
  if (!Number.isFinite(marks) || marks < 0) errors.push("Marks must be a non-negative number.");
  if (!Number.isFinite(negativeMarks) || negativeMarks < 0) errors.push("Negative marks must be a non-negative number.");
  if (errors.length) return { errors };
  return {
    errors,
    draft: {
      question_type: fields.questionType,
      prompt: fields.prompt.trim(),
      stimulus,
      topic: fields.topic.trim(),
      difficulty: fields.difficulty,
      options,
      correct_answer: correctAnswer,
      explanation: fields.explanation.trim(),
      marks,
      negative_marks: negativeMarks,
      source_reference: fields.source.trim() || null,
    },
  };
}

function QuestionEditor({ question, onClose, onSaved }: Props) {
  const [questionType, setQuestionType] = useState<AuthoringQuestionDraft["question_type"]>(question?.question_type ?? "single_choice");
  const [prompt, setPrompt] = useState(question?.prompt ?? "");
  const [topic, setTopic] = useState(question?.topic ?? "");
  const [difficulty, setDifficulty] = useState<QuestionDifficulty>(question?.difficulty ?? "medium");
  const [optionsJson, setOptionsJson] = useState(JSON.stringify(question?.options ?? emptyDraft.options, null, 2));
  const [correctJson, setCorrectJson] = useState(JSON.stringify(question?.correct_answer ?? emptyDraft.correct_answer, null, 2));
  const [stimulusJson, setStimulusJson] = useState(question?.stimulus ? JSON.stringify(question.stimulus, null, 2) : "");
  const [explanation, setExplanation] = useState(question?.explanation ?? "");
  const [marks, setMarks] = useState(String(question?.marks ?? 1));
  const [negativeMarks, setNegativeMarks] = useState(String(question?.negative_marks ?? 0));
  const [source, setSource] = useState(question?.source_reference ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();
  const parsed = useMemo(() => parseDraft({
    questionType,
    prompt,
    topic,
    difficulty,
    optionsJson,
    correctJson,
    stimulusJson,
    explanation,
    marks,
    negativeMarks,
    source,
  }), [questionType, prompt, topic, difficulty, optionsJson, correctJson, stimulusJson, explanation, marks, negativeMarks, source]);

  const save = async (addAnother: boolean) => {
    if (!parsed.draft) return;
    setSaving(true);
    setMessage(null);
    try {
      const saved = question
        ? await updateQuestion(question.id, parsed.draft)
        : await createQuestion(parsed.draft);
      await queryClient.invalidateQueries({ queryKey: ["authoring-questions"] });
      onSaved(saved, addAnother);
      if (addAnother && !question) {
        setPrompt("");
        setOptionsJson(JSON.stringify(emptyDraft.options, null, 2));
        setCorrectJson(JSON.stringify(emptyDraft.correct_answer, null, 2));
        setStimulusJson("");
        setExplanation("");
        setSource("");
        setMessage("Saved as draft. Topic, difficulty, and marks were kept for the next question.");
      } else {
        onClose();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The question could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const previewOptions = parsed.draft?.options ?? [];
  return (
    <div className="authoring-modal-backdrop" role="presentation">
      <section className="authoring-editor" role="dialog" aria-modal="true" aria-labelledby="question-editor-title">
        <div className="authoring-editor-header">
          <div><span className="section-kicker">QUESTION AUTHORING</span><h2 id="question-editor-title">{question ? `Edit question v${question.version_number}` : "Create question"}</h2></div>
          <button className="icon-button" aria-label="Close editor" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="authoring-editor-grid">
          <form className="authoring-form" onSubmit={(event) => { event.preventDefault(); void save(false); }}>
            <label>Question type
              <select value={questionType} onChange={(event) => {
                const next = event.target.value as AuthoringQuestionDraft["question_type"];
                setQuestionType(next);
                setOptionsJson(next === "numeric" ? "[]" : JSON.stringify(emptyDraft.options, null, 2));
                setCorrectJson(next === "multi_choice"
                  ? JSON.stringify({ option_ids: ["option-a"] }, null, 2)
                  : next === "numeric"
                    ? JSON.stringify({ value: 0, tolerance: 0 }, null, 2)
                    : JSON.stringify(emptyDraft.correct_answer, null, 2));
              }}>
                <option value="single_choice">Single-choice MCQ</option>
                <option value="multi_choice">Multiple-select MCQ</option>
                <option value="numeric">Numeric answer</option>
              </select>
            </label>
            <label>Question text<textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} maxLength={20_000} /></label>
            <div className="authoring-two-fields">
              <label>Topic<input value={topic} onChange={(event) => setTopic(event.target.value)} maxLength={150} /></label>
              <label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value as QuestionDifficulty)}><option>easy</option><option>medium</option><option>hard</option></select></label>
            </div>
            {questionType !== "numeric" && <label>Options JSON<textarea value={optionsJson} onChange={(event) => setOptionsJson(event.target.value)} rows={5} spellCheck={false} /></label>}
            <label>Correct answer JSON<textarea value={correctJson} onChange={(event) => setCorrectJson(event.target.value)} rows={3} spellCheck={false} /></label>
            <label>Stimulus JSON (optional)<textarea value={stimulusJson} onChange={(event) => setStimulusJson(event.target.value)} rows={4} placeholder={'{"kind":"passage","title":"Read this first","content":"..."}'} spellCheck={false} /></label>
            <label>Verified explanation<textarea value={explanation} onChange={(event) => setExplanation(event.target.value)} rows={3} maxLength={20_000} /></label>
            <div className="authoring-two-fields">
              <label>Marks<input type="number" min="0" step="0.25" value={marks} onChange={(event) => setMarks(event.target.value)} /></label>
              <label>Negative marks<input type="number" min="0" step="0.25" value={negativeMarks} onChange={(event) => setNegativeMarks(event.target.value)} /></label>
            </div>
            <label>Source / verification reference<input value={source} onChange={(event) => setSource(event.target.value)} maxLength={2_000} /></label>
            {parsed.errors.length > 0 && <ul className="authoring-validation-errors" aria-live="polite">{parsed.errors.map((error) => <li key={error}>{error}</li>)}</ul>}
            {message && <p className="authoring-status" role="status">{message}</p>}
            <div className="authoring-form-actions">
              <button type="button" className="button button-outline" onClick={onClose}>Cancel</button>
              {!question && <button type="button" className="button button-outline" disabled={!parsed.draft || saving} onClick={() => void save(true)}>Save &amp; add another</button>}
              <button type="submit" className="button button-primary" disabled={!parsed.draft || saving}>{saving ? "Saving…" : "Save as draft"}</button>
            </div>
          </form>
          <aside className="candidate-preview">
            <span className="section-kicker">CANDIDATE PREVIEW</span>
            <h3>{prompt || "Your question will appear here"}</h3>
            <StimulusBlock stimulus={parsed.draft?.stimulus ?? null} />
            {previewOptions.map((option, index) => <div className="candidate-preview-option" key={option.id}><span>{String.fromCharCode(65 + index)}</span>{option.text || "Option text"}</div>)}
            {questionType === "numeric" && <div className="candidate-preview-option">Numeric response input</div>}
            {parsed.errors.length > 0 && <p>Fix validation issues to save this draft.</p>}
          </aside>
        </div>
      </section>
    </div>
  );
}

function ImportModal({ onClose }: { onClose: () => void }) {
  const [source, setSource] = useState("");
  const [contentType, setContentType] = useState<"application/json" | "text/csv">("application/json");
  const [result, setResult] = useState<Awaited<ReturnType<typeof importQuestions>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const run = async (dryRun: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const response = await importQuestions(source, contentType, dryRun);
      setResult(response);
      if (!dryRun) await queryClient.invalidateQueries({ queryKey: ["authoring-questions"] });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The import could not be processed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="authoring-modal-backdrop" role="presentation">
      <section className="authoring-dialog" role="dialog" aria-modal="true" aria-labelledby="bulk-import-title">
        <div className="authoring-editor-header"><div><span className="section-kicker">QUESTION BANK</span><h2 id="bulk-import-title">Bulk import</h2></div><button className="icon-button" aria-label="Close import dialog" onClick={onClose}><X size={18} /></button></div>
        <label className="import-file-input"><FileUp size={17} /> Choose CSV or JSON file
          <input type="file" accept=".csv,.json,text/csv,application/json" onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setContentType(file.name.toLowerCase().endsWith(".csv") ? "text/csv" : "application/json");
            setSource(await file.text());
            setResult(null);
          }} />
        </label>
        <label>Or paste import content
          <textarea value={source} onChange={(event) => { setSource(event.target.value); setResult(null); }} rows={11} spellCheck={false} />
        </label>
        <p className="authoring-help">Each imported question is created as a draft. JSON accepts an array or a <code>{"{ questions: [...] }"}</code> object; CSV options and correct_answer cells must contain JSON.</p>
        {error && <p className="assessment-inline-error" role="alert">{error}</p>}
        {result && <div className="import-result" role="status"><strong>{result.valid_count} valid</strong><span>{result.errors.length} row errors</span>{result.imported_count > 0 && <span>{result.imported_count} drafts imported</span>}
          {result.errors.map((item, index) => <p key={`${item.row_index}-${item.field}-${index}`}>Row {item.row_index} · {item.field}: {item.message}</p>)}
        </div>}
        <div className="authoring-form-actions">
          <button className="button button-outline" onClick={onClose}>Close</button>
          <button className="button button-outline" disabled={!source.trim() || busy} onClick={() => void run(true)}>{busy ? "Validating…" : "Validate import"}</button>
          <button className="button button-primary" disabled={!source.trim() || busy || !result?.valid_count} onClick={() => void run(false)}>Import valid rows</button>
        </div>
      </section>
    </div>
  );
}

export function QuestionBankTab() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState<QuestionDifficulty | "">("");
  const [status, setStatus] = useState<QuestionStatus | "">("");
  const [verified, setVerified] = useState<"" | "verified" | "unverified">("");
  const [editing, setEditing] = useState<AuthoringQuestion | null | undefined>(undefined);
  const [preview, setPreview] = useState<AuthoringQuestion | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmArchive, setConfirmArchive] = useState<AuthoringQuestion | null>(null);
  const [busyQuestionId, setBusyQuestionId] = useState<string | null>(null);
  const questionsQuery = useQuery({
    queryKey: ["authoring-questions", search, topic, difficulty, status, verified],
    queryFn: () => listAuthoringQuestions({
      search,
      topic,
      difficulty,
      status,
      verified: verified === "" ? null : verified === "verified",
      pageSize: 100,
    }),
  });
  const topics = [...new Set((questionsQuery.data?.items ?? []).map((question) => question.topic))].sort();

  const executeQuestionAction = async (question: AuthoringQuestion, action: "publish" | "archive") => {
    setBusyQuestionId(question.id);
    setError(null);
    try {
      if (action === "publish") await verifyPublishQuestion(question.id);
      else await archiveQuestion(question.id);
      await queryClient.invalidateQueries({ queryKey: ["authoring-questions"] });
      if (preview?.id === question.id) setPreview(null);
      setConfirmArchive(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The question could not be updated.");
    } finally {
      setBusyQuestionId(null);
    }
  };

  return (
    <section className="authoring-workspace">
      <div className="authoring-toolbar">
        <div><h2>Question bank</h2><p>Questions remain drafts until their answers and explanations are reviewed.</p></div>
        <div><button className="button button-outline" onClick={() => setImportOpen(true)}><FileUp size={15} /> Bulk import</button><button className="button button-primary" onClick={() => setEditing(null)}><CirclePlus size={15} /> New question</button></div>
      </div>
      <div className="authoring-filters">
        <label className="authoring-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search question text or topic" /></label>
        <label><span className="sr-only">Filter topic</span><select value={topic} onChange={(event) => setTopic(event.target.value)}><option value="">All topics</option>{topics.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label><span className="sr-only">Filter difficulty</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value as QuestionDifficulty | "")}><option value="">All difficulty</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></label>
        <label><span className="sr-only">Filter status</span><select value={status} onChange={(event) => setStatus(event.target.value as QuestionStatus | "")}><option value="">All statuses</option><option value="draft">Draft</option><option value="review">Review</option><option value="published">Published</option><option value="archived">Archived</option></select></label>
        <label><span className="sr-only">Filter verification</span><select value={verified} onChange={(event) => setVerified(event.target.value as typeof verified)}><option value="">Verified or unverified</option><option value="verified">Verified</option><option value="unverified">Unverified</option></select></label>
      </div>
      {error && <p className="assessment-inline-error" role="alert">{error}</p>}
      {questionsQuery.isLoading && <div className="panel assessment-state" role="status">Loading question bank…</div>}
      {questionsQuery.isError && <div className="panel assessment-state error-state" role="alert"><strong>Question bank unavailable</strong><span>{questionsQuery.error.message}</span><button className="button button-outline" onClick={() => void questionsQuery.refetch()}>Try again</button></div>}
      {questionsQuery.data && (
        <div className="question-bank-layout">
          <div className="question-bank-list">
            <div className="question-bank-count">{questionsQuery.data.total} questions</div>
            {questionsQuery.data.items.length === 0 && <div className="panel empty-assessments"><h3>No matching questions</h3><p>Create a question or change your filters.</p></div>}
            {questionsQuery.data.items.map((question) => (
              <article className={`question-bank-row ${preview?.id === question.id ? "selected" : ""}`} key={question.id}>
                <button className="question-row-main" onClick={() => setPreview(preview?.id === question.id ? null : question)}>
                  <span><strong>{question.topic}</strong><span>{question.prompt}</span><small>{question.question_type.replace("_", " ")} · {question.difficulty} · v{question.version_number}</small></span>
                  <span className={`authoring-status-badge ${question.status}`}>{question.status}</span>
                </button>
                <div className="question-row-actions">
                  <span>{question.verified_at ? "Verified" : "Unverified"} · {question.usage_count} active pools</span>
                  <button aria-label={`Edit ${question.prompt}`} onClick={() => setEditing(question)} disabled={question.status === "archived"}><Pencil size={14} /></button>
                  {question.status !== "published" && question.status !== "archived" && <button aria-label={`Verify and publish ${question.prompt}`} onClick={() => void executeQuestionAction(question, "publish")} disabled={busyQuestionId === question.id}><Check size={15} /></button>}
                  {question.status !== "archived" && <button aria-label={`Archive ${question.prompt}`} onClick={() => setConfirmArchive(question)}><Archive size={14} /></button>}
                </div>
              </article>
            ))}
          </div>
          <aside className="question-preview-panel">
            {preview ? (
              <>
                <div className="authoring-editor-header"><div><span className="section-kicker">QUESTION PREVIEW</span><h3>{preview.topic}</h3></div><button className="icon-button" aria-label="Close question preview" onClick={() => setPreview(null)}><X size={16} /></button></div>
                <p>{preview.prompt}</p>
                <StimulusBlock stimulus={preview.stimulus} />
                {preview.options.map((option, index) => <div className="candidate-preview-option" key={option.id}><span>{String.fromCharCode(65 + index)}</span>{option.text}</div>)}
                <div className="answer-review-explanation">{preview.explanation}</div>
                <p className="authoring-help">Answer key: {JSON.stringify(preview.correct_answer)}</p>
              </>
            ) : <div className="empty-preview"><BookOpenCheck size={22} /><strong>Select a question</strong><span>Preview content and review its version, answer, and explanation.</span></div>}
          </aside>
        </div>
      )}
      {editing !== undefined && <QuestionEditor question={editing ?? undefined} onClose={() => setEditing(undefined)} onSaved={(saved, keepOpen) => {
        setPreview(saved);
        if (!keepOpen) setEditing(undefined);
      }} />}
      {importOpen && <ImportModal onClose={() => setImportOpen(false)} />}
      {confirmArchive && (
        <div className="authoring-modal-backdrop" role="presentation">
          <section className="authoring-dialog" role="alertdialog" aria-modal="true" aria-labelledby="archive-question-title">
            <h2 id="archive-question-title">Archive this question?</h2>
            <p>This soft-archives the question and keeps historical attempts intact. It is currently referenced by {confirmArchive.usage_count} active assessment pool(s).</p>
            <div className="authoring-form-actions">
              <button className="button button-outline" onClick={() => setConfirmArchive(null)}>Cancel</button>
              <button className="button button-primary" disabled={busyQuestionId === confirmArchive.id} onClick={() => void executeQuestionAction(confirmArchive, "archive")}>Archive question</button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
