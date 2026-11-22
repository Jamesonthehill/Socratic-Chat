import React from "react";
import { uniqueContent } from "./learning-presentation";

export function ActivityProgress({ state, sections = [] }) {
  const index = state.application_answers?.length || 0;
  const interview = state.stage === "interview";
  return (
    <nav className="sdl-activity-progress" aria-label="Application steps">
      <div>
        <strong>
          {interview ? "Explore your reasoning" : "Apply what you learned"}
        </strong>
        <span>
          {interview
            ? `Interview ${(state.interview_answers?.length || 0) + 1} of ${state.interview_count}`
            : `Part ${index + 1} of ${state.application_count}`}
        </span>
      </div>
      <ol>
        {sections.map((section, position) => (
          <li
            key={section.id}
            aria-current={!interview && position === index ? "step" : undefined}
            data-status={
              interview || position < index
                ? "complete"
                : position === index
                  ? "current"
                  : "upcoming"
            }
          >
            <span aria-hidden="true">
              {interview || position < index ? "✓" : position + 1}
            </span>
            {section.title}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function ScenarioCard({ task, activeQuestion }) {
  const paragraphs = uniqueContent([
    task.description,
    task.submission_prompt,
  ]).filter((text) => text !== activeQuestion?.prompt?.trim());
  if (!paragraphs.length) return null;
  return (
    <section
      className="sdl-scenario-card"
      aria-label="Application task scenario"
    >
      <p className="eyebrow">Scenario</p>
      <h3>{task.title || "Your learning challenge"}</h3>
      {paragraphs.map((text) => (
        <p key={text}>{text}</p>
      ))}
    </section>
  );
}

export function ActiveQuestion({ question, interview, number, idPrefix = "sdl-active" }) {
  return (
    <header className="sdl-active-question">
      <p className="eyebrow">
        {number ? `Question ${number} · ${interview ? "Interview" : "Application"}` : interview ? "Reasoning & reflection" : "Your next step"}
      </p>
      <h3 id={`${idPrefix}-question`}>{question.title || "Interview question"}</h3>
      <p id={`${idPrefix}-prompt`}>{question.prompt}</p>
      <small>A couple of sentences or bullets is enough.</small>
    </header>
  );
}

export function LessonProgress({ state, plan }) {
  const stage = state.stage === "paused" ? state.resume_stage : state.stage;
  const phases = [
    { label: "Study", stages: ["welcome", "study_resources"], count: 1 },
    { label: "Quiz", stages: ["diagnostic_quiz", "quiz_review"], count: state.quiz_count || plan.diagnostic_quiz?.length || 1, done: state.quiz_index || 0 },
    { label: "Application", stages: ["application"], count: state.application_count || plan.application_sections?.length || 1, done: state.application_answers?.length || 0 },
    ...(state.assessment_version === 2 ? [{ label: "Interview", stages: ["interview"], count: state.interview_count || 2, done: state.interview_answers?.length || 0 }] : []),
  ];
  const active = stage === "completed" ? phases.length : phases.findIndex(phase => phase.stages.includes(stage));
  return <nav className="sdl-phase-progress" aria-label="Learning stages">
    {phases.map((phase, index) => <div key={phase.label} aria-current={index === active ? "step" : undefined}>
      <strong>{phase.label}</strong>
      <div className="sdl-phase-segments" role="progressbar" aria-label={`${phase.label} progress`}
        aria-valuemin={0} aria-valuemax={phase.count} aria-valuenow={index < active ? phase.count : Math.min(phase.count, phase.done || 0)}>
        {Array.from({ length: phase.count }, (_, part) => <span key={part} data-status={index < active || part < (phase.done || 0) ? "complete" : index === active && part === (phase.done || 0) ? "current" : "upcoming"} />)}
      </div>
    </div>)}
  </nav>;
}
