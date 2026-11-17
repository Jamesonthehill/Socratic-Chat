import { useState } from "react";
import { date, TOOLS } from "./api";

function openingFor(item) {
  const config = item.student_config || item.config || {};
  if (item.tool === "socratic") {
    const firstStep = config.learning_steps?.[0];
    return {
      label: firstStep ? `Step 1: ${firstStep.title}` : "Socratic tutor",
      scenario: firstStep?.scenario || "",
      question: firstStep?.question || config.prompt || "The tutor will open with a question based on the selected materials.",
    };
  }
  if (item.tool === "debate") return {
    label: "Debate scenario",
    scenario: config.scenario || "",
    question: config.opening_prompt || "What position would you take, and why?",
  };
  if (item.tool === "reflections") return {
    label: "Reflection prompt",
    scenario: "",
    question: config.milestone_prompt || config.sub_topics?.[0] || "Your reflection prompt will appear here.",
  };
  if (item.tool === "self-directed-learning") return {
    label: "Lesson focus",
    scenario: "",
    question: config.prompt || config.learning_plan?.title || "Your prepared lesson will appear here.",
  };
  return { label: "Activity instructions", scenario: "", question: config.prompt || item.instructions || "" };
}

export function StudentActivityPreview({ item, files = [] }) {
  const [started, setStarted] = useState(false);
  const config = item.student_config || item.config || {};
  const opening = openingFor(item);
  return (
    <section id="student-activity-preview" className="student-activity-preview" aria-label="Student-view preview">
      <p className="context">Student-view preview · read only</p>
      <h2>{item.title}</h2>
      <p className="help">This preview does not start a student attempt or generate an AI reply. Live tutor wording may vary.</p>
      <div className="student-preview-meta">
        <span>{TOOLS[item.tool]?.name || "Activity"}</span>
        <span>Due {date(item.due_at)}</span>
      </div>
      <div className="student-preview-layout">
        <aside className="student-preview-assignment">
          <h3>Your assignment</h3>
          <p>{item.instructions || "Your instructor has not added separate instructions."}</p>
          {files.length > 0 && <><h4>Course materials</h4><ul>{files.map(file => <li key={file.file_id}>{file.filename}</li>)}</ul></>}
          {config.learning_steps?.length > 0 && <>
            <h4>Your learning path</h4>
            <ol>{config.learning_steps.map((step, index) => <li key={`${step.title}-${index}`}>{step.title}</li>)}</ol>
          </>}
        </aside>
        <div className="student-preview-chat">
          <h3>{TOOLS[item.tool]?.name || "Activity"}</h3>
          {started ? <>
            <div className="student-preview-message">
              <strong>{opening.label}</strong>
              {opening.scenario && <p>{opening.scenario}</p>}
              <p>{opening.question}</p>
            </div>
            <label htmlFor="student-preview-reply">Your response</label>
            <textarea id="student-preview-reply" rows={3} disabled placeholder="Students write their response here" />
            <button type="button" className="secondary" onClick={() => setStarted(false)}>Reset preview</button>
          </> : <>
            <p>Ready when you are. Your professor’s settings are already loaded.</p>
            <button type="button" onClick={() => setStarted(true)}>Preview start</button>
          </>}
        </div>
      </div>
    </section>
  );
}
