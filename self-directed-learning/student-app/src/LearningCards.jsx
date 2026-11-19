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

export function ActiveQuestion({ question, interview, idPrefix = "sdl-active" }) {
  return (
    <header className="sdl-active-question">
      <p className="eyebrow">
        {interview ? "Reasoning & reflection" : "Your next step"}
      </p>
      <h3 id={`${idPrefix}-question`}>{question.title || "Interview question"}</h3>
      <p id={`${idPrefix}-prompt`}>{question.prompt}</p>
      <small>A couple of sentences or bullets is enough.</small>
    </header>
  );
}
