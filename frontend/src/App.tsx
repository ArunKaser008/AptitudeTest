import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpenCheck,
  Bookmark,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileQuestion,
  Flag,
  Gauge,
  LayoutDashboard,
  Lightbulb,
  Menu,
  MessageCircle,
  RotateCcw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  Timer,
  Trophy,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link, NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { AssessmentCatalogPage, AssessmentExamPage, AssessmentResultsPage } from "./AssessmentFlow";
import { AuthoringPage } from "./AuthoringFlow";
import { PageHeading } from "./components/PageHeading";
import { allAssessmentQuestions, assessmentQuestionBanks } from "./data/assessmentQuestionBanks";
import {
  assessments,
  companies,
  isDemoData,
  overview,
  performanceTrend,
  questions,
  recommendations,
  sectionScores,
  type AssessmentQuestion,
} from "./data/mockData";
import {
  completePreviewAttempt,
  getPreviewDurationMinutes,
  getPreviewQuestionCount,
  getSecondsRemaining,
  loadPreviewPracticeSession,
  loadPreviewAttempt,
  loadPreviewResult,
  sampleNewQuestionSet,
  savePreviewAttempt,
  savePreviewPracticeSession,
  startPreviewAttempt,
  type PreviewAttempt,
  type PreviewAttemptResult,
  type PreviewPracticeSession,
} from "./services/previewAssessment";

const navGroups = [
  {
    label: "WORKSPACE",
    links: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard },
      { to: "/aptitude", label: "Aptitude assessment", icon: FileQuestion },
      { to: "/practice", label: "Practice zone", icon: BookOpenCheck },
      { to: "/companies", label: "Company mock tests", icon: BriefcaseBusiness },
    ],
  },
  {
    label: "YOUR PROGRESS",
    links: [
      { to: "/performance", label: "My performance", icon: BarChart3 },
      { to: "/recommendations", label: "Recommendations", icon: Lightbulb },
    ],
  },
  {
    label: "ADMINISTRATION",
    links: [{ to: "/aptitude/manage", label: "Assessment studio", icon: Settings }],
  },
];

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const isAssessmentRoute = location.pathname.startsWith("/aptitude")
    || location.pathname.startsWith("/exam/")
    || location.pathname.startsWith("/results/");

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <Link to="/" className="brand" onClick={() => setSidebarOpen(false)}>
          <span className="brand-mark"><img src="/mentormuni-logo.png" alt="" /></span>
          <span>Mentor<span className="brand-light">Muni</span><small>PLACEMENT READINESS</small></span>
        </Link>
        <div className="profile-switch">
          <div className="avatar">AN</div>
          <div className="profile-copy"><strong>Guest candidate</strong><span>Assessment workspace</span></div>
          <ChevronDown size={16} className="muted-icon" />
        </div>
        <nav className="side-nav" aria-label="Main navigation">
          {navGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <p className="nav-heading">{group.label}</p>
              {group.links.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                >
                  <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
                  {label === "Recommendations" && <span className="nav-count">3</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="mentor-card">
            <span className="mentor-icon"><MessageCircle size={17} /></span>
            <strong>Need a little guidance?</strong>
            <p>Your next step is one focused practice session away.</p>
            <Link to="/recommendations">View my plan <ArrowRight size={14} /></Link>
          </div>
          <div className="sidebar-foot"><ShieldCheck size={15} /> Your progress stays yours</div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumb"><span>Student workspace</span><ChevronRight size={15} /><strong>Placement readiness</strong></div>
          <div className="topbar-actions">
            <Link className="icon-button search-button" aria-label="Browse assessments" to="/aptitude"><Search size={18} /></Link>
            <a className="help-button" href="mailto:enroll@mentormuni.com"><CircleHelp size={17} /><span>Help centre</span></a>
            <div className="top-avatar" aria-label="Anonymous candidate">AN</div>
          </div>
        </header>
        {isDemoData && !isAssessmentRoute && <div className="demo-banner"><Sparkles size={14} /><span>Preview workspace</span><span className="demo-separator">·</span><span>Sample data on this screen is for demonstration and is not connected to a live account.</span></div>}
        <main className="page-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/aptitude" element={<AssessmentCatalogPage />} />
            <Route path="/exam/:assessmentId" element={<AssessmentExamPage />} />
            <Route path="/results/:assessmentId" element={<AssessmentResultsPage />} />
            <Route path="/aptitude/manage" element={<AuthoringPage />} />
            <Route path="/admin/questions" element={<AuthoringPage />} />
            <Route path="/practice" element={<PracticePage />} />
            <Route path="/performance" element={<PerformancePage />} />
            <Route path="/companies" element={<CompaniesPage />} />
            <Route path="/recommendations" element={<RecommendationsPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function Dashboard() {
  return (
    <>
      <PageHeading eyebrow="FRIDAY, 20 NOVEMBER" title="Good afternoon, Arun" description="A little focused practice today can make a big difference on placement day." action={<Link className="button button-primary" to="/aptitude"><Target size={17} /> Take an assessment</Link>} />
      <div className="readiness-banner">
        <div className="readiness-copy"><span className="banner-label"><Sparkles size={15} /> YOUR PLACEMENT READINESS</span><div className="readiness-number">{overview.readiness}<span>/100</span></div><p>You’re building a strong foundation. A little more focus on data interpretation will move you forward.</p><Link to="/performance" className="banner-link">See your full readiness report <ArrowRight size={15} /></Link></div>
        <div className="readiness-art" aria-label="Readiness score 68 out of 100">
          <div className="score-ring"><div><strong>{overview.readiness}</strong><span>READINESS</span></div></div>
          <div className="ring-caption"><span className="ring-dot" /> Developing <span className="ring-divider">·</span> Keep it up</div>
          <div className="floating-chip chip-one"><ArrowUpRight size={15} /> +12 pts</div>
          <div className="floating-chip chip-two"><Trophy size={14} /> 8 tests done</div>
        </div>
      </div>
      <section className="metric-grid" aria-label="Your assessment overview">
        <MetricCard icon={<FileQuestion size={18} />} label="Tests completed" value={`${overview.testsCompleted}`} note="2 this month" tone="blue" />
        <MetricCard icon={<Target size={18} />} label="Average accuracy" value={`${overview.accuracy}%`} note="Across all attempts" tone="green" />
        <MetricCard icon={<Timer size={18} />} label="Average speed" value={overview.avgSpeed} note="Per question" tone="purple" />
        <MetricCard icon={<Clock3 size={18} />} label="Practice time" value={overview.practiceTime} note="You’re showing up!" tone="amber" />
      </section>
      <div className="content-grid dashboard-grid">
        <section className="panel trend-panel">
          <div className="panel-heading"><div><h2>Your progress over time</h2><p>A steady upward trend. Nice work!</p></div><Link to="/performance" className="text-link">View report <ArrowRight size={14} /></Link></div>
          <div className="chart-legend"><span><i className="legend-dot blue-dot" /> Readiness score</span><span><i className="legend-dot green-dot" /> Accuracy</span></div>
          <div className="trend-chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={performanceTrend} margin={{ top: 8, right: 4, bottom: 0, left: -18 }}>
                <defs><linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#1a8fc4" stopOpacity={0.17} /><stop offset="100%" stopColor="#1a8fc4" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke="#edf1f5" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: "#8792a0", fontSize: 11 }} dy={9} />
                <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fill: "#8792a0", fontSize: 11 }} />
                <Tooltip contentStyle={{ border: "1px solid #e8edf2", borderRadius: 12, boxShadow: "0 8px 24px #172e4a12" }} />
                <Area type="monotone" dataKey="score" name="Readiness" stroke="#1a8fc4" strokeWidth={2.5} fill="url(#scoreFill)" />
                <Area type="monotone" dataKey="accuracy" name="Accuracy" stroke="#52b788" strokeWidth={2} fill="transparent" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="trend-insight"><span className="insight-icon"><ArrowUpRight size={16} /></span><span><strong>12 points up</strong> since your first assessment</span></div>
        </section>
        <section className="panel section-panel">
          <div className="panel-heading"><div><h2>Section snapshot</h2><p>Where you’re shining and where to focus</p></div><Link to="/performance" className="text-link">Details <ArrowRight size={14} /></Link></div>
          <div className="section-list">{sectionScores.map((item) => <div className="section-score" key={item.name}><div className="section-score-top"><span>{item.name}</span><strong>{item.score}%</strong></div><div className="progress-track"><div className="progress-fill" style={{ width: `${item.score}%`, background: item.color }} /></div></div>)}</div>
          <div className="section-insight"><Lightbulb size={16} /><span><strong>Data interpretation</strong> is a good place to focus next.</span></div>
        </section>
      </div>
      <div className="content-grid lower-grid">
        <section className="panel recommendations-panel">
          <div className="panel-heading"><div><span className="section-kicker"><Sparkles size={14} /> YOUR NEXT STEPS</span><h2>Picked for your progress</h2></div><Link to="/recommendations" className="text-link">See all <ArrowRight size={14} /></Link></div>
          <div className="recommendation-list">{recommendations.slice(0, 2).map((item, index) => <Link className="recommendation-row" to="/practice" key={item.title}><span className={`rec-icon ${item.tone}`}>{index === 0 ? <Timer size={17} /> : <BarChart3 size={17} />}</span><span className="rec-copy"><strong>{item.title}</strong><span>{item.detail}</span><small>{item.meta}</small></span><ArrowRight size={17} className="row-arrow" /></Link>)}</div>
        </section>
        <section className="panel continue-panel">
          <div className="continue-top"><span className="continue-icon"><BookOpenCheck size={19} /></span><span className="continue-label">PICK UP WHERE YOU LEFT OFF</span></div>
          <h2>Strengthen your fundamentals</h2><p>Your last session: Percentages &amp; ratios</p>
          <div className="continue-progress"><div className="progress-track"><div className="progress-fill" style={{ width: "62%" }} /></div><span>62%</span></div>
          <Link className="button button-outline continue-button" to="/practice">Continue learning <ArrowRight size={15} /></Link>
        </section>
      </div>
      <section className="journey-strip"><span className="journey-icon"><Trophy size={19} /></span><span><strong>You’ve improved 12 points</strong><small>Every practice session is adding up. Keep your momentum going.</small></span><Link to="/performance" className="text-link">Your journey <ArrowRight size={14} /></Link></section>
    </>
  );
}

function MetricCard({ icon, label, value, note, tone }: { icon: React.ReactNode; label: string; value: string; note: string; tone: string }) {
  return <article className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><span className="metric-note">{note}</span></article>;
}

export function PreviewAssessmentCatalog() {
  const navigate = useNavigate();
  const [level, setLevel] = useState("All levels");
  const visibleAssessments = assessments.filter((assessment) => level === "All levels" || assessment.level === "Intermediate");
  return (
    <>
      <PageHeading eyebrow="MEASURE YOUR READINESS" title="Aptitude assessments" description="Find your baseline, build confidence, and see your progress with each attempt." />
      <div className="callout callout-blue"><span className="callout-icon"><ShieldCheck size={18} /></span><span><strong>Practice simulations, not official company assessments.</strong><small>Company-style tests are based on publicly available information and may not reflect current hiring processes.</small></span></div>
      <div className="catalog-toolbar"><div><h2>Choose your assessment</h2><p>Take your time. You can review details before you begin.</p></div><label className="filter-select"><span className="sr-only">Filter assessments by level</span><select value={level} onChange={(event) => setLevel(event.target.value)}><option>All levels</option><option>Intermediate</option></select><ChevronDown size={14} /></label></div>
      <div className="assessment-grid">{visibleAssessments.map((assessment, index) => {
        const bank = assessmentQuestionBanks[assessment.id] ?? [];
        const questionCount = getPreviewQuestionCount(assessment, bank);
        const durationMinutes = getPreviewDurationMinutes(assessment, bank);
        return <article className="assessment-card" key={assessment.id}>
          <div className="assessment-card-top"><span className={`assessment-icon assessment-icon-${index}`}><FileQuestion size={20} /></span><span className={`badge ${index === 2 ? "badge-neutral" : index === 1 ? "badge-purple" : "badge-green"}`}>{assessment.badge}</span></div>
          <h3>{assessment.title}</h3><p className="assessment-description">{assessment.description}</p>
          <div className="assessment-meta"><span><FileQuestion size={15} />{questionCount} sample questions</span><span><Clock3 size={15} />{durationMinutes} min preview</span><span><Gauge size={15} />{assessment.level}</span></div>
          <div className="chip-list">{assessment.sections.map((section) => <span className="topic-chip" key={section}>{section}</span>)}</div>
          <button className="button button-primary full-button" onClick={() => { startPreviewAttempt(assessment, bank); navigate(`/exam/${assessment.id}`); }}>Start {questionCount}-question preview <ArrowRight size={16} /></button>
        </article>;
      })}</div>
      <div className="catalog-footer"><ShieldCheck size={17} /><span>Preview mode: assessments use sample questions and do not save responses to a candidate account.</span></div>
    </>
  );
}

export function PreviewExamPage() {
  const { assessmentId = "foundation" } = useParams();
  const navigate = useNavigate();
  const assessment = assessments.find((item) => item.id === assessmentId);
  const bank = assessment ? assessmentQuestionBanks[assessment.id] ?? [] : [];
  const [attempt, setAttempt] = useState<PreviewAttempt | null>(() => assessment ? loadPreviewAttempt(assessment, bank) : null);
  const [confirm, setConfirm] = useState(false);
  const submitted = useRef(false);
  const questionsById = new Map([...questions, ...allAssessmentQuestions].map((question) => [question.id, question]));
  const attemptQuestions = attempt?.questionIds
    .map((questionId) => questionsById.get(questionId))
    .filter((question): question is AssessmentQuestion => question !== undefined) ?? [];
  const question = attempt && attemptQuestions.length > 0
    ? attemptQuestions[attempt.currentQuestion]
    : undefined;
  const selected = question ? attempt?.responses[question.id] ?? null : null;
  const totalQuestions = attemptQuestions.length;
  const currentQuestion = question ? attempt?.currentQuestion ?? 0 : 0;
  const [clockNow, setClockNow] = useState(Date.now);
  const remainingSeconds = attempt ? getSecondsRemaining(attempt.deadlineAt, clockNow) : 0;
  const formattedTime = `${String(Math.floor(remainingSeconds / 3600)).padStart(2, "0")}:${String(Math.floor((remainingSeconds % 3600) / 60)).padStart(2, "0")}:${String(remainingSeconds % 60).padStart(2, "0")}`;

  useEffect(() => {
    if (assessment && !attempt) {
      setAttempt(startPreviewAttempt(assessment, bank));
    }
  }, [assessment, attempt, bank]);

  useEffect(() => {
    if (attempt) savePreviewAttempt(attempt);
  }, [attempt]);

  useEffect(() => {
    if (!attempt) return;
    const syncClock = () => setClockNow(Date.now());
    const timer = window.setInterval(syncClock, 1000);
    window.addEventListener("focus", syncClock);
    document.addEventListener("visibilitychange", syncClock);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", syncClock);
      document.removeEventListener("visibilitychange", syncClock);
    };
  }, [Boolean(attempt)]);

  const finishAttempt = () => {
    if (!assessment || !attempt || submitted.current) return;
    submitted.current = true;
    const result: PreviewAttemptResult = {
      assessmentId: assessment.id,
      questionIds: attempt.questionIds,
      responses: attempt.responses,
      elapsedSeconds: Math.min(
        attempt.durationSeconds,
        Math.max(0, attempt.durationSeconds - getSecondsRemaining(attempt.deadlineAt)),
      ),
    };
    completePreviewAttempt(result);
    navigate(`/results/${assessment.id}`, { replace: true });
  };

  useEffect(() => {
    if (attempt && remainingSeconds === 0) finishAttempt();
  }, [Boolean(attempt), remainingSeconds]);

  const updateAttempt = (updates: Partial<PreviewAttempt>) => {
    setAttempt((current) => current ? { ...current, ...updates } : current);
  };

  if (!assessment) return <NotFound />;
  if (!attempt || !question) return <div className="exam-shell"><div className="panel">Preparing a fresh preview question set…</div></div>;

  return <div className="exam-shell">
    <div className="exam-top"><Link to="/aptitude" className="exam-brand"><span className="brand-mark"><img src="/mentormuni-logo.png" alt="" /></span> MentorMuni <span className="exam-divider">/</span> {assessment?.title || "Assessment"}</Link><span className="exam-candidate">Candidate <strong>AS-2048</strong></span></div>
    <div className="exam-status"><span><span className="live-dot" /> Timed preview</span><span className="exam-progress-copy">Question {currentQuestion + 1} of {totalQuestions}</span><div className="exam-progress"><div style={{ width: `${((currentQuestion + 1) / totalQuestions) * 100}%` }} /></div><span className={`exam-timer ${remainingSeconds <= 300 ? "urgent" : ""}`} aria-label={`Time remaining ${formattedTime}`}><Clock3 size={17} /> {formattedTime}</span></div>
    <div className="exam-content"><div className="exam-question-panel">
      <div className="question-overline"><span>QUESTION {String(currentQuestion + 1).padStart(2, "0")}</span><span className="badge badge-green">{question.difficulty}</span><span className="question-topic">{question.topic}</span></div>
      <h1>{question.prompt}</h1>
      <p className="question-hint">Choose one answer from the options below.</p>
      <div className="answer-options" role="group" aria-label="Answer options">{question.options.map((option, index) => <button key={option} aria-pressed={selected === index} className={`answer-option ${selected === index ? "selected" : ""}`} onClick={() => updateAttempt({ responses: { ...attempt.responses, [question.id]: index } })}><span className="option-key">{String.fromCharCode(65 + index)}</span><span>{option}</span>{selected === index && <Check size={17} className="option-check" />}</button>)}</div>
      <div className="question-actions"><button className={`button button-outline ${attempt.marked.includes(question.id) ? "marked-button" : ""}`} onClick={() => updateAttempt({ marked: attempt.marked.includes(question.id) ? attempt.marked.filter((id) => id !== question.id) : [...attempt.marked, question.id] })}><Flag size={16} /> {attempt.marked.includes(question.id) ? "Marked for review" : "Mark for review"}</button><button className="clear-button" onClick={() => { const responses = { ...attempt.responses }; delete responses[question.id]; updateAttempt({ responses }); }}><RotateCcw size={15} /> Clear response</button></div>
      <div className="exam-navigation"><button className="button button-outline" disabled={currentQuestion === 0} onClick={() => updateAttempt({ currentQuestion: currentQuestion - 1 })}><ChevronLeft size={16} /> Previous</button><button className="button button-primary" onClick={() => { if (currentQuestion === totalQuestions - 1) setConfirm(true); else updateAttempt({ currentQuestion: currentQuestion + 1 }); }}>{currentQuestion === totalQuestions - 1 ? "Review and submit" : "Next question"} <ChevronRight size={16} /></button></div>
    </div>
    <aside className="exam-palette-panel"><h2>Question palette</h2><p>Navigate through your assessment</p><div className="palette-legend"><span><i className="palette-dot answered" /> Answered</span><span><i className="palette-dot review" /> Review</span><span><i className="palette-dot" /> Not visited</span></div><div className="question-palette">{attempt.questionIds.map((questionId, index) => <button key={questionId} aria-label={`Question ${index + 1}`} className={`${index === currentQuestion ? "current" : ""} ${attempt.marked.includes(questionId) ? "review" : attempt.responses[questionId] !== undefined ? "answered" : ""}`} onClick={() => updateAttempt({ currentQuestion: index })}>{index + 1}</button>)}</div><div className="palette-note"><ShieldCheck size={16} /><span>Preview progress is saved in this browser tab. It is not a secure live assessment.</span></div><button className="submit-assessment" onClick={() => setConfirm(true)}>Submit assessment <ArrowRight size={16} /></button></aside></div>
    {confirm && <div className="modal-backdrop" role="presentation"><div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><button className="modal-close" aria-label="Close" onClick={() => setConfirm(false)}><X size={19} /></button><span className="modal-symbol"><Flag size={21} /></span><h2 id="confirm-title">Submit your assessment?</h2><p>You’ve answered {Object.keys(attempt.responses).length} of {totalQuestions} questions. You can still go back and review your responses.</p><div className="modal-actions"><button className="button button-outline" onClick={() => setConfirm(false)}>Keep reviewing</button><button className="button button-primary" onClick={finishAttempt}>Submit assessment</button></div></div></div>}
  </div>;
}

export function PreviewResultsPage() {
  const navigate = useNavigate();
  const { assessmentId = "" } = useParams();
  const assessment = assessments.find((item) => item.id === assessmentId);
  const [result] = useState(() => loadPreviewResult(assessmentId));
  if (!assessment || !result) {
    return <div className="not-found"><span className="not-found-icon"><CircleHelp size={22} /></span><h1>Assessment result unavailable</h1><p>Finish a preview assessment to see its score and answer breakdown.</p><Link to="/aptitude" className="button button-primary">Choose an assessment <ArrowRight size={15} /></Link></div>;
  }
  const questionsById = new Map([...questions, ...allAssessmentQuestions].map((question) => [question.id, question]));
  const attemptQuestions = result.questionIds
    .map((questionId) => questionsById.get(questionId))
    .filter((question): question is AssessmentQuestion => question !== undefined);
  const total = attemptQuestions.length;
  const correct = attemptQuestions.filter((question) => result.responses[question.id] === question.answer).length;
  const attempted = Object.keys(result.responses).length;
  const incorrect = attempted - correct;
  const unanswered = total - attempted;
  const accuracy = attempted === 0 ? 0 : Math.round((correct / attempted) * 100);
  const attemptRate = total === 0 ? 0 : Math.round((attempted / total) * 100);
  const minutesUsed = Math.floor(result.elapsedSeconds / 60);
  const secondsUsed = result.elapsedSeconds % 60;
  const score = total === 0 ? 0 : Math.round((correct / total) * 100);
  const breakdown = [
    { name: "Correct", value: correct },
    { name: "Incorrect", value: incorrect },
    { name: "Unanswered", value: unanswered },
  ];
  return <>
    <PageHeading eyebrow="YOUR ASSESSMENT REPORT" title="Your results" description={`${assessment.title} · ${total} questions in this preview attempt`} action={<button className="button button-outline" onClick={() => navigate("/performance")}>View all performance <ArrowRight size={15} /></button>} />
    <div className="results-hero"><div className="results-score"><span>ASSESSMENT SCORE</span><strong>{score}<small>/100</small></strong><em><ShieldCheck size={14} /> Based on this attempt only</em></div><div className="results-divider" /><div className="results-stats"><div><span>Accuracy</span><strong>{accuracy}%</strong></div><div><span>Attempt rate</span><strong>{attemptRate}%</strong></div><div><span>Correct</span><strong>{correct} <small>of {total}</small></strong></div><div><span>Time used</span><strong>{minutesUsed}<small>m {secondsUsed}s</small></strong></div></div></div>
    <div className="content-grid results-grid"><section className="panel"><div className="panel-heading"><div><h2>Topic performance</h2><p>Accuracy from the questions in this attempt</p></div></div><div className="results-section-list">{Array.from(new Set(attemptQuestions.map((question) => question.topic))).map((topic) => { const topicQuestions = attemptQuestions.filter((question) => question.topic === topic); const topicCorrect = topicQuestions.filter((question) => result.responses[question.id] === question.answer).length; const topicAccuracy = Math.round((topicCorrect / topicQuestions.length) * 100); return <div className="results-section-row" key={topic}><div className="results-section-name"><span className="section-color" style={{ backgroundColor: topicAccuracy >= 70 ? "#52b788" : "#f0a64b" }} />{topic}<strong>{topicAccuracy}%</strong></div><div className="progress-track"><div className="progress-fill" style={{ width: `${topicAccuracy}%`, backgroundColor: topicAccuracy >= 70 ? "#52b788" : "#f0a64b" }} /></div></div>; })}</div></section>
      <section className="panel breakdown-panel">
        <div className="panel-heading"><div><h2>Your answer breakdown</h2><p>{total} questions in this preview attempt</p></div></div>
        <div className="breakdown-layout">
          <div className="donut-wrap" role="img" aria-label={`Out of ${total} questions: ${correct} correct, ${incorrect} incorrect, ${unanswered} unanswered`}>
            <div className="donut-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={breakdown} dataKey="value" innerRadius="58%" outerRadius="78%" paddingAngle={3} stroke="#101b2a" strokeWidth={3}><Cell fill="#61c98d" /><Cell fill="#f07f79" /><Cell fill="#60758b" /></Pie><Tooltip /></PieChart></ResponsiveContainer></div>
            <div className="donut-center"><strong>{total}</strong><span>QUESTIONS</span></div>
          </div>
          <div className="breakdown-legend" aria-label="Question outcomes">
            <div className="breakdown-item"><span className="breakdown-label"><i className="legend-dot green-dot" />Correct</span><span className="breakdown-count"><strong>{correct}</strong><small>questions</small></span></div>
            <div className="breakdown-item"><span className="breakdown-label"><i className="legend-dot red-dot" />Incorrect</span><span className="breakdown-count"><strong>{incorrect}</strong><small>questions</small></span></div>
            <div className="breakdown-item"><span className="breakdown-label"><i className="legend-dot unanswered-dot" />Unanswered</span><span className="breakdown-count"><strong>{unanswered}</strong><small>questions</small></span></div>
          </div>
        </div>
      </section></div>
    <section className="panel answer-review-panel"><div className="panel-heading"><div><h2>Review your answers</h2><p>Revisit the explanation for each question in this set</p></div></div><div className="answer-review-list">{attemptQuestions.map((question, index) => { const response = result.responses[question.id]; const wasCorrect = response === question.answer; return <article className="answer-review-item" key={question.id}><div className="answer-review-heading"><span>Q{index + 1} · {question.topic}</span><strong className={wasCorrect ? "review-correct" : response === undefined ? "review-skipped" : "review-incorrect"}>{wasCorrect ? "Correct" : response === undefined ? "Unanswered" : "Incorrect"}</strong></div><p>{question.prompt}</p><small>{response === undefined ? "No answer selected" : `Your answer: ${question.options[response]}`} · Correct answer: {question.options[question.answer]}</small><div className="answer-review-explanation">{question.explanation}</div></article>; })}</div></section>
    <div className="action-card"><div><h2>Ready to practise again?</h2><p>Your next attempt will draw a fresh question set from the preview bank.</p></div><Link to="/aptitude" className="button button-primary">Choose another assessment <ArrowRight size={16} /></Link></div>
    <p className="simulation-note"><ShieldCheck size={15} /> This is a local preview using sample questions. It is not a prediction of placement or hiring outcomes.</p>
  </>;
}

function PracticePage() {
  const [storedSession] = useState(loadPreviewPracticeSession);
  const [topic, setTopic] = useState(storedSession?.topic ?? "All topics");
  const [difficulty, setDifficulty] = useState(storedSession?.difficulty ?? "All levels");
  const [questionLimit, setQuestionLimit] = useState(storedSession?.questionLimit ?? 10);
  const questionsById = new Map(questions.map((item) => [item.id, item]));
  const [questionSet, setQuestionSet] = useState<AssessmentQuestion[]>(() => storedSession
    ? storedSession.questionIds
      .map((questionId) => questionsById.get(questionId))
      .filter((item): item is AssessmentQuestion => item !== undefined)
    : []);
  const [activeIndex, setActiveIndex] = useState(storedSession?.activeIndex ?? 0);
  const [choice, setChoice] = useState<number | null>(storedSession?.choice ?? null);
  const [checked, setChecked] = useState(storedSession?.checked ?? false);
  const [bookmarked, setBookmarked] = useState<number[]>(storedSession?.bookmarked ?? []);
  const [finished, setFinished] = useState(storedSession?.finished ?? false);
  const [timedOut, setTimedOut] = useState(storedSession?.timedOut ?? false);
  const [deadlineAt, setDeadlineAt] = useState<number | null>(storedSession?.deadlineAt ?? null);
  const [clockNow, setClockNow] = useState(Date.now);
  const availableQuestions = questions.filter((item) => (topic === "All topics" || item.topic === topic) && (difficulty === "All levels" || item.difficulty === difficulty));
  const question = finished ? undefined : questionSet[activeIndex];
  const remainingSeconds = deadlineAt === null ? null : getSecondsRemaining(deadlineAt, clockNow);
  const questionsPractised = finished && !timedOut
    ? questionSet.length
    : Math.min(activeIndex + (checked ? 1 : 0), questionSet.length);
  const progressPercent = questionSet.length === 0
    ? 0
    : Math.min(100, (questionsPractised / questionSet.length) * 100);
  const formattedTime = remainingSeconds === null
    ? ""
    : `${String(Math.floor(remainingSeconds / 60)).padStart(2, "0")}:${String(remainingSeconds % 60).padStart(2, "0")}`;

  useEffect(() => {
    if (deadlineAt === null || finished) return;
    const syncClock = () => setClockNow(Date.now());
    const timer = window.setInterval(syncClock, 1000);
    window.addEventListener("focus", syncClock);
    document.addEventListener("visibilitychange", syncClock);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", syncClock);
      document.removeEventListener("visibilitychange", syncClock);
    };
  }, [deadlineAt, finished]);

  useEffect(() => {
    if (deadlineAt !== null && !finished && remainingSeconds === 0) {
      setTimedOut(true);
      setFinished(true);
    }
  }, [deadlineAt, finished, remainingSeconds]);

  useEffect(() => {
    if (deadlineAt === null || questionSet.length === 0) return;
    const session: PreviewPracticeSession = {
      questionIds: questionSet.map((item) => item.id),
      topic,
      difficulty,
      questionLimit,
      activeIndex,
      choice,
      checked,
      bookmarked,
      deadlineAt,
      finished,
      timedOut,
    };
    savePreviewPracticeSession(session);
  }, [activeIndex, bookmarked, checked, choice, deadlineAt, difficulty, finished, questionLimit, questionSet, timedOut, topic]);

  const next = () => {
    if (activeIndex + 1 >= questionSet.length) setFinished(true);
    else setActiveIndex((value) => value + 1);
    setChoice(null);
    setChecked(false);
  };
  const startPractice = () => {
    const selectedQuestions = sampleNewQuestionSet("practice", availableQuestions, questionLimit);
    setQuestionSet(selectedQuestions);
    const startedAt = Date.now();
    setDeadlineAt(startedAt + selectedQuestions.length * 60 * 1000);
    setClockNow(startedAt);
    setActiveIndex(0);
    setChecked(false);
    setChoice(null);
    setFinished(false);
    setTimedOut(false);
  };
  return <>
    <PageHeading eyebrow="PRACTISE WITH PURPOSE" title="Practice zone" description="Choose a topic, practise against the clock, and get feedback as you go." />
    <div className="practice-controls panel">
      <label>Topic<select value={topic} onChange={(event) => setTopic(event.target.value)}><option>All topics</option>{Array.from(new Set(questions.map((item) => item.topic))).map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option>All levels</option><option>Easy</option><option>Medium</option><option>Hard</option></select></label>
      <label>Questions<select value={questionLimit} onChange={(event) => setQuestionLimit(Number(event.target.value))}><option value={5}>5 questions</option><option value={10}>10 questions</option><option value={20}>20 questions</option></select></label>
      <button className="button button-primary" disabled={availableQuestions.length === 0} onClick={startPractice}>Start timed practice <ArrowRight size={16} /></button>
      <span className="practice-timing-note"><Clock3 size={14} /> 1 minute per question</span>
    </div>
    <div className="practice-layout">
      <section className="panel practice-question">
        {question ? <>
          <div className="practice-question-top">
            <span className="badge badge-blue">{question.topic}</span>
            <span className="badge badge-neutral">{question.difficulty}</span>
            <span className="practice-count">Question {activeIndex + 1} of {questionSet.length}</span>
            <span className={`practice-timer ${remainingSeconds !== null && remainingSeconds <= 60 ? "urgent" : ""}`} aria-label={`Time remaining ${formattedTime}`}><Clock3 size={15} /> {formattedTime}</span>
            <button aria-label={bookmarked.includes(question.id) ? "Remove bookmark" : "Bookmark question"} className={`bookmark-button ${bookmarked.includes(question.id) ? "bookmarked" : ""}`} onClick={() => setBookmarked((items) => items.includes(question.id) ? items.filter((id) => id !== question.id) : [...items, question.id])}><Bookmark size={18} /></button>
          </div>
          <h2>{question.prompt}</h2>
          <div className="answer-options practice-options">
            {question.options.map((option, index) => <button key={option} className={`answer-option ${choice === index ? "selected" : ""} ${checked && index === question.answer ? "correct-option" : ""} ${checked && choice === index && index !== question.answer ? "incorrect-option" : ""}`} onClick={() => { if (!checked) setChoice(index); }}><span className="option-key">{String.fromCharCode(65 + index)}</span><span>{option}</span>{checked && index === question.answer && <Check size={17} className="option-check" />}</button>)}
          </div>
          {checked && <div className={`answer-feedback ${choice === question.answer ? "feedback-correct" : "feedback-incorrect"}`}><strong>{choice === question.answer ? "That’s right!" : "Not quite. Let’s learn from it."}</strong><p>{question.explanation}</p></div>}
          <div className="practice-actions">{!checked ? <button className="button button-primary" disabled={choice === null} onClick={() => setChecked(true)}>Check answer <Check size={16} /></button> : <button className="button button-primary" onClick={next}>{activeIndex === questionSet.length - 1 ? "Finish practice set" : "Next question"} <ArrowRight size={16} /></button>}</div>
        </> : finished ? <div className="empty-state"><Trophy size={22} /><strong>{timedOut ? "Time’s up" : "Practice set complete"}</strong><span>{timedOut ? `Your timed preview ended after ${Math.max(0, Math.min(activeIndex + (checked ? 1 : 0), questionSet.length))} of ${questionSet.length} questions.` : `You’ve finished all ${questionSet.length} questions in this preview set.`}</span><button className="button button-outline" onClick={startPractice}>Try a fresh set</button></div> : availableQuestions.length === 0 ? <div className="empty-state"><CircleHelp size={22} /><strong>No preview questions for this combination</strong><span>Try another topic or difficulty.</span></div> : <div className="empty-state"><BookOpenCheck size={22} /><strong>Ready for a fresh practice set?</strong><span>Choose your topic and difficulty, then start a new timed set of questions.</span></div>}
      </section>
      <aside className="practice-side">
        <div className="panel practice-progress-card"><span className="mini-kicker">TODAY’S PRACTICE</span><h3>You’re building a habit</h3><div className="practice-progress-stat"><strong>{questionsPractised}</strong><span>of {questionSet.length} questions practised</span></div><div className="progress-track"><div className="progress-fill" style={{ width: `${progressPercent}%` }} /></div><p>Each question is a step closer to your goal.</p></div>
        <div className="panel practice-tip"><span className="tip-icon"><Lightbulb size={17} /></span><strong>Practice tip</strong><p>Focus on understanding why an answer is correct. Speed comes naturally as your concepts get stronger.</p></div>
        <button className="retry-link" onClick={startPractice}><RotateCcw size={15} /> Start a fresh question set</button>
      </aside>
    </div>
  </>;
}

function PerformancePage() {
  return <>
    <PageHeading eyebrow="YOUR PROGRESS, MADE CLEAR" title="My performance" description="See the patterns in your practice and celebrate the progress you’re making." action={<span className="plan-duration"><Clock3 size={15} /> Last 30 days</span>} />
    <div className="metric-grid performance-metrics"><MetricCard icon={<Gauge size={18} />} label="Readiness score" value="68 / 100" note="+12 points overall" tone="blue" /><MetricCard icon={<Target size={18} />} label="Average accuracy" value="76%" note="+7% since last month" tone="green" /><MetricCard icon={<Clock3 size={18} />} label="Time per question" value="52 sec" note="8 sec faster" tone="purple" /><MetricCard icon={<Trophy size={18} />} label="Assessments" value="8" note="2 this month" tone="amber" /></div>
    <section className="panel performance-trend-panel"><div className="panel-heading"><div><h2>Readiness and accuracy trend</h2><p>Progress across your last 5 assessments</p></div></div><div className="chart-legend"><span><i className="legend-dot blue-dot" /> Readiness</span><span><i className="legend-dot green-dot" /> Accuracy</span></div><div className="performance-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={performanceTrend} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}><CartesianGrid stroke="#edf1f5" vertical={false} /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: "#8792a0", fontSize: 12 }} dy={10} /><YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fill: "#8792a0", fontSize: 12 }} /><Tooltip /><Area type="monotone" dataKey="score" name="Readiness" stroke="#1a8fc4" strokeWidth={2.5} fill="#e7f4fa" /><Area type="monotone" dataKey="accuracy" name="Accuracy" stroke="#52b788" strokeWidth={2} fill="transparent" /></AreaChart></ResponsiveContainer></div></section>
    <div className="content-grid performance-bottom"><section className="panel"><div className="panel-heading"><div><h2>Topic strengths and focus areas</h2><p>Use your next practice session where it counts</p></div></div>{sectionScores.map((section) => <div className="performance-topic" key={section.name}><div><strong>{section.name}</strong><span>{section.score >= 75 ? "Strength" : section.score >= 65 ? "Building" : "Focus area"}</span></div><div className="progress-track"><div className="progress-fill" style={{ width: `${section.score}%`, background: section.color }} /></div><strong>{section.score}%</strong></div>)}</section><section className="panel readiness-method"><span className="metric-icon blue"><ShieldCheck size={18} /></span><h2>How readiness is measured</h2><p>Your readiness score reflects assessed performance across aptitude sections. It is a learning indicator—not a prediction of selection or placement.</p><div className="method-row"><span>Quantitative &amp; reasoning</span><strong>50%</strong></div><div className="method-row"><span>Verbal &amp; interpretation</span><strong>35%</strong></div><div className="method-row"><span>Problem solving</span><strong>15%</strong></div><small>Weights are preview values and are configurable by assessment policy.</small></section></div>
  </>;
}

function CompaniesPage() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const visibleCompanies = companies.filter((company) => company.name.toLowerCase().includes(query.toLowerCase()) || company.category.toLowerCase().includes(query.toLowerCase()));
  return <>
    <PageHeading eyebrow="PREPARE WITH CONTEXT" title="Company mock tests" description="Practise skills often used in hiring assessments. Every test here is a MentorMuni practice simulation—not an official company test." />
    <div className="callout callout-amber"><span className="callout-icon"><CircleHelp size={18} /></span><span><strong>Hiring processes can change.</strong><small>These practice simulations are informed by public sources. Always check the employer’s current recruitment information.</small></span></div>
    <div className="company-toolbar"><div><h2>Explore company practice</h2><p>Choose an area to prepare for your next opportunity.</p></div><label className="search-field"><Search size={16} /><input aria-label="Search companies" placeholder="Search companies" value={query} onChange={(event) => setQuery(event.target.value)} /></label></div>
    <div className="company-grid">{visibleCompanies.map((company) => <article className="company-card" key={company.name}><div className="company-card-top"><span className={`company-logo ${company.color}`}>{company.name.slice(0, 1)}</span><span className="badge badge-neutral">Practice simulation</span></div><h3>{company.name}</h3><p>{company.category}</p><div className="company-detail"><span><FileQuestion size={15} /> {company.tests} practice tests</span><span><Clock3 size={15} /> 30–60 min</span></div><div className="company-card-footer"><span>Reviewed Nov 2026</span><button className="text-link" onClick={() => navigate("/exam/company")}>Try a mock <ArrowRight size={14} /></button></div></article>)}</div>
    {visibleCompanies.length === 0 && <div className="empty-state"><Search size={22} /><strong>No matching companies</strong><span>Try another company or category.</span></div>}
    <section className="panel company-source-panel"><span className="source-icon"><ShieldCheck size={18} /></span><div><strong>Transparent preparation, always.</strong><p>Company details should include public source references and review dates before assessments are published. Simulations never imply affiliation or guarantee hiring outcomes.</p></div></section>
  </>;
}

function RecommendationsPage() {
  return <>
    <PageHeading eyebrow="YOUR PERSONALIZED PLAN" title="A clear next step" description="Small, focused practice sessions help turn insights into progress." action={<span className="plan-duration"><Clock3 size={15} /> 7-day plan</span>} />
    <div className="recommendation-summary"><span className="summary-icon"><Sparkles size={19} /></span><div><strong>Built around your recent assessment</strong><p>Prioritized by topic accuracy, time spent, and the skills that can help you make progress next.</p></div><span className="summary-tag">PREVIEW</span></div>
    <div className="plan-layout"><div className="plan-days">{["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].map((day, index) => <article className={`plan-day ${index === 3 ? "today" : ""}`} key={day}><div className="day-label"><span>DAY {index + 1}</span><strong>{day}</strong></div><div className="day-content"><span className={`day-icon day-${index % 3}`}>{index === 2 ? <Target size={17} /> : index === 5 ? <Trophy size={17} /> : <BookOpenCheck size={17} />}</span><div><strong>{recommendations[index % recommendations.length].title}</strong><p>{recommendations[index % recommendations.length].detail}</p><small><Clock3 size={13} /> {recommendations[index % recommendations.length].meta.split("·")[1]?.trim() || "15 min"}</small></div></div><Link to="/practice" className="day-action">{index < 3 ? "Start session" : "View session"} <ArrowRight size={14} /></Link></article>)}</div><aside className="plan-sidebar"><div className="panel plan-progress"><span className="mini-kicker">THIS WEEK</span><div className="weekly-score"><strong>2</strong><span>of 7 sessions</span></div><div className="week-dots">{["M", "T", "W", "T", "F", "S", "S"].map((day, index) => <span className={index < 2 ? "done" : ""} key={`${day}-${index}`}>{index < 2 ? <Check size={13} /> : day}</span>)}</div><p>A short practice session keeps your momentum going.</p><Link to="/practice" className="button button-primary full-button">Practise now <ArrowRight size={15} /></Link></div><div className="panel plan-principle"><Lightbulb size={18} /><strong>Measure. Improve. Prove.</strong><p>Revisit your assessment after a week to see the progress your practice is making.</p></div></aside></div>
  </>;
}

export function QuestionBankPage() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("All statuses");
  const [category, setCategory] = useState("All categories");
  const [difficulty, setDifficulty] = useState("All difficulties");
  const [showNew, setShowNew] = useState(false);
  const [drafts, setDrafts] = useState<Array<{ id: string; prompt: string; category: string; difficulty: string; status: string; answer: string; explanation: string }>>([]);
  const [draft, setDraft] = useState({ prompt: "", category: "Quantitative", difficulty: "Medium", answer: "", explanation: "" });
  const rows = [
    { id: "Q-1024", prompt: "Percentage increase and decrease", category: "Quantitative", difficulty: "Easy", status: "Published" },
    { id: "Q-1023", prompt: "Linear seating arrangement", category: "Logical reasoning", difficulty: "Medium", status: "Review" },
    { id: "Q-1022", prompt: "Reading comprehension: renewable energy", category: "Verbal ability", difficulty: "Medium", status: "Published" },
    { id: "Q-1021", prompt: "Interpret the quarterly sales table", category: "Data interpretation", difficulty: "Hard", status: "Draft" },
  ];
  const allRows = [...rows, ...drafts];
  const filtered = allRows.filter((row) => row.prompt.toLowerCase().includes(query.toLowerCase())
    && (status === "All statuses" || row.status === status)
    && (category === "All categories" || row.category === category)
    && (difficulty === "All difficulties" || row.difficulty === difficulty));
  const counts = {
    total: allRows.length,
    published: allRows.filter((row) => row.status === "Published").length,
    review: allRows.filter((row) => row.status === "Review").length,
    draft: allRows.filter((row) => row.status === "Draft").length,
  };
  const createDraft = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextId = `Q-${1025 + drafts.length}`;
    setDrafts((current) => [...current, {
      id: nextId,
      prompt: draft.prompt.trim(),
      category: draft.category,
      difficulty: draft.difficulty,
      status: "Draft",
      answer: draft.answer.trim(),
      explanation: draft.explanation.trim(),
    }]);
    setDraft({ prompt: "", category: "Quantitative", difficulty: "Medium", answer: "", explanation: "" });
    setShowNew(false);
  };
  return <>
    <PageHeading eyebrow="ADMIN WORKSPACE · PREVIEW" title="Question bank" description="Manage, review, and version verified questions for assessments and practice." action={<button className="button button-primary" onClick={() => setShowNew(true)}><span>+</span> Create question</button>} />
    <div className="admin-stats"><div><span>Sample questions</span><strong>{counts.total}</strong></div><div><span>Published</span><strong>{counts.published}</strong></div><div><span>In review</span><strong className="text-amber">{counts.review}</strong></div><div><span>Drafts</span><strong>{counts.draft}</strong></div></div>
    <section className="panel question-bank-panel"><div className="bank-toolbar"><label className="search-field"><Search size={16} /><input aria-label="Search question bank" placeholder="Search questions…" value={query} onChange={(event) => setQuery(event.target.value)} /></label><select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}><option>All statuses</option><option>Published</option><option>Review</option><option>Draft</option></select><select aria-label="Filter by category" value={category} onChange={(event) => setCategory(event.target.value)}><option>All categories</option>{Array.from(new Set(allRows.map((row) => row.category))).map((item) => <option key={item}>{item}</option>)}</select><select aria-label="Filter by difficulty" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option>All difficulties</option><option>Easy</option><option>Medium</option><option>Hard</option></select></div><div className="table-scroll"><table><thead><tr><th>QUESTION</th><th>CATEGORY</th><th>DIFFICULTY</th><th>STATUS</th></tr></thead><tbody>{filtered.map((row) => <tr key={row.id}><td><span className="question-id">{row.id}</span><strong>{row.prompt}</strong></td><td>{row.category}</td><td><span className="difficulty-dot" />{row.difficulty}</td><td><span className={`status-pill status-${row.status.toLowerCase()}`}>{row.status}</span></td></tr>)}</tbody></table>{filtered.length === 0 && <div className="empty-state"><Search size={22} /><strong>No matching questions</strong><span>Try a different search or filter.</span></div>}</div><div className="table-footer"><span>Showing {filtered.length} sample questions</span><div><span className="current-page">Preview</span></div></div></section>
    {showNew && <div className="modal-backdrop" role="presentation"><form className="confirm-modal question-form" role="dialog" aria-modal="true" aria-labelledby="new-question-title" onSubmit={createDraft}><button type="button" className="modal-close" aria-label="Close" onClick={() => setShowNew(false)}><X size={19} /></button><span className="modal-symbol"><FileQuestion size={21} /></span><h2 id="new-question-title">Create a question draft</h2><p>New questions are kept as drafts and cannot enter assessments until reviewed and verified.</p><label>Question text<textarea required rows={3} value={draft.prompt} onChange={(event) => setDraft((current) => ({ ...current, prompt: event.target.value }))} /></label><div className="question-form-row"><label>Category<select value={draft.category} onChange={(event) => setDraft((current) => ({ ...current, category: event.target.value }))}><option>Quantitative</option><option>Logical reasoning</option><option>Verbal ability</option><option>Data interpretation</option></select></label><label>Difficulty<select value={draft.difficulty} onChange={(event) => setDraft((current) => ({ ...current, difficulty: event.target.value }))}><option>Easy</option><option>Medium</option><option>Hard</option></select></label></div><label>Verified answer<input required value={draft.answer} onChange={(event) => setDraft((current) => ({ ...current, answer: event.target.value }))} /></label><label>Explanation<textarea required rows={2} value={draft.explanation} onChange={(event) => setDraft((current) => ({ ...current, explanation: event.target.value }))} /></label><div className="modal-actions"><button type="button" className="button button-outline" onClick={() => setShowNew(false)}>Cancel</button><button type="submit" className="button button-primary">Save draft <Check size={15} /></button></div></form></div>}
  </>;
}

function NotFound() {
  return <div className="not-found"><span className="not-found-icon"><CircleHelp size={22} /></span><h1>We can’t find that page</h1><p>It may have moved, or the link may be incorrect.</p><Link to="/" className="button button-primary">Back to dashboard <ArrowRight size={15} /></Link></div>;
}

export default App;
