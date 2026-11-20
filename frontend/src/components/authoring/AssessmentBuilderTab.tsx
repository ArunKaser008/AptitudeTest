import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus, Send, Settings2, X } from "lucide-react";
import {
  cloneAuthoringAssessment,
  createAuthoringAssessment,
  listAuthoringAssessments,
  listAuthoringQuestions,
  publishAuthoringAssessment,
  updateAuthoringAssessmentConfig,
  updateAuthoringSectionPool,
  type AssessmentConfigDraft,
  type AssessmentSectionDraft,
  type AuthoringAssessment,
  type AuthoringSection,
} from "../../services/authoringApi";

const blankSection = (): AssessmentSectionDraft => ({
  section_key: "quantitative",
  title: "Quantitative",
  position: 0,
  question_count: 10,
  marks_per_question: 1,
  negative_marks: 0,
  question_version_ids: [],
});

function configFor(assessment?: AuthoringAssessment): AssessmentConfigDraft {
  return {
    duration_seconds: assessment?.duration_seconds ?? 600,
    show_explanations_after_submission: assessment?.show_explanations_after_submission ?? true,
    randomize_questions: assessment?.randomize_questions ?? true,
    randomize_options: assessment?.randomize_options ?? true,
    scoring_policy: assessment?.scoring_policy ?? { minimum_score_zero: true },
    sections: assessment?.sections.map((section) => ({
      section_key: section.section_key,
      title: section.title,
      position: section.position,
      question_count: section.question_count,
      marks_per_question: section.marks_per_question,
      negative_marks: section.negative_marks,
      question_version_ids: section.question_version_ids,
    })) ?? [blankSection()],
  };
}

function PoolPicker({ section, onClose, onSaved }: {
  section: AuthoringSection;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [selectedIds, setSelectedIds] = useState(section.question_version_ids);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const questionsQuery = useQuery({
    queryKey: ["authoring-pool-picker"],
    queryFn: () => listAuthoringQuestions({ status: "published", verified: true, pageSize: 100 }),
  });
  const toggle = (id: string) => {
    setSelectedIds((ids) => ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]);
  };
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await updateAuthoringSectionPool(section.id, selectedIds);
      await queryClient.invalidateQueries({ queryKey: ["authoring-assessments"] });
      onSaved();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The question pool could not be updated.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="authoring-modal-backdrop" role="presentation">
      <section className="authoring-dialog pool-picker" role="dialog" aria-modal="true" aria-labelledby="pool-picker-title">
        <div className="authoring-editor-header"><div><span className="section-kicker">SECTION QUESTION POOL</span><h2 id="pool-picker-title">{section.title}</h2></div><button className="icon-button" aria-label="Close pool picker" onClick={onClose}><X size={18} /></button></div>
        <p>Choose verified, published questions. {selectedIds.length} selected for {section.question_count} required.</p>
        {questionsQuery.isLoading && <div role="status">Loading verified questions…</div>}
        {questionsQuery.isError && <p className="assessment-inline-error" role="alert">{questionsQuery.error.message}</p>}
        <div className="pool-question-list">
          {(questionsQuery.data?.items ?? []).map((question) => (
            <label className="pool-question-option" key={question.id}>
              <input type="checkbox" checked={selectedIds.includes(question.id)} onChange={() => toggle(question.id)} />
              <span><strong>{question.topic} · {question.difficulty}</strong><small>{question.prompt}</small></span>
            </label>
          ))}
          {questionsQuery.data?.items.length === 0 && <p>No verified published questions are available in the bank.</p>}
        </div>
        {error && <p className="assessment-inline-error" role="alert">{error}</p>}
        <div className="authoring-form-actions"><button className="button button-outline" onClick={onClose}>Cancel</button><button className="button button-primary" disabled={busy || questionsQuery.isLoading} onClick={() => void save()}>{busy ? "Saving pool…" : "Save question pool"}</button></div>
      </section>
    </div>
  );
}

function AssessmentConfigEditor({ assessment, onClose }: {
  assessment?: AuthoringAssessment;
  onClose: () => void;
}) {
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<"aptitude" | "company_mock" | "practice">(assessment?.category ?? "aptitude");
  const [targetRole, setTargetRole] = useState(assessment?.target_role ?? "");
  const [aiGenerationEnabled, setAiGenerationEnabled] = useState(assessment ? true : true);
  const [blueprintTopics, setBlueprintTopics] = useState("");
  const [config, setConfig] = useState(() => configFor(assessment));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const updateConfig = <K extends keyof AssessmentConfigDraft>(key: K, value: AssessmentConfigDraft[K]) => {
    setConfig((current) => ({ ...current, [key]: value }));
  };
  const updateSection = (index: number, patch: Partial<AssessmentSectionDraft>) => {
    setConfig((current) => ({
      ...current,
      sections: current.sections.map((section, sectionIndex) => sectionIndex === index
        ? { ...section, ...patch }
        : section),
    }));
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (assessment) {
        await updateAuthoringAssessmentConfig(assessment.id, config);
      } else {
        await createAuthoringAssessment({
          slug: slug.trim(),
          title: title.trim(),
          description: description.trim(),
          category,
          target_role: targetRole.trim() || null,
          ai_generation_enabled: aiGenerationEnabled,
          blueprint_topics: blueprintTopics.split(",").map((topic) => topic.trim()).filter(Boolean),
          ...config,
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["authoring-assessments"] });
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The assessment could not be saved.");
    } finally {
      setBusy(false);
    }
  };
  const close = () => {
    if (window.confirm("Discard unsaved assessment changes?")) onClose();
  };
  return (
    <div className="authoring-modal-backdrop" role="presentation">
      <section className="authoring-dialog assessment-config-editor" role="dialog" aria-modal="true" aria-labelledby="assessment-editor-title">
        <div className="authoring-editor-header"><div><span className="section-kicker">ASSESSMENT BUILDER</span><h2 id="assessment-editor-title">{assessment ? `Configure ${assessment.title}` : "Create assessment"}</h2></div><button className="icon-button" aria-label="Close assessment editor" onClick={close}><X size={18} /></button></div>
        <form className="authoring-form" onSubmit={(event) => void save(event)}>
          {!assessment && <div className="authoring-two-fields">
            <label>Slug<input required minLength={1} maxLength={100} value={slug} onChange={(event) => setSlug(event.target.value)} /></label>
            <label>Title<input required minLength={1} maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
            <label>Category<select value={category} onChange={(event) => setCategory(event.target.value as typeof category)}><option value="aptitude">Aptitude</option><option value="company_mock">Company mock</option><option value="practice">Practice</option></select></label>
            <label>Target role<input maxLength={150} value={targetRole} onChange={(event) => setTargetRole(event.target.value)} placeholder="IT Services, SDE / Product, Analytics…" /></label>
            <label className="authoring-full-field">Description<input value={description} onChange={(event) => setDescription(event.target.value)} /></label>
            <label className="authoring-full-field">Blueprint topics (comma-separated)<input value={blueprintTopics} onChange={(event) => setBlueprintTopics(event.target.value)} placeholder="Applied Quantitative, Data Interpretation" /></label>
            <label className="authoring-full-field"><input type="checkbox" checked={aiGenerationEnabled} onChange={(event) => setAiGenerationEnabled(event.target.checked)} /> Generate fresh AI questions when the pool needs more unique items</label>
          </div>}
          <label>Duration (seconds)<input type="number" min="1" max="86400" required value={config.duration_seconds} onChange={(event) => updateConfig("duration_seconds", Number(event.target.value))} /></label>
          <div className="authoring-toggle-row">
            <label><input type="checkbox" checked={config.randomize_questions} onChange={(event) => updateConfig("randomize_questions", event.target.checked)} /> Randomize question order</label>
            <label><input type="checkbox" checked={config.randomize_options} onChange={(event) => updateConfig("randomize_options", event.target.checked)} /> Randomize options</label>
            <label><input type="checkbox" checked={config.show_explanations_after_submission} onChange={(event) => updateConfig("show_explanations_after_submission", event.target.checked)} /> Release explanations after submission</label>
          </div>
          <div className="authoring-section-list">
            <div className="authoring-toolbar"><div><h3>Ordered sections</h3><p>Each section must have enough verified published questions in its pool.</p></div><button type="button" className="button button-outline" onClick={() => updateConfig("sections", [...config.sections, { ...blankSection(), section_key: `section-${config.sections.length + 1}`, title: `Section ${config.sections.length + 1}`, position: config.sections.length }])}><Plus size={14} /> Add section</button></div>
            {config.sections.map((section, index) => (
              <div className="authoring-section-fields" key={`${section.section_key}-${index}`}>
                <label>Section key<input required value={section.section_key} onChange={(event) => updateSection(index, { section_key: event.target.value })} /></label>
                <label>Title<input required value={section.title} onChange={(event) => updateSection(index, { title: event.target.value })} /></label>
                <label>Order<input type="number" min="0" value={section.position} onChange={(event) => updateSection(index, { position: Number(event.target.value) })} /></label>
                <label>Questions<input type="number" min="1" value={section.question_count} onChange={(event) => updateSection(index, { question_count: Number(event.target.value) })} /></label>
                <label>Marks each<input type="number" min="0" step="0.25" value={section.marks_per_question} onChange={(event) => updateSection(index, { marks_per_question: Number(event.target.value) })} /></label>
                <label>Negative<input type="number" min="0" step="0.25" value={section.negative_marks} onChange={(event) => updateSection(index, { negative_marks: Number(event.target.value) })} /></label>
                {config.sections.length > 1 && <button type="button" className="clear-button" onClick={() => updateConfig("sections", config.sections.filter((_, itemIndex) => itemIndex !== index))}>Remove section</button>}
              </div>
            ))}
          </div>
          {assessment?.config_status === "published" && <p className="authoring-help">Saving creates a new draft configuration version. The currently published version remains pinned for existing attempts.</p>}
          {error && <p className="assessment-inline-error" role="alert">{error}</p>}
          <div className="authoring-form-actions"><button type="button" className="button button-outline" onClick={close}>Cancel</button><button className="button button-primary" disabled={busy || !config.sections.length}>{busy ? "Saving…" : "Save draft configuration"}</button></div>
        </form>
      </section>
    </div>
  );
}

function CloneAssessmentDialog({ assessment, onClose }: { assessment: AuthoringAssessment; onClose: () => void }) {
  const [slug, setSlug] = useState(`${assessment.slug}-copy`);
  const [title, setTitle] = useState(`${assessment.title} copy`);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const queryClient = useQueryClient();
  const clone = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await cloneAuthoringAssessment(assessment.id, slug.trim(), title.trim());
      await queryClient.invalidateQueries({ queryKey: ["authoring-assessments"] });
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The assessment could not be cloned.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="authoring-modal-backdrop" role="presentation">
      <form className="authoring-dialog authoring-form" role="dialog" aria-modal="true" aria-labelledby="clone-assessment-title" onSubmit={(event) => void clone(event)}>
        <div className="authoring-editor-header"><h2 id="clone-assessment-title">Clone assessment</h2><button type="button" className="icon-button" aria-label="Close clone dialog" onClick={onClose}><X size={18} /></button></div>
        <label>New slug<input required value={slug} onChange={(event) => setSlug(event.target.value)} /></label>
        <label>New title<input required value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <p className="authoring-help">The clone will be a new draft with copied sections and question pool links.</p>
        {error && <p className="assessment-inline-error" role="alert">{error}</p>}
        <div className="authoring-form-actions"><button type="button" className="button button-outline" onClick={onClose}>Cancel</button><button className="button button-primary" disabled={busy}>{busy ? "Cloning…" : "Clone as draft"}</button></div>
      </form>
    </div>
  );
}

export function AssessmentBuilderTab() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AuthoringAssessment | null | undefined>(undefined);
  const [cloning, setCloning] = useState<AuthoringAssessment | null>(null);
  const [poolSection, setPoolSection] = useState<AuthoringSection | null>(null);
  const [busyAssessmentId, setBusyAssessmentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const assessmentsQuery = useQuery({
    queryKey: ["authoring-assessments"],
    queryFn: listAuthoringAssessments,
  });

  const publish = async (assessment: AuthoringAssessment) => {
    setBusyAssessmentId(assessment.id);
    setError(null);
    try {
      await publishAuthoringAssessment(assessment.id);
      await queryClient.invalidateQueries({ queryKey: ["authoring-assessments"] });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Assessment publish failed.");
    } finally {
      setBusyAssessmentId(null);
    }
  };

  return (
    <section className="authoring-workspace">
      <div className="authoring-toolbar">
        <div><h2>Assessments &amp; pools</h2><p>Build versioned configurations and verify section readiness before publishing.</p></div>
        <button className="button button-primary" onClick={() => setEditing(null)}><Plus size={15} /> New assessment</button>
      </div>
      {error && <p className="assessment-inline-error" role="alert">{error}</p>}
      {assessmentsQuery.isLoading && <div className="panel assessment-state" role="status">Loading assessments…</div>}
      {assessmentsQuery.isError && <div className="panel assessment-state error-state" role="alert"><strong>Assessment list unavailable</strong><span>{assessmentsQuery.error.message}</span><button className="button button-outline" onClick={() => void assessmentsQuery.refetch()}>Try again</button></div>}
      {assessmentsQuery.data?.length === 0 && <div className="panel empty-assessments"><h3>No assessments configured</h3><p>Create a draft, add a verified question pool, then publish it for candidate delivery.</p></div>}
      <div className="assessment-builder-list">
        {assessmentsQuery.data?.map((assessment) => (
          <article className="panel assessment-builder-card" key={assessment.id}>
            <div className="assessment-builder-heading">
              <div><span className={`authoring-status-badge ${assessment.status}`}>{assessment.status}</span><h3>{assessment.title}</h3><p>{assessment.slug} · {assessment.duration_seconds ? Math.ceil(assessment.duration_seconds / 60) : "No"} min · config v{assessment.config_version_number ?? "—"} ({assessment.config_status ?? "none"})</p></div>
              <div className="assessment-builder-actions">
                <button className="button button-outline" onClick={() => setEditing(assessment)}><Settings2 size={14} /> Configure</button>
                <button className="icon-button" aria-label={`Clone ${assessment.title}`} onClick={() => setCloning(assessment)}><Copy size={15} /></button>
                <button className="button button-primary" disabled={!assessment.ready || assessment.config_status !== "draft" || busyAssessmentId === assessment.id} onClick={() => void publish(assessment)}><Send size={14} /> Publish</button>
              </div>
            </div>
            <div className="readiness-meter"><span>{assessment.eligible_verified_count} / {assessment.required_question_count} verified pool questions</span><div className="progress-track"><div className="progress-fill" style={{ width: `${assessment.required_question_count ? Math.min(100, 100 * assessment.eligible_verified_count / assessment.required_question_count) : 0}%` }} /></div><strong>{assessment.ready ? "Ready" : "Needs questions"}</strong></div>
            <div className="section-readiness-list">
              {assessment.sections.map((section) => (
                <div className="section-readiness-row" key={section.id}>
                  <span className={`readiness-indicator ${section.ready ? "ready" : ""}`}>{section.ready ? <Check size={13} /> : <span>!</span>}</span>
                  <span><strong>{section.position + 1}. {section.title}</strong><small>{section.eligible_verified_count} / {section.question_count} verified · {section.marks_per_question} marks · -{section.negative_marks}</small></span>
                  <button className="button button-outline" disabled={assessment.config_status !== "draft"} onClick={() => setPoolSection(section)}>Manage pool</button>
                </div>
              ))}
            </div>
            {!assessment.ready && <p className="authoring-help">Publishing is disabled until every section has at least its required number of verified, published questions.</p>}
          </article>
        ))}
      </div>
      {editing !== undefined && <AssessmentConfigEditor assessment={editing ?? undefined} onClose={() => setEditing(undefined)} />}
      {cloning && <CloneAssessmentDialog assessment={cloning} onClose={() => setCloning(null)} />}
      {poolSection && <PoolPicker section={poolSection} onClose={() => setPoolSection(null)} onSaved={() => void queryClient.invalidateQueries({ queryKey: ["authoring-assessments"] })} />}
    </section>
  );
}
