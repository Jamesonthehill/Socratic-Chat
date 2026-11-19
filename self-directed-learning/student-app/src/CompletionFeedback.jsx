import React from "react";

const categories = [
  ["well", "What You Did Well", "✓"],
  ["improve", "Areas for Improvement", "↗"],
  ["application", "Application & Critical Thinking", "◇"],
  ["next", "Recommended Next Steps", "→"],
];

export default function CompletionFeedback({ feedback }) {
  if (!feedback?.cards?.length) return null;
  return (
    <section className="sdl-completion-feedback" aria-label="Your learning feedback">
      <header>
        <p className="eyebrow">Lesson complete</p>
        <h3>Your learning feedback</h3>
        {feedback.source === "recorded_evidence" && <p className="help">This summary uses your saved responses. Detailed AI feedback is unavailable for this record.</p>}
      </header>
      <div className="sdl-feedback-cards">
        {categories.map(([key, title, icon]) => {
          const card = feedback.cards.find(item => item.key === key);
          if (!card) return null;
          return <article className={`sdl-learning-feedback sdl-learning-feedback-${key}`} key={key}>
            <h4><span aria-hidden="true">{icon}</span>{title}</h4>
            <p>{card.text}</p>
            {card.evidence?.length > 0 && <details>
              <summary>From your responses</summary>
              {card.evidence.map((item, index) => <blockquote key={`${item.id}-${index}`}>{item.quote}</blockquote>)}
            </details>}
          </article>;
        })}
      </div>
    </section>
  );
}
