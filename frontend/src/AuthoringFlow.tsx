import { useState } from "react";
import { BookOpenCheck, Layers3 } from "lucide-react";
import { PageHeading } from "./components/PageHeading";
import { AssessmentBuilderTab } from "./components/authoring/AssessmentBuilderTab";
import { QuestionBankTab } from "./components/authoring/QuestionBankTab";

type AuthoringTab = "questions" | "assessments";

export function AuthoringPage() {
  const [tab, setTab] = useState<AuthoringTab>("questions");
  return (
    <>
      <PageHeading
        eyebrow="ASSESSMENT OPERATIONS"
        title="Assessment studio"
        description="Manage verified question content, configure assessment pools, and publish reviewed assessments."
      />
      <div className="authoring-tabs" role="tablist" aria-label="Assessment studio sections">
        <button
          id="question-bank-tab"
          role="tab"
          aria-selected={tab === "questions"}
          aria-controls="question-bank-panel"
          className={tab === "questions" ? "active" : ""}
          onClick={() => setTab("questions")}
        >
          <BookOpenCheck size={16} /> Question bank
        </button>
        <button
          id="assessment-builder-tab"
          role="tab"
          aria-selected={tab === "assessments"}
          aria-controls="assessment-builder-panel"
          className={tab === "assessments" ? "active" : ""}
          onClick={() => setTab("assessments")}
        >
          <Layers3 size={16} /> Assessments &amp; pools
        </button>
      </div>
      {tab === "questions"
        ? <div id="question-bank-panel" role="tabpanel" aria-labelledby="question-bank-tab"><QuestionBankTab /></div>
        : <div id="assessment-builder-panel" role="tabpanel" aria-labelledby="assessment-builder-tab"><AssessmentBuilderTab /></div>}
      <p className="authoring-security-note">Authoring access controls are not yet enabled in this pre-authentication development release. Do not expose this workspace publicly.</p>
    </>
  );
}
