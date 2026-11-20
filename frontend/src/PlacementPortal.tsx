import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Archive,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  Building2,
  Check,
  CircleHelp,
  Clock3,
  FileQuestion,
  FlaskConical,
  GraduationCap,
  LogOut,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import {
  clearPlacementToken,
  getPlacementToken,
  placementJson,
  placementRequest,
  setPlacementToken,
  type AttemptQuestion,
  type AttemptResult,
  type PlacementAssignment,
  type PlacementAttempt,
  type PlacementQuestion,
  type PlacementTest,
  type PlacementUser,
  type PracticeQuestion,
} from "./services/placementApi";
import "./placement.css";

type Tab = "questions" | "studio" | "tests" | "assignments" | "analytics" | "people";
const ACTIVE_PLACEMENT_ATTEMPT = "mentormuni:placement-active-attempt:v1";

export function PlacementLoginForm({ onLogin }: { onLogin: (user: PlacementUser, token: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await placementRequest<{ access_token: string; user: PlacementUser }>(
        "/login",
        placementJson("POST", { email: email.trim(), password }),
      );
      setPlacementToken(result.access_token);
      onLogin(result.user, result.access_token);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="placement-login" onSubmit={submit}>
      <div className="placement-brand-mark"><GraduationCap size={23} /></div>
      <p className="placement-eyebrow">MENTORMUNI PLACEMENT TESTS</p>
      <h1>Welcome to your test workspace</h1>
      <p className="placement-muted">Sign in with the account provided by your college or platform administrator.</p>
      <label>Email address<input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      {error && <p className="placement-error" role="alert">{error}</p>}
      <button className="placement-button primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"} <ArrowRight size={16} /></button>
    </form>
  );
}

export function PlacementPortal() {
  const [user, setUser] = useState<PlacementUser | null>(null);
  const [loading, setLoading] = useState(Boolean(getPlacementToken()));
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("questions");
  const [activeAttempt, setActiveAttempt] = useState<PlacementAttempt | null>(null);
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null);
  const [resumeAttemptId, setResumeAttemptId] = useState(() => sessionStorage.getItem(ACTIVE_PLACEMENT_ATTEMPT));
  const [colleges, setColleges] = useState<Array<{ id: string; name: string; slug: string }>>([]);
  const [collegeContext, setCollegeContext] = useState<string | null>(null);

  useEffect(() => {
    if (!getPlacementToken()) {
      setLoading(false);
      return;
    }
    let active = true;
    placementRequest<PlacementUser>("/me")
      .then((me) => { if (active) setUser(me); })
      .catch((requestError: unknown) => {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : "Session could not be restored.");
          clearPlacementToken();
        }
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!user || user.role !== "platform_admin") {
      setCollegeContext(user?.college_id ?? null);
      return;
    }
    let active = true;
    placementRequest<Array<{ id: string; name: string; slug: string }>>("/colleges")
      .then((items) => {
        if (!active) return;
        setColleges(items);
        setCollegeContext((current) => current ?? items[0]?.id ?? null);
      })
      .catch((requestError: unknown) => {
        if (active) setError(requestError instanceof Error ? requestError.message : "Could not load colleges.");
      });
    return () => { active = false; };
  }, [user]);
  useEffect(() => {
    if (user?.role !== "student") return;
    const savedAttemptId = sessionStorage.getItem(ACTIVE_PLACEMENT_ATTEMPT);
    if (!savedAttemptId) return;
    let active = true;
    placementRequest<PlacementAttempt>(`/attempts/${savedAttemptId}`)
      .then(async (attempt) => {
        if (!active) return;
        setActiveAttempt(attempt);
        if (attempt.status !== "in_progress") {
          const submittedResult = await placementRequest<AttemptResult>(`/attempts/${savedAttemptId}/review`);
          if (active) setAttemptResult(submittedResult);
        }
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        sessionStorage.removeItem(ACTIVE_PLACEMENT_ATTEMPT);
        setResumeAttemptId(null);
        setError(requestError instanceof Error ? requestError.message : "The saved attempt could not be restored.");
      });
    return () => { active = false; };
  }, [user]);

  function signOut() {
    clearPlacementToken();
    sessionStorage.removeItem(ACTIVE_PLACEMENT_ATTEMPT);
    setUser(null);
    setActiveAttempt(null);
    setAttemptResult(null);
    setResumeAttemptId(null);
  }

  if (loading) return <div className="placement-shell"><div className="placement-loading">Restoring your secure session…</div></div>;
  if (!user) {
    return <main className="placement-login-page">
      {error && <div className="placement-error placement-session-error" role="alert">{error}</div>}
      <PlacementLoginForm onLogin={(signedInUser) => { setError(""); setUser(signedInUser); }} />
    </main>;
  }
  if (activeAttempt) {
    return <div className="placement-shell"><PlacementRunner attempt={activeAttempt} onAttemptChange={setActiveAttempt} onResult={setAttemptResult} onExit={() => {
      if (attemptResult) {
        sessionStorage.removeItem(ACTIVE_PLACEMENT_ATTEMPT);
        setResumeAttemptId(null);
      }
      setActiveAttempt(null);
      setAttemptResult(null);
    }} result={attemptResult} /></div>;
  }
  if (user.role === "student") {
    return     <div className="placement-shell"><PlacementHeader user={user} onSignOut={signOut} colleges={colleges} collegeId={collegeContext} onCollegeChange={setCollegeContext} />
      <StudentHome resumeAttemptId={resumeAttemptId} onResume={() => {
        if (!resumeAttemptId) return;
        void placementRequest<PlacementAttempt>(`/attempts/${resumeAttemptId}`).then((attempt) => {
          setActiveAttempt(attempt);
          if (attempt.status !== "in_progress") {
            return placementRequest<AttemptResult>(`/attempts/${resumeAttemptId}/review`).then(setAttemptResult);
          }
          return undefined;
        }).catch((requestError: unknown) => setError(requestError instanceof Error ? requestError.message : "Could not resume attempt."));
      }} onStart={(attempt) => {
        sessionStorage.setItem(ACTIVE_PLACEMENT_ATTEMPT, attempt.id);
        setResumeAttemptId(attempt.id);
        setActiveAttempt(attempt);
      }} />
    </div>;
  }

  const nav: Array<{ id: Tab; label: string; icon: typeof FileQuestion }> = [
    { id: "questions", label: "Question bank", icon: FileQuestion },
    { id: "studio", label: "AI & imports", icon: Sparkles },
    { id: "tests", label: "Test studio", icon: BookOpenCheck },
    { id: "assignments", label: "Assignments", icon: Send },
    { id: "analytics", label: "Cohort analytics", icon: Activity },
    { id: "people", label: "People & cohorts", icon: Users },
  ];
  return <div className="placement-shell">
    <PlacementHeader user={user} onSignOut={signOut} colleges={colleges} collegeId={collegeContext} onCollegeChange={setCollegeContext} />
    <div className="placement-layout">
      <aside className="placement-nav" aria-label="Placement administration">
        <p>ADMIN WORKSPACE</p>
        {nav.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? "selected" : ""} onClick={() => setTab(id)}><Icon size={17} />{label}</button>)}
        <div className="placement-nav-note"><ShieldCheck size={16} /> College data stays tenant-scoped.</div>
      </aside>
      <main className="placement-main">
        {tab === "questions" && <QuestionBank user={user} collegeId={collegeContext} />}
        {tab === "studio" && <GenerationStudio collegeId={collegeContext} />}
        {tab === "tests" && <TestStudio collegeId={collegeContext} />}
        {tab === "assignments" && <AssignmentStudio collegeId={collegeContext} />}
        {tab === "analytics" && <CohortAnalytics collegeId={collegeContext} />}
        {tab === "people" && <PeopleStudio user={user} collegeId={collegeContext} onCollegeCreated={(college) => { setColleges((previous) => [...previous, college]); setCollegeContext(college.id); }} />}
      </main>
    </div>
  </div>;
}

function PlacementHeader({ user, onSignOut, colleges, collegeId, onCollegeChange }: {
  user: PlacementUser;
  onSignOut: () => void;
  colleges: Array<{ id: string; name: string; slug: string }>;
  collegeId: string | null;
  onCollegeChange: (id: string) => void;
}) {
  return <header className="placement-header">
    <a className="placement-logo" href="/placement"><span><GraduationCap size={20} /></span><strong>MentorMuni <small>PLACEMENT TESTS</small></strong></a>
    <div className="placement-user">{user.role === "platform_admin" && <label className="placement-context">College context<select aria-label="College context" value={collegeId ?? ""} onChange={(event) => onCollegeChange(event.target.value)}><option value="">Select a college</option>{colleges.map((college) => <option key={college.id} value={college.id}>{college.name}</option>)}</select></label>}<span>{user.display_name}<small>{user.role.replace("_", " ")}{user.college_id ? " · college workspace" : " · platform"}</small></span><button aria-label="Sign out" onClick={onSignOut}><LogOut size={17} /> Sign out</button></div>
  </header>;
}

function PanelHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="placement-heading"><div><p>{eyebrow}</p><h1>{title}</h1><span>{description}</span></div>{action}</div>;
}

function StatusMessage({ error, info }: { error?: string; info?: string }) {
  if (!error && !info) return null;
  return <div className={error ? "placement-error" : "placement-notice"} role={error ? "alert" : "status"}>{error || info}</div>;
}

function useRemote<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = async () => {
    setLoading(true);
    try {
      setData(await placementRequest<T>(path));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load data.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void reload(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);
  return { data, error, loading, reload, setData };
}

function QuestionBank({ user, collegeId }: { user: PlacementUser; collegeId: string | null }) {
  const { data, error, loading, reload } = useRemote<{ items: PlacementQuestion[]; total: number }>("/questions");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState("");
  const [editing, setEditing] = useState<PlacementQuestion | null>(null);
  const filtered = (data?.items ?? []).filter((item) => `${item.topic_name} ${item.payload.stem} ${item.subtopic}`.toLowerCase().includes(query.toLowerCase()));
  useEffect(() => {
    if (editing) document.getElementById("question-editor")?.scrollIntoView({ behavior: "smooth" });
  }, [editing]);

  async function review(question: PlacementQuestion, action: "approve" | "discard") {
    setPending(question.id);
    setMessage("");
    try {
      await placementRequest("/ai/questions/review-action", placementJson("POST", { actions: [{ question_id: question.id, action }] }));
      setMessage(action === "approve" ? "Question approved and activated." : "Draft discarded.");
      await reload();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "Question action failed.");
    } finally {
      setPending("");
    }
  }
  async function archive(question: PlacementQuestion) {
    if (!window.confirm("Archive this question? Existing test and attempt history will be preserved.")) return;
    setPending(question.id);
    try {
      await placementRequest(`/questions/${question.id}/archive`, placementJson("POST", {}));
      setMessage("Question archived. Referenced history is preserved.");
      await reload();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "Could not archive this question.");
    } finally { setPending(""); }
  }
  async function clone(question: PlacementQuestion) {
    if (!collegeId) {
      setMessage("Select a college context before cloning a global question.");
      return;
    }
    setPending(question.id); setMessage("");
    try {
      await placementRequest(
        `/questions/${question.id}/clone-to-college?college_id=${encodeURIComponent(collegeId)}`,
        placementJson("POST", {}),
      );
      setMessage("Global question cloned to this college as a draft.");
      await reload();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "Could not clone the question.");
    } finally { setPending(""); }
  }

  return <>
    <PanelHeading eyebrow="AUTHORING" title="Question bank" description="Search and review tenant-visible questions. Question records are archived rather than deleted." action={<button className="placement-button primary" onClick={() => document.getElementById("question-editor")?.scrollIntoView({ behavior: "smooth" })}><Plus size={16} /> Add question</button>} />
    <StatusMessage error={error || (message && !/approved|archived|discarded|updated|saved|cloned/i.test(message) ? message : "")} info={message && /approved|archived|discarded|updated|saved|cloned/i.test(message) ? message : ""} />
    <section className="placement-card">
      <div className="placement-toolbar"><input aria-label="Search question bank" placeholder="Search stem, topic, or subtopic" value={query} onChange={(event) => setQuery(event.target.value)} /><span>{data?.total ?? 0} questions</span></div>
      {loading ? <p className="placement-muted">Loading questions…</p> : filtered.length ? <div className="placement-table-wrap"><table className="placement-table"><thead><tr><th>Question</th><th>Topic</th><th>Level</th><th>Source / status</th><th>Actions</th></tr></thead><tbody>
        {filtered.map((question) => {
          const readOnlyGlobal = question.scope === "global" && user.role !== "platform_admin";
          return <tr key={question.id}><td><strong>{question.payload.stem}</strong><small>{question.question_type.replaceAll("_", " ")}</small></td><td>{question.topic_name}<small>{question.subtopic || "—"}</small></td><td>{question.difficulty}</td><td><span className={`placement-pill ${question.status}`}>{question.status}</span><small>{question.source_type}</small></td><td className="placement-actions">
          {readOnlyGlobal && <button disabled={pending === question.id || !collegeId} onClick={() => void clone(question)}>Clone to college</button>}
          {!readOnlyGlobal && question.status !== "archived" && <button disabled={pending === question.id} onClick={() => setEditing(question)}>Edit</button>}
          {!readOnlyGlobal && question.status === "draft" && <><button disabled={pending === question.id} onClick={() => void review(question, "approve")}><Check size={14} /> Approve</button><button disabled={pending === question.id} onClick={() => void review(question, "discard")}><Archive size={14} /> Discard</button></>}
          {!readOnlyGlobal && question.status !== "archived" && <button disabled={pending === question.id} onClick={() => void archive(question)}><Archive size={14} /> Archive</button>}
        </td></tr>;
        })}
      </tbody></table></div> : <div className="placement-empty"><FileQuestion size={22} />No matching questions yet. Create one below or generate a draft in AI & imports.</div>}
    </section>
    <QuestionEditor key={editing?.id ?? "new-question"} collegeId={collegeId} initialQuestion={editing} onCancel={() => setEditing(null)} onCreated={async () => { setEditing(null); setMessage(editing ? "Question updated." : "Question saved as a draft."); await reload(); }} />
  </>;
}

export function QuestionEditor({ collegeId, initialQuestion = null, onCancel, onCreated }: {
  collegeId: string | null;
  initialQuestion?: PlacementQuestion | null;
  onCancel?: () => void;
  onCreated: () => Promise<void>;
}) {
  const [stem, setStem] = useState(initialQuestion?.payload.stem ?? "");
  const [topic, setTopic] = useState(initialQuestion?.topic_slug ?? "");
  const [subtopic, setSubtopic] = useState(initialQuestion?.subtopic ?? "");
  const [kind, setKind] = useState<PlacementQuestion["question_type"]>(initialQuestion?.question_type ?? "mcq_single");
  const [difficulty, setDifficulty] = useState<PlacementQuestion["difficulty"]>(initialQuestion?.difficulty ?? "medium");
  const [optionTexts, setOptionTexts] = useState(initialQuestion?.payload.options.map((option) => option.text) ?? ["", "", "", ""]);
  const [correct, setCorrect] = useState(initialQuestion ? Math.max(0, initialQuestion.payload.options.findIndex((option) => option.id === initialQuestion.payload.correct_option_id)) : 0);
  const [shortcut, setShortcut] = useState(initialQuestion?.payload.shortcut_solution ?? "");
  const [concept, setConcept] = useState(initialQuestion?.payload.concept_solution ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function reset() { setStem(""); setTopic(""); setSubtopic(""); setOptionTexts(["", "", "", ""]); setShortcut(""); setConcept(""); setCorrect(0); }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = optionTexts.map((item) => item.trim().toLocaleLowerCase());
    if (normalized.some((item) => !item) || new Set(normalized).size !== 4) {
      setError("Enter four non-empty, distinct answer options.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await placementRequest(initialQuestion ? `/questions/${initialQuestion.id}` : "/questions", placementJson(initialQuestion ? "PATCH" : "POST", {
        scope: initialQuestion?.scope ?? (collegeId ? "college" : "global"),
        college_id: initialQuestion?.college_id ?? collegeId,
        topic_slug: topic,
        subtopic,
        question_type: kind,
        source_type: initialQuestion?.source_type ?? "manual",
        payload: {
          stem: stem.trim(),
          options: optionTexts.map((text, index) => ({ id: `option_${index + 1}`, text: text.trim() })),
          correct_option_id: `option_${correct + 1}`,
          shortcut_solution: shortcut.trim(),
          concept_solution: concept.trim(),
          estimated_seconds: 60,
          difficulty,
          company_tags: [],
          stimulus: initialQuestion?.payload.stimulus ?? null,
          latex: initialQuestion?.payload.latex ?? null,
          code_language: initialQuestion?.payload.code_language ?? null,
        },
      }));
      if (!initialQuestion) reset();
      await onCreated();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save the question.");
    } finally { setBusy(false); }
  }
  return <section className="placement-card" id="question-editor">
    <div className="placement-card-heading"><div><span className="placement-eyebrow">MANUAL AUTHORING</span><h2>{initialQuestion ? "Edit question" : "Create a question"}</h2></div>{initialQuestion && onCancel && <button className="placement-text-button" onClick={onCancel}>Cancel edit</button>}</div>
    <div className="placement-editor-layout"><form className="placement-form" onKeyDown={(event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        event.currentTarget.requestSubmit();
      }
    }} onSubmit={(event) => void submit(event)}>
      <label className="span-two">Question stem<textarea required minLength={8} value={stem} onChange={(event) => setStem(event.target.value)} placeholder="Write the scenario and the question…" /></label>
      <label>Topic slug<input required value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="percentages" /></label>
      <label>Subtopic<input value={subtopic} onChange={(event) => setSubtopic(event.target.value)} /></label>
      <label>Question type<select value={kind} onChange={(event) => setKind(event.target.value as PlacementQuestion["question_type"])}><option value="mcq_single">Multiple choice</option><option value="data_interpretation">Data interpretation</option><option value="pseudocode">Pseudocode</option><option value="logical_reasoning">Logical reasoning</option><option value="verbal">Verbal</option></select></label>
      <label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value as PlacementQuestion["difficulty"])}><option>easy</option><option>medium</option><option>hard</option></select></label>
      <div className="placement-option-editor span-two"><span>Answer options (select the correct answer)</span>{optionTexts.map((value, index) => <label key={index}><input type="radio" name="correct-option" aria-label={`Set option ${index + 1} as correct`} checked={correct === index} onChange={() => setCorrect(index)} /><input required aria-label={`Option ${index + 1}`} placeholder={`Option ${index + 1}`} value={value} onChange={(event) => setOptionTexts((previous) => previous.map((item, current) => current === index ? event.target.value : item))} /></label>)}</div>
      <label>Shortcut solution<textarea required value={shortcut} onChange={(event) => setShortcut(event.target.value)} /></label>
      <label>Concept solution<textarea required value={concept} onChange={(event) => setConcept(event.target.value)} /></label>
      {error && <p className="placement-error span-two" role="alert">{error}</p>}
      <div className="span-two"><button className="placement-button primary" disabled={busy}>{busy ? "Saving…" : initialQuestion ? "Save changes" : "Save as draft"} <Check size={15} /></button></div>
    </form><aside className="placement-live-preview"><span>LIVE STUDENT PREVIEW</span><h3>{stem || "Your question stem will appear here"}</h3>{optionTexts.map((option, index) => <p key={index}><kbd>{index + 1}</kbd>{option || `Option ${index + 1}`}</p>)}</aside></div>
  </section>;
}

function GenerationStudio({ collegeId }: { collegeId: string | null }) {
  const [prompt, setPrompt] = useState("");
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [count, setCount] = useState(10);
  const [duration, setDuration] = useState(20);
  const [topics, setTopics] = useState("");
  const [importText, setImportText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [extractionErrors, setExtractionErrors] = useState<Array<{ row_number: number; message: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [generated, setGenerated] = useState<{ test: PlacementTest; questions: PlacementQuestion[] } | null>(null);
  const [replacing, setReplacing] = useState("");

  async function generate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await placementRequest<{ test: PlacementTest; questions: PlacementQuestion[] }>("/ai/generate-test", placementJson("POST", {
        prompt: prompt.trim(), target_difficulty: difficulty, question_count: count, duration_minutes: duration,
        college_id: collegeId, topic_slugs: topics.split(",").map((item) => item.trim()).filter(Boolean),
      }));
      setGenerated(result);
      setMessage(`Created "${result.test.title}" as a draft with ${result.questions.length} reviewable question(s).`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Generation failed.");
    } finally { setBusy(false); }
  }
  async function extract(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file && !importText.trim()) { setError("Paste question text or choose a supported file."); return; }
    setBusy(true); setError(""); setMessage(""); setExtractionErrors([]);
    try {
      let payload: BodyInit;
      if (file) {
        const formData = new FormData();
        formData.set("file", file);
        if (collegeId) formData.set("college_id", collegeId);
        payload = formData;
      } else {
        payload = JSON.stringify({ filename: "pasted-questions.txt", content: importText, college_id: collegeId });
      }
      const result = await placementRequest<{ questions: PlacementQuestion[]; errors: Array<{ row_number: number; message: string }> }>("/ai/extract-questions", { method: "POST", body: payload });
      setMessage(`Extracted ${result.questions.length} draft question(s). ${result.errors.length} row(s) need correction.`);
      setExtractionErrors(result.errors);
      setImportText(""); setFile(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Import failed.");
    } finally { setBusy(false); }
  }
  async function replaceSimilar(question: PlacementQuestion) {
    if (!generated) return;
    setReplacing(question.id); setError(""); setMessage("");
    try {
      const replacement = await placementRequest<PlacementQuestion>(
        `/ai/questions/${question.id}/replace-similar`,
        placementJson("POST", { test_id: generated.test.id, topic_slug: question.topic_slug, subtopic: question.subtopic }),
      );
      setGenerated((current) => current ? {
        ...current,
        questions: current.questions.map((item) => item.id === question.id ? replacement : item),
      } : current);
      setMessage("A similar draft question replaced the selected test item. Review it before publishing.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not replace the question.");
    } finally { setReplacing(""); }
  }
  return <>
    <PanelHeading eyebrow="AI-ASSISTED AUTHORING" title="AI & imports" description="Generate a draft test, or extract candidate questions for human review before activation." />
    <StatusMessage error={error} info={message} />
    <div className="placement-two-column">
      <section className="placement-card">
        <div className="placement-card-heading"><div><span className="placement-eyebrow"><Sparkles size={13} /> DRAFT GENERATION</span><h2>Prompt to test</h2></div></div>
        <form className="placement-form" onSubmit={(event) => void generate(event)}>
          <label className="span-two">Syllabus, role, or company-style intent<textarea required minLength={10} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Build a fresher SDE screening test covering arrays, numerical reasoning, and data interpretation…" /></label>
          <label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value as typeof difficulty)}><option>easy</option><option>medium</option><option>hard</option></select></label>
          <label>Questions<input type="number" min={1} max={100} value={count} onChange={(event) => setCount(Number(event.target.value))} /></label>
          <label>Duration (minutes)<input type="number" min={1} max={360} value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
          <label>Topic slugs<input value={topics} onChange={(event) => setTopics(event.target.value)} placeholder="percentages, arrays" /></label>
          <div className="span-two"><button className="placement-button primary" disabled={busy}>{busy ? "Generating draft…" : "Generate draft test"} <Sparkles size={15} /></button></div>
        </form>
        {generated && <div className="placement-generated"><strong>{generated.test.title}</strong><span>{generated.questions.length} questions · {generated.test.status}</span><p>Review generated drafts in Question bank before publishing.</p>{generated.questions.map((question) => <div className="placement-generated-question" key={question.id}><span>{question.topic_slug}: {question.payload.stem}</span><button className="placement-button small secondary" disabled={Boolean(replacing)} onClick={() => void replaceSimilar(question)}>{replacing === question.id ? "Replacing…" : "Replace with similar"}</button></div>)}</div>}
      </section>
      <section className="placement-card">
        <div className="placement-card-heading"><div><span className="placement-eyebrow"><FlaskConical size={13} /> EXTRACTION REVIEW QUEUE</span><h2>Import text or file</h2></div></div>
        <p className="placement-muted">Extracted questions are saved as drafts; verify answer keys and solutions before activating.</p>
        <form className="placement-form" onSubmit={(event) => void extract(event)}>
          <label className="span-two">Paste source text<textarea value={importText} onChange={(event) => setImportText(event.target.value)} placeholder={"Question: ...\nA) ...\nB) ...\nC) ...\nD) ...\nAnswer: A"} /></label>
          <label className="span-two">Or select PDF, DOCX, CSV, or TXT<input type="file" accept=".pdf,.docx,.csv,.txt" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
          <div className="span-two"><button className="placement-button secondary" disabled={busy}><Plus size={15} /> Extract drafts</button></div>
        </form>
        {extractionErrors.length > 0 && <div className="placement-import-errors" role="alert"><strong>Rows needing correction</strong><ul>{extractionErrors.map((item, index) => <li key={`${item.row_number}-${index}`}>Row {item.row_number}: {item.message}</li>)}</ul></div>}
      </section>
    </div>
  </>;
}

function TestStudio({ collegeId }: { collegeId: string | null }) {
  const { data: tests, error, loading, reload } = useRemote<PlacementTest[]>("/tests");
  const { data: bank, reload: reloadQuestions } = useRemote<{ items: PlacementQuestion[] }>("/questions");
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [duration, setDuration] = useState(30);
  const [negativeMarks, setNegativeMarks] = useState(0);
  const [passingCutoff, setPassingCutoff] = useState(0);
  const [editingId, setEditingId] = useState("");
  const [questionSections, setQuestionSections] = useState<Record<string, string>>({});
  const [errorAction, setErrorAction] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const questions = (bank?.items ?? []).filter((item) => item.status === "active");

  async function createTest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected.length) { setErrorAction("Select at least one active question before creating a test."); return; }
    setBusy(true); setErrorAction(""); setMessage("");
    try {
      const questionOrder = {
        questions: selected.map((question_id) => ({ question_id, section_name: questionSections[question_id] ?? "General" })),
      };
      if (editingId) {
        await placementRequest(`/tests/${editingId}`, placementJson("PATCH", {
          title: title.trim(), description: description.trim(), duration_minutes: duration,
          negative_marks: negativeMarks, passing_cutoff_percent: passingCutoff,
        }));
        await placementRequest(`/tests/${editingId}/questions`, placementJson("PUT", questionOrder));
        setMessage("Draft test and question order updated.");
      } else {
        await placementRequest("/tests", placementJson("POST", {
          title: title.trim(), description: description.trim(), scope: collegeId ? "college" : "global",
          college_id: collegeId, duration_minutes: duration, negative_marks: negativeMarks,
          passing_cutoff_percent: passingCutoff, question_ids: questionOrder.questions,
        }));
        setMessage("Draft test created. Publish it when the question set and timing are ready.");
      }
      setTitle(""); setDescription(""); setSelected([]); setQuestionSections({}); setEditingId("");
      await reload();
    } catch (requestError) { setErrorAction(requestError instanceof Error ? requestError.message : "Could not create test."); }
    finally { setBusy(false); }
  }
  async function editTest(test: PlacementTest) {
    setBusy(true); setErrorAction("");
    try {
      const order = await placementRequest<{ questions: Array<{ question_id: string; section_name: string }> }>(`/tests/${test.id}/questions`);
      setEditingId(test.id);
      setTitle(test.title);
      setDescription(test.description);
      setDuration(test.duration_minutes);
      setNegativeMarks(test.negative_marks);
      setPassingCutoff(test.passing_cutoff_percent);
      setSelected(order.questions.map((question) => question.question_id));
      setQuestionSections(Object.fromEntries(order.questions.map((question) => [question.question_id, question.section_name])));
    } catch (requestError) {
      setErrorAction(requestError instanceof Error ? requestError.message : "Could not load the test blueprint.");
    } finally { setBusy(false); }
  }
  function moveQuestion(index: number, offset: -1 | 1) {
    const target = index + offset;
    if (target < 0 || target >= selected.length) return;
    setSelected((previous) => {
      const next = [...previous];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }
  async function publish(test: PlacementTest) {
    setBusy(true); setErrorAction(""); setMessage("");
    try {
      await placementRequest(`/tests/${test.id}/publish`, placementJson("POST", {}));
      setMessage(`${test.title} is published.`);
      await reload();
    } catch (requestError) { setErrorAction(requestError instanceof Error ? requestError.message : "Could not publish test."); }
    finally { setBusy(false); }
  }
  async function archive(test: PlacementTest) {
    if (!window.confirm("Archive this test? Its assignments and attempt history are retained.")) return;
    try {
      await placementRequest(`/tests/${test.id}/archive`, placementJson("POST", {}));
      setMessage(`${test.title} archived.`);
      await reload();
    } catch (requestError) { setErrorAction(requestError instanceof Error ? requestError.message : "Could not archive test."); }
  }
  return <>
    <PanelHeading eyebrow="ASSESSMENT AUTHORING" title="Test studio" description="Assemble verified questions into a timed test. Publishing requires a ready question set." />
    <StatusMessage error={error || errorAction} info={message} />
    <div className="placement-two-column">
      <section className="placement-card">
        <div className="placement-card-heading"><div><span className="placement-eyebrow">BUILDER</span><h2>Create a test</h2></div></div>
        <form className="placement-form" onSubmit={(event) => void createTest(event)}>
          <label className="span-two">Title<input required value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <label className="span-two">Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
          <label>Duration (minutes)<input type="number" min={1} max={360} value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
          <label>Negative marks<input type="number" min={0} max={100} value={negativeMarks} onChange={(event) => setNegativeMarks(Number(event.target.value))} /></label>
          <label>Passing cutoff %<input type="number" min={0} max={100} value={passingCutoff} onChange={(event) => setPassingCutoff(Number(event.target.value))} /></label>
          <fieldset className="span-two placement-question-pick"><legend>Active questions ({selected.length} selected)</legend>
            {questions.map((question) => <label key={question.id}><input type="checkbox" checked={selected.includes(question.id)} onChange={(event) => {
              if (event.target.checked) {
                setSelected((previous) => [...previous, question.id]);
                setQuestionSections((previous) => ({ ...previous, [question.id]: previous[question.id] ?? "General" }));
              } else {
                setSelected((previous) => previous.filter((id) => id !== question.id));
                setQuestionSections((previous) => { const next = { ...previous }; delete next[question.id]; return next; });
              }
            }} /><span>{question.payload.stem}<small>{question.topic_slug} · {question.difficulty}</small></span></label>)}
            {!questions.length && <span className="placement-muted">Activate reviewed questions in Question bank first.</span>}
          </fieldset>
          {selected.length > 0 && <ol className="span-two placement-order-list">{selected.map((id, index) => <li key={id}><span>{index + 1}. {questions.find((question) => question.id === id)?.payload.stem ?? "Question"}</span><button type="button" disabled={index === 0} onClick={() => moveQuestion(index, -1)} aria-label={`Move question ${index + 1} up`}>↑</button><button type="button" disabled={index === selected.length - 1} onClick={() => moveQuestion(index, 1)} aria-label={`Move question ${index + 1} down`}>↓</button><button type="button" onClick={() => { setSelected((previous) => previous.filter((questionId) => questionId !== id)); setQuestionSections((previous) => { const next = { ...previous }; delete next[id]; return next; }); }}>Remove</button></li>)}</ol>}
          {errorAction && <p className="placement-error span-two" role="alert">{errorAction}</p>}
          <div className="span-two"><button className="placement-button primary" disabled={busy}>{busy ? "Saving…" : editingId ? "Save test changes" : "Save draft test"}</button></div>
        </form>
        <button className="placement-text-button" onClick={() => void reloadQuestions()}>Refresh question list</button>{editingId && <button className="placement-text-button" onClick={() => { setEditingId(""); setTitle(""); setDescription(""); setSelected([]); setQuestionSections({}); }}>Cancel edit</button>}
      </section>
      <section className="placement-card">
        <div className="placement-card-heading"><div><span className="placement-eyebrow">TEST CATALOG</span><h2>Readiness & publishing</h2></div></div>
        {loading ? <p className="placement-muted">Loading tests…</p> : tests?.length ? <div className="placement-test-list">{tests.map((test) => <article key={test.id}>
          <span className={`placement-pill ${test.status}`}>{test.status}</span><h3>{test.title}</h3><p>{test.description || "No description"} · {test.question_count} questions · {test.duration_minutes} min</p>
          <div className="placement-row-actions">{test.status === "draft" && <><button className="placement-button small secondary" disabled={busy} onClick={() => void editTest(test)}>Edit / reorder</button><button className="placement-button small primary" disabled={busy || test.question_count < 1} onClick={() => void publish(test)}><Check size={14} /> Publish</button></>}{test.status !== "archived" && <button className="placement-button small secondary" onClick={() => void archive(test)}><Archive size={14} /> Archive</button>}</div>
        </article>)}</div> : <p className="placement-empty">No tests yet. Generate a test in AI & imports or create one here.</p>}
      </section>
    </div>
  </>;
}

function AssignmentStudio({ collegeId }: { collegeId: string | null }) {
  const { data: tests, error: testError } = useRemote<PlacementTest[]>("/tests");
  const { data: assignments, error, loading, reload } = useRemote<PlacementAssignment[]>("/assignments");
  const { data: batches } = useRemote<Array<{ id: string; name: string; branch: string; graduation_year: number }>>("/batches");
  const publishedTests = (tests ?? []).filter((test) => test.status === "published");
  const [testId, setTestId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [branches, setBranches] = useState("");
  const [graduationYear, setGraduationYear] = useState("");
  const [startsAt, setStartsAt] = useState(() => new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 16));
  const [endsAt, setEndsAt] = useState("");
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [editingId, setEditingId] = useState("");
  const [message, setMessage] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [busy, setBusy] = useState(false);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!collegeId) { setSubmitError("Choose a college context before creating an assignment."); return; }
    if (endsAt && new Date(endsAt) <= new Date(startsAt)) { setSubmitError("The closing time must be after the opening time."); return; }
    setBusy(true); setSubmitError(""); setMessage("");
    try {
      const assignmentData = {
        batch_ids: batchId ? [batchId] : [],
        branches: branches.split(",").map((branch) => branch.trim()).filter(Boolean),
        graduation_year: graduationYear ? Number(graduationYear) : null,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        max_attempts: maxAttempts,
      };
      if (editingId) {
        await placementRequest(`/assignments/${editingId}`, placementJson("PATCH", assignmentData));
        setMessage("Assignment schedule updated.");
      } else {
        await placementRequest("/assignments", placementJson("POST", {
          ...assignmentData, test_id: testId, college_id: collegeId,
        }));
        setMessage("Assignment created and made available to the selected cohort.");
      }
      setEditingId("");
      await reload();
    } catch (requestError) { setSubmitError(requestError instanceof Error ? requestError.message : "Could not create assignment."); }
    finally { setBusy(false); }
  }
  function editAssignment(assignment: PlacementAssignment) {
    const asLocalDateTime = (value: string) => {
      const date = new Date(value);
      return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
    };
    setEditingId(assignment.id);
    setTestId(assignment.test_id);
    setBatchId(assignment.batch_ids[0] ?? "");
    setBranches(assignment.branches.join(", "));
    setGraduationYear(assignment.graduation_year ? String(assignment.graduation_year) : "");
    setStartsAt(asLocalDateTime(assignment.starts_at));
    setEndsAt(assignment.ends_at ? asLocalDateTime(assignment.ends_at) : "");
    setMaxAttempts(assignment.max_attempts);
    setSubmitError("");
  }
  async function archiveAssignment(assignment: PlacementAssignment) {
    if (!window.confirm("Archive this assignment? Existing attempts and their results are retained.")) return;
    try {
      await placementRequest(`/assignments/${assignment.id}/archive`, placementJson("POST", {}));
      setMessage("Assignment archived.");
      await reload();
    } catch (requestError) {
      setSubmitError(requestError instanceof Error ? requestError.message : "Could not archive assignment.");
    }
  }
  return <>
    <PanelHeading eyebrow="DELIVERY" title="Batch assignments" description="Schedule published tests for a college, batch, or branch with explicit attempt limits." />
    <StatusMessage error={error || testError || submitError} info={message} />
    <div className="placement-two-column">
      <section className="placement-card">
        <div className="placement-card-heading"><div><span className="placement-eyebrow">ONE-FLOW ASSIGNMENT</span><h2>{editingId ? "Edit assignment" : "Schedule a test"}</h2></div>{editingId && <button className="placement-text-button" onClick={() => setEditingId("")}>Cancel</button>}</div>
        <form className="placement-form" onSubmit={(event) => void create(event)}>
          <label className="span-two">Published test<select required disabled={Boolean(editingId)} value={testId} onChange={(event) => setTestId(event.target.value)}><option value="">Select a test</option>{publishedTests.map((test) => <option key={test.id} value={test.id}>{test.title}</option>)}</select></label>
          <label className="span-two">Target batch<select value={batchId} onChange={(event) => setBatchId(event.target.value)}><option value="">All college students</option>{(batches ?? []).map((batch) => <option key={batch.id} value={batch.id}>{batch.name} · {batch.branch} · {batch.graduation_year}</option>)}</select></label>
          <label>Branches (comma-separated)<input value={branches} onChange={(event) => setBranches(event.target.value)} placeholder="CSE, IT" /></label>
          <label>Graduation year (optional)<input type="number" min={2000} max={2200} value={graduationYear} onChange={(event) => setGraduationYear(event.target.value)} /></label>
          <label>Opens at<input type="datetime-local" required value={startsAt} onChange={(event) => setStartsAt(event.target.value)} /></label>
          <label>Closes at (optional)<input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} /></label>
          <label>Maximum attempts<input type="number" min={1} max={100} value={maxAttempts} onChange={(event) => setMaxAttempts(Number(event.target.value))} /></label>
          <div className="span-two"><button className="placement-button primary" disabled={busy || (!editingId && !publishedTests.length)}>{busy ? "Scheduling…" : editingId ? "Save changes" : "Create assignment"} <Send size={14} /></button></div>
        </form>
      </section>
      <section className="placement-card">
        <div className="placement-card-heading"><div><span className="placement-eyebrow">SCHEDULE</span><h2>Active assignments</h2></div></div>
        {loading ? <p className="placement-muted">Loading assignments…</p> : assignments?.length ? <div className="placement-test-list">{assignments.map((item) => <article key={item.id}><span className={`placement-pill ${item.status}`}>{item.status}</span><h3>{item.test_title}</h3><p>{new Date(item.starts_at).toLocaleString()} {item.ends_at ? `– ${new Date(item.ends_at).toLocaleString()}` : "· No closing time"}</p><small>{item.max_attempts} max attempts · {item.batch_ids.length ? "Batch restricted" : "All batches"}</small>{item.status === "active" && <div className="placement-row-actions"><button className="placement-button small secondary" onClick={() => editAssignment(item)}>Edit schedule</button><button className="placement-button small secondary" onClick={() => void archiveAssignment(item)}>Archive</button></div>}</article>)}</div> : <p className="placement-empty">No assignments scheduled.</p>}
      </section>
    </div>
  </>;
}

function CohortAnalytics({ collegeId }: { collegeId: string | null }) {
  const path = `/analytics/college${collegeId ? `?college_id=${encodeURIComponent(collegeId)}` : ""}`;
  const { data, error, loading, reload } = useRemote<Record<string, unknown>>(path);
  if (loading) return <p className="placement-muted">Loading cohort analytics…</p>;
  const topics = Array.isArray(data?.topic_breakdown) ? data.topic_breakdown as Array<Record<string, unknown>> : [];
  const cohorts = Array.isArray(data?.cohort_breakdown) ? data.cohort_breakdown as Array<Record<string, unknown>> : [];
  return <>
    <PanelHeading eyebrow="READINESS INSIGHTS" title="Cohort analytics" description="Aggregate scores and topic readiness for your permitted college scope." action={<button className="placement-button secondary" onClick={() => void reload()}>Refresh</button>} />
    <StatusMessage error={error} />
    <div className="placement-metric-grid"><Metric label="Completed attempts" value={String(data?.attempts_completed ?? 0)} /><Metric label="Average score" value={`${Number(data?.average_score_percent ?? 0)}%`} /><Metric label="Topics measured" value={String(topics.length)} /></div>
    <section className="placement-card"><div className="placement-card-heading"><div><span className="placement-eyebrow">TOPIC READINESS</span><h2>Accuracy and time by topic</h2></div></div>
      {topics.length ? <div className="placement-table-wrap"><table className="placement-table"><thead><tr><th>Topic</th><th>Correct</th><th>Incorrect</th><th>Unanswered</th><th>Accuracy</th><th>Avg seconds</th></tr></thead><tbody>{topics.map((item, index) => <tr key={`${String(item.topic_slug)}-${index}`}><td>{String(item.topic_slug)}</td><td>{String(item.correct)}</td><td>{String(item.incorrect)}</td><td>{String(item.unanswered)}</td><td>{String(item.accuracy_percent)}%</td><td>{String(item.avg_time_seconds)}s</td></tr>)}</tbody></table></div> : <p className="placement-empty">No submitted test attempts are available for this cohort yet.</p>}
    </section>
    <section className="placement-card"><div className="placement-card-heading"><div><span className="placement-eyebrow">COHORT SNAPSHOT</span><h2>Batch overview</h2></div></div>
      {cohorts.length ? <div className="placement-table-wrap"><table className="placement-table"><thead><tr><th>Cohort</th><th>Completed attempts</th><th>Average score</th></tr></thead><tbody>{cohorts.map((item, index) => <tr key={`${String(item.cohort)}-${index}`}><td>{String(item.cohort)}</td><td>{String(item.attempts_completed)}</td><td>{String(item.average_score_percent)}%</td></tr>)}</tbody></table></div> : <p className="placement-empty">Cohort breakdown will appear after students submit assignments.</p>}
    </section>
  </>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <article className="placement-metric"><span>{label}</span><strong>{value}</strong></article>;
}

function PeopleStudio({ user, collegeId, onCollegeCreated }: {
  user: PlacementUser;
  collegeId: string | null;
  onCollegeCreated: (college: { id: string; name: string; slug: string }) => void;
}) {
  const { data: batches, error: batchesError, loading, reload } = useRemote<Array<{ id: string; name: string; branch: string; graduation_year: number; section: string }>>("/batches");
  const [collegeName, setCollegeName] = useState("");
  const [collegeSlug, setCollegeSlug] = useState("");
  const [batchName, setBatchName] = useState("");
  const [branch, setBranch] = useState("");
  const [year, setYear] = useState(new Date().getFullYear() + 1);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [batchId, setBatchId] = useState("");
  const [role, setRole] = useState<"college_admin" | "student">("student");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function createCollege(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const result = await placementRequest<{ id: string; name: string; slug: string }>("/colleges", placementJson("POST", { slug: collegeSlug, name: collegeName }));
      onCollegeCreated(result); setCollegeName(""); setCollegeSlug(""); setMessage(`College ${result.name} created and selected as the workspace context.`);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not create college."); }
    finally { setBusy(false); }
  }
  async function createBatch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      await placementRequest("/batches", placementJson("POST", { name: batchName, branch, graduation_year: year, section: "", college_id: collegeId }));
      setBatchName(""); setBranch(""); setMessage("Batch created."); await reload();
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not create batch."); }
    finally { setBusy(false); }
  }
  async function createUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      await placementRequest("/users", placementJson("POST", { email, password, display_name: email.split("@")[0], role, college_id: collegeId, batch_id: role === "student" ? batchId : null }));
      setEmail(""); setPassword(""); setMessage("User account created.");
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not create account."); }
    finally { setBusy(false); }
  }
  return <>
    <PanelHeading eyebrow="ORGANIZATION" title="People & cohorts" description="Manage college cohorts and provision placement-workspace accounts." />
    <StatusMessage error={error || batchesError} info={message} />
    {user.role === "platform_admin" && <section className="placement-card"><div className="placement-card-heading"><div><span className="placement-eyebrow"><Building2 size={13} /> TENANTS</span><h2>Add a college</h2></div></div><form className="placement-inline-form" onSubmit={(event) => void createCollege(event)}><input required aria-label="College name" placeholder="College name" value={collegeName} onChange={(event) => setCollegeName(event.target.value)} /><input required aria-label="College slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" placeholder="college-slug" value={collegeSlug} onChange={(event) => setCollegeSlug(event.target.value)} /><button className="placement-button primary" disabled={busy}>Add college</button></form></section>}
    <div className="placement-two-column">
      <section className="placement-card"><div className="placement-card-heading"><div><span className="placement-eyebrow">COHORTS</span><h2>Create a batch</h2></div></div>
        <form className="placement-form" onSubmit={(event) => void createBatch(event)}><label>Batch name<input required value={batchName} onChange={(event) => setBatchName(event.target.value)} /></label><label>Branch<input required value={branch} onChange={(event) => setBranch(event.target.value)} placeholder="CSE" /></label><label>Graduation year<input type="number" min={2000} max={2200} value={year} onChange={(event) => setYear(Number(event.target.value))} /></label><div><button className="placement-button primary" disabled={busy || (user.role === "platform_admin" && !collegeId)}>Add batch <Plus size={14} /></button></div></form>
        {loading ? <p className="placement-muted">Loading cohorts…</p> : <div className="placement-test-list">{(batches ?? []).map((batch) => <article key={batch.id}><h3>{batch.name}</h3><p>{batch.branch} · {batch.graduation_year}{batch.section ? ` · ${batch.section}` : ""}</p></article>)}</div>}
      </section>
      <section className="placement-card"><div className="placement-card-heading"><div><span className="placement-eyebrow"><Users size={13} /> ACCESS</span><h2>Provision account</h2></div></div>
        <form className="placement-form" onSubmit={(event) => void createUser(event)}><label className="span-two">Email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label><label>Temporary password<input type="password" required minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} /></label><label>Role<select value={role} onChange={(event) => setRole(event.target.value as typeof role)}><option value="student">Student</option><option value="college_admin">College admin</option></select></label>{role === "student" && <label className="span-two">Assigned batch<select required value={batchId} onChange={(event) => setBatchId(event.target.value)}><option value="">Select a batch</option>{(batches ?? []).map((batch) => <option key={batch.id} value={batch.id}>{batch.name} · {batch.branch} · {batch.graduation_year}</option>)}</select></label>}<div className="span-two"><button className="placement-button secondary" disabled={busy || !collegeId}>Create account <Plus size={14} /></button></div></form>
      </section>
    </div>
  </>;
}

function StudentHome({ resumeAttemptId, onResume, onStart }: {
  resumeAttemptId: string | null;
  onResume: () => void;
  onStart: (attempt: PlacementAttempt) => void;
}) {
  const { data: assignments, error, loading, reload } = useRemote<PlacementAssignment[]>("/student/assignments");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  async function start(assignment: PlacementAssignment) {
    setBusy(assignment.id); setMessage("");
    try {
      const attempt = await placementRequest<PlacementAttempt>("/attempts/start", placementJson("POST", { assignment_id: assignment.id }));
      onStart(attempt);
    } catch (requestError) { setMessage(requestError instanceof Error ? requestError.message : "Could not start test."); }
    finally { setBusy(""); }
  }
  return <main className="placement-main student-home">
    <PanelHeading eyebrow="STUDENT WORKSPACE" title="Your assigned tests" description="Start an available placement assessment. Your timer is based on server-synced deadlines." />
    <StatusMessage error={error || message} />
    {resumeAttemptId && <section className="placement-card placement-resume"><div><span className="placement-eyebrow">IN-PROGRESS ATTEMPT</span><h2>Continue where you left off</h2><p>Your saved answers and remaining time are restored from the server.</p></div><button className="placement-button primary" onClick={onResume}>Resume test <ArrowRight size={14} /></button></section>}
    <section className="placement-card">
      <div className="placement-card-heading"><div><span className="placement-eyebrow">TEST ASSIGNMENTS</span><h2>Ready when you are</h2></div><button className="placement-button secondary" onClick={() => void reload()}>Refresh</button></div>
      {loading ? <p className="placement-muted">Loading assignments…</p> : assignments?.length ? <div className="placement-test-list">{assignments.map((assignment) => <article key={assignment.id}><span className={`placement-pill ${assignment.status}`}>{assignment.status}</span><h3>{assignment.test_title}</h3><p>{new Date(assignment.starts_at).toLocaleString()} {assignment.ends_at ? `– ${new Date(assignment.ends_at).toLocaleString()}` : "· No closing time"}</p><button className="placement-button primary" disabled={busy === assignment.id || assignment.status !== "active" || Boolean(resumeAttemptId)} onClick={() => void start(assignment)}>{busy === assignment.id ? "Preparing…" : "Start timed test"} <ArrowRight size={15} /></button></article>)}</div> : <div className="placement-empty"><CircleHelp size={22} />No tests are assigned to your account right now.</div>}
    </section>
    <StudentAnalytics />
  </main>;
}

function StudentAnalytics() {
  const { data, error } = useRemote<{ attempts_completed: number; average_score_percent: number; topic_breakdown: Array<Record<string, unknown>> }>("/analytics/student");
  return <section className="placement-card"><div className="placement-card-heading"><div><span className="placement-eyebrow">MY PERFORMANCE</span><h2>Readiness snapshot</h2></div></div>
    <StatusMessage error={error} />
    <div className="placement-metric-grid"><Metric label="Completed attempts" value={String(data?.attempts_completed ?? 0)} /><Metric label="Average score" value={`${Number(data?.average_score_percent ?? 0)}%`} /></div>
    {(data?.topic_breakdown ?? []).length ? <div className="placement-table-wrap"><table className="placement-table"><thead><tr><th>Topic</th><th>Accuracy</th><th>Average speed</th></tr></thead><tbody>{data?.topic_breakdown.map((topic, index) => <tr key={`${String(topic.topic_slug)}-${index}`}><td>{String(topic.topic_slug)}</td><td>{String(topic.accuracy_percent)}%</td><td>{String(topic.avg_time_seconds)}s</td></tr>)}</tbody></table></div> : <p className="placement-muted">Topic analytics appear after you submit your first test.</p>}
  </section>;
}

export function PlacementRunner({ attempt: initialAttempt, onAttemptChange, onResult, onExit, result }: {
  attempt: PlacementAttempt;
  onAttemptChange: (attempt: PlacementAttempt) => void;
  onResult: (result: AttemptResult) => void;
  onExit: () => void;
  result: AttemptResult | null;
}) {
  const [attempt, setAttempt] = useState(initialAttempt);
  const [position, setPosition] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const [now, setNow] = useState(Date.now);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [resultLoading, setResultLoading] = useState(false);
  const [reviewMarked, setReviewMarked] = useState(false);
  const autoSubmitStarted = useRef(false);
  const question = attempt.questions[position];
  const [serverOffset, setServerOffset] = useState(() => Date.parse(initialAttempt.server_time) - Date.now());
  const remaining = Math.max(0, Math.ceil((Date.parse(attempt.deadline_at) - (now + serverOffset)) / 1000));
  const timeLabel = `${String(Math.floor(remaining / 60)).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`;

  useEffect(() => {
    setAttempt(initialAttempt);
    setServerOffset(Date.parse(initialAttempt.server_time) - Date.now());
    setReviewMarked(Boolean(initialAttempt.questions[position]?.marked_for_review));
  }, [initialAttempt]);
  useEffect(() => {
    if (result) return;
    const timer = window.setInterval(() => {
      setNow(Date.now());
      setSeconds((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [Boolean(result)]);
  useEffect(() => {
    if (question) {
      setReviewMarked(question.marked_for_review);
      setSeconds(0);
    }
  }, [position, question?.question_id]);

  async function saveAnswer(selected: string | null, marked = reviewMarked) {
    setSaving(true); setError("");
    try {
      const updated = await placementRequest<PlacementAttempt>(`/attempts/${attempt.id}/answer`, placementJson("PATCH", {
        question_position: position, selected_option_id: selected, marked_for_review: marked, time_spent_seconds: seconds,
      }));
      setAttempt(updated); onAttemptChange(updated);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Answer could not be saved."); }
    finally { setSaving(false); }
  }
  function navigateTo(target: number) {
    if (target === position) return;
    void saveAnswer(question.selected_option_id);
    setPosition(target);
  }
  async function submitAttempt(automatic = false) {
    if (!automatic && !window.confirm("Submit this test now? You will not be able to change answers afterward.")) return;
    setResultLoading(true); setError("");
    try {
      const submitted = await placementRequest<AttemptResult>(`/attempts/${attempt.id}/submit`, placementJson("POST", {}));
      onResult(submitted);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Submission failed."); }
    finally { setResultLoading(false); }
  }
  useEffect(() => {
    if (remaining === 0 && !saving && !result && !autoSubmitStarted.current) {
      autoSubmitStarted.current = true;
      void submitAttempt(true);
    }
  }, [remaining, result, saving]);
  if (result) return <PlacementResult attempt={attempt} result={result} onExit={onExit} />;
  return <main className="placement-runner">
    <header className="placement-runner-header"><button className="placement-text-button" onClick={onExit}><ArrowLeft size={16} /> Exit</button><div><strong>{attempt.title}</strong><small>Question {position + 1} of {attempt.questions.length}</small></div><div className={`placement-timer ${remaining < 60 ? "urgent" : ""}`} aria-label={`Time remaining ${timeLabel}`}><Clock3 size={16} />{timeLabel}</div></header>
    <StatusMessage error={error} />
    <div className="placement-runner-layout">
      <section className="placement-card placement-question-card">
        <div className="placement-question-meta"><span>{question.topic_slug.replaceAll("-", " ")}</span><span>{question.difficulty}</span><span>Target {question.estimated_seconds}s</span></div>
        <h1>{question.stem}</h1>
        <Stimulus stimulus={question.stimulus} />
        {question.latex && <pre className="placement-code">{question.latex}</pre>}
        {question.options.map((option, index) => <button key={option.id} className={`placement-answer ${question.selected_option_id === option.id ? "chosen" : ""}`} onClick={() => void saveAnswer(option.id)}><kbd>{index + 1}</kbd>{option.text}</button>)}
        <div className="placement-question-controls"><button className={`placement-button ${reviewMarked ? "marked" : "secondary"}`} onClick={() => { const next = !reviewMarked; setReviewMarked(next); void saveAnswer(question.selected_option_id, next); }}><Archive size={14} />{reviewMarked ? "Marked for review" : "Mark for review"}</button><span className="placement-save-state" role="status">{saving ? "Saving answer…" : question.selected_option_id ? "Answer saved" : "Not answered"}</span></div>
        <div className="placement-runner-controls"><button className="placement-button secondary" disabled={position === 0} onClick={() => navigateTo(position - 1)}>Previous</button><button className="placement-button primary" disabled={position === attempt.questions.length - 1} onClick={() => navigateTo(position + 1)}>Next <ArrowRight size={14} /></button></div>
      </section>
      <aside className="placement-card placement-palette"><h2>Question palette</h2><p>Select a question to navigate.</p><div>{attempt.questions.map((item, index) => <button key={item.question_id} aria-label={`Go to question ${index + 1}`} className={`${index === position ? "current" : ""} ${item.selected_option_id ? "answered" : ""} ${item.marked_for_review ? "flagged" : ""}`} onClick={() => navigateTo(index)}>{index + 1}</button>)}</div><ul><li><i className="answered" /> Answered</li><li><i className="flagged" /> Review</li><li><i /> Unanswered</li></ul></aside>
    </div>
    <footer className="placement-submit-bar"><span>{attempt.questions.filter((item) => item.selected_option_id).length} / {attempt.questions.length} answered</span><button className="placement-button primary" disabled={resultLoading || saving} onClick={() => void submitAttempt()}>{resultLoading ? "Submitting…" : "Submit test"} <Check size={15} /></button></footer>
  </main>;
}

function Stimulus({ stimulus }: { stimulus: AttemptQuestion["stimulus"] }) {
  if (!stimulus || typeof stimulus !== "object") return null;
  const kind = stimulus.kind;
  const title = typeof stimulus.title === "string" ? stimulus.title : "";
  if (kind === "table" && Array.isArray(stimulus.headers) && Array.isArray(stimulus.rows)) {
    return <div className="placement-stimulus"><strong>{title}</strong><div className="placement-table-wrap"><table className="placement-table"><thead><tr>{stimulus.headers.map((header, index) => <th key={`${String(header)}-${index}`}>{String(header)}</th>)}</tr></thead><tbody>{stimulus.rows.map((row, index) => <tr key={index}>{Array.isArray(row) ? row.map((cell, cellIndex) => <td key={cellIndex}>{String(cell)}</td>) : null}</tr>)}</tbody></table></div></div>;
  }
  if ((kind === "passage" || kind === "code") && typeof stimulus.content === "string") {
    return <div className={`placement-stimulus ${kind}`}>{title && <strong>{title}</strong>}{kind === "code" ? <pre>{stimulus.content}</pre> : <p>{stimulus.content}</p>}</div>;
  }
  return null;
}

export function PlacementResult({ attempt, result, onExit }: { attempt: PlacementAttempt; result: AttemptResult; onExit: () => void }) {
  const [review, setReview] = useState(false);
  const [practiceQuestions, setPracticeQuestions] = useState<PracticeQuestion[]>([]);
  const [practiceAnswers, setPracticeAnswers] = useState<Record<number, string>>({});
  const [practiceLoading, setPracticeLoading] = useState(false);
  const [practiceError, setPracticeError] = useState("");
  const topics = useMemo(() => result.topic_breakdown, [result.topic_breakdown]);
  async function practiceWeakTopics() {
    const weakTopics = [...topics]
      .sort((left, right) => Number(left.accuracy_percent) - Number(right.accuracy_percent))
      .slice(0, 3)
      .map((topic) => String(topic.topic_slug));
    setPracticeLoading(true); setPracticeError("");
    try {
      const generated = await placementRequest<PracticeQuestion[]>("/practice/similar", placementJson("POST", {
        attempt_id: result.attempt_id,
        topic_slugs: weakTopics,
        question_count: Math.max(1, weakTopics.length * 2),
      }));
      setPracticeQuestions(generated);
      setPracticeAnswers({});
    } catch (requestError) {
      setPracticeError(requestError instanceof Error ? requestError.message : "Could not generate weak-topic practice.");
    } finally { setPracticeLoading(false); }
  }
  return <main className="placement-main placement-result-page">
    <div className="placement-result-header"><div><p className="placement-eyebrow">TEST SUBMITTED</p><h1>{attempt.title}</h1><span>{result.passed ? "Passed" : "Keep practicing"} · {result.correct} correct · {result.incorrect} incorrect · {result.unanswered} unanswered</span></div><strong>{result.score}<small> / {result.max_score}</small></strong></div>
    <div className="placement-metric-grid"><Metric label="Score" value={`${Math.round(result.score / Math.max(1, result.max_score) * 100)}%`} /><Metric label="Accuracy" value={`${result.accuracy_percent}%`} /><Metric label="Correct" value={String(result.correct)} /><Metric label="Status" value={result.passed ? "Passed" : "Review"} /></div>
    <section className="placement-card"><div className="placement-card-heading"><div><span className="placement-eyebrow">TOPIC DIAGNOSTICS</span><h2>Accuracy & speed matrix</h2></div><button className="placement-button primary" disabled={practiceLoading || topics.length === 0} onClick={() => void practiceWeakTopics()}>{practiceLoading ? "Generating practice…" : "Practice weak topics"} <Sparkles size={14} /></button></div>
      <div className="placement-table-wrap"><table className="placement-table"><thead><tr><th>Topic</th><th>Correct</th><th>Incorrect</th><th>Unanswered</th><th>Accuracy</th><th>Avg time</th></tr></thead><tbody>{topics.map((topic, index) => <tr key={`${String(topic.topic_slug)}-${index}`}><td>{String(topic.topic_slug)}</td><td>{String(topic.correct)}</td><td>{String(topic.incorrect)}</td><td>{String(topic.unanswered)}</td><td>{String(topic.accuracy_percent)}%</td><td>{String(topic.avg_time_seconds)}s</td></tr>)}</tbody></table></div>
      {practiceError && <p className="placement-error" role="alert">{practiceError}</p>}
      {practiceQuestions.length > 0 && <div className="placement-practice-list">{practiceQuestions.map((question, index) => <article key={`${question.topic_slug}-${index}`}><span className="placement-eyebrow">{question.topic_slug} · FRESH PRACTICE</span><h3>{question.stem}</h3><Stimulus stimulus={question.stimulus} />{question.options.map((option) => <button key={option.id} className={`placement-answer ${practiceAnswers[index] === option.id ? option.id === question.correct_option_id ? "chosen" : "incorrect-answer" : ""}`} onClick={() => setPracticeAnswers((previous) => ({ ...previous, [index]: option.id }))}>{option.text}</button>)}{practiceAnswers[index] && <div className="placement-practice-solution"><strong>{practiceAnswers[index] === question.correct_option_id ? "Correct" : "Review the solution"}</strong><p><b>Shortcut:</b> {question.shortcut_solution}</p><p><b>Concept:</b> {question.concept_solution}</p></div>}</article>)}</div>}
    </section>
    <section className="placement-card"><div className="placement-card-heading"><div><span className="placement-eyebrow">LEARN FROM THE ATTEMPT</span><h2>Question review</h2></div><button className="placement-button secondary" onClick={() => setReview((value) => !value)}>{review ? "Hide solutions" : "Review solutions"}</button></div>
      {review && <div className="placement-review-list">{result.answers.map((answer) => <article key={answer.question_id}><div className="placement-question-meta"><span>{answer.topic_slug}</span><span>{answer.time_spent_seconds}s / {answer.estimated_seconds}s target</span><b className={answer.is_correct ? "correct" : "incorrect"}>{answer.mistake_tag.replaceAll("_", " ")}</b></div><h3>{answer.stem}</h3><p><strong>Correct answer:</strong> {answer.options.find((option) => option.id === answer.correct_option_id)?.text ?? answer.correct_option_id}</p><p><strong>Shortcut:</strong> {answer.shortcut_solution}</p><p><strong>Concept:</strong> {answer.concept_solution}</p></article>)}</div>}
    </section>
    <button className="placement-button primary" onClick={onExit}>Back to workspace</button>
  </main>;
}
