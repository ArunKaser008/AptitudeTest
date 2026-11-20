import type { QuestionStimulus } from "../../services/assessmentApi";

export function StimulusBlock({ stimulus }: { stimulus: QuestionStimulus | null }) {
  if (!stimulus) return null;
  const title = stimulus.title && <h2 className="stimulus-title">{stimulus.title}</h2>;

  if (stimulus.kind === "table") {
    return (
      <figure className="question-stimulus">
        {title}
        <div className="stimulus-table-scroll">
          <table className="stimulus-table">
            <thead><tr>{stimulus.headers.map((header, index) => <th key={`${header}-${index}`}>{header}</th>)}</tr></thead>
            <tbody>
              {stimulus.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell === null ? "—" : typeof cell === "string" || typeof cell === "number" ? cell : JSON.stringify(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </figure>
    );
  }

  if (stimulus.kind === "code") {
    return (
      <figure className="question-stimulus">
        {title}
        <pre className="stimulus-code"><code className={`language-${stimulus.language}`}>{stimulus.content}</code></pre>
      </figure>
    );
  }

  return (
    <figure className="question-stimulus">
      {title}
      <div className="stimulus-passage">{stimulus.content}</div>
    </figure>
  );
}
