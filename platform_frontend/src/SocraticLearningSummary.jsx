import Markdown from "react-markdown";
import LearningDifficultyChart from "./LearningDifficultyChart";

export function emphasizeFeedbackReason(text = "") {
  if (/\*\*[^*\n]+\*\*/.test(text)) return text;
  const reason = text.match(/\b(?:because|therefore|as a result|so that)\b[^.!?\n]*(?:[.!?]|$)/i)?.[0]
    || text.split(/(?<=[.!?])\s+|\n+/).find(part => /\b(?:must|needs? to|requires?|means)\b/i.test(part));
  return reason ? text.replace(reason, `**${reason}**`) : text;
}

export default function SocraticLearningSummary({ summary, messages = [], steps = [], metrics = {}, assignmentId, onUpdateFeedback, busy, onViewOriginal, canViewOriginal }) {
  if (!summary) return null;
  const firstTutor = messages.find(message => message.role === "assistant");
  const originalQuestion = firstTutor?.next_thinking_step || steps[0]?.question || summary.original_question;
  const savedReviews = summary.step_reviews || [];
  const reviews = steps.length ? steps.map((step, index) => ({
    step_index: index, title: step.title, goal: step.goal, source: step.source,
    ...savedReviews.find(review => review.step_index === index),
  })) : savedReviews;

  function reading(source) {
    const text = source?.text?.trim();
    if (!text) return null;
    const preferred = source.evidence_quote?.trim();
    const passage = preferred && text.includes(preferred) ? preferred : text;
    const excerpt = passage.length > 600 ? `${passage.slice(0, 600).replace(/\s+\S*$/, "")}…` : passage;
    return <aside className="learning-helpful-reading" aria-label="Helpful course reading">
      <span className="learning-reading-label">A USEFUL PART TO READ</span>
      <blockquote>{excerpt}</blockquote>
      <div className="learning-reading-footer"><small>{source.title || "Course material"}{source.page_number ? ` · Page ${source.page_number}` : ""}</small>
        {onViewOriginal && canViewOriginal?.(source) && <button type="button" className="secondary compact" onClick={() => onViewOriginal(source)}>Read in course material</button>}
      </div>
    </aside>;
  }

  return <section className="socratic-learning-summary" aria-label="Learning summary" tabIndex={0}>
    <h2>Your learning journey</h2>
    {assignmentId && <LearningDifficultyChart assignmentId={assignmentId} metrics={metrics} />}
    {originalQuestion && <><h3>Opening question</h3><Markdown>{originalQuestion}</Markdown></>}
    <h3>Your own summary</h3>
    <p className="student-reflection-text">{summary.student_reflection}</p>
    {reviews.length > 0 && <div className="learning-review-section-heading"><div><span>LOOK HOW FAR YOU’VE COME</span><h3>Step-by-step feedback</h3></div><b>{reviews.length} steps</b></div>}
    {!savedReviews.length && onUpdateFeedback && <div className="learning-feedback-update"><p>Your saved summary was created before step-by-step feedback was available.</p><button type="button" disabled={busy} onClick={onUpdateFeedback}>Generate step feedback</button></div>}
    {savedReviews.length > 0 && onUpdateFeedback && <button className="secondary compact" type="button" disabled={busy} onClick={onUpdateFeedback}>Update tutor feedback</button>}
    {reviews.map(review => <section className="learning-step-review" key={review.step_index}>
      <header className="learning-review-header">
        <span className="learning-review-number" aria-hidden="true">{String(review.step_index + 1).padStart(2, "0")}</span>
        <div><span className="learning-review-kicker">A MOMENT FROM YOUR JOURNEY</span><h3 aria-label={`Step ${review.step_index + 1} · ${review.title}`}>{review.title}</h3></div>
      </header>
      <div className="learning-review-body">
      {review.goal && <details className="learning-review-goal"><summary>Learning goal</summary><p>{review.goal}</p></details>}
      <div className="learning-review-findings">
      {[["understood", "What you understood", "✓"], ["clarified", "What became clearer", "✦"], ["revisit", "A helpful reminder", "↻"]].map(([key, label, icon]) =>
        review[key]?.length > 0 && <div className={`learning-review-category is-${key}`} key={key}><h4><span aria-hidden="true">{icon}</span>{label}</h4>
          {review[key].map((finding, index) => <div className="learning-finding" key={index}>
            <Markdown>{emphasizeFeedbackReason(finding.explanation)}</Markdown>
          </div>)}
        </div>)}
      </div>
      {!["understood", "clarified", "revisit"].some(key => review[key]?.length) && <p>{savedReviews.some(item => item.step_index === review.step_index) ? "There is not enough conversation evidence to assess this step yet." : "Feedback has not been generated for this step yet."}</p>}
      {reading(review.source)}
      </div>
    </section>)}
    {summary.concepts_to_revisit?.length > 0 ? <section className="learning-revisit" aria-label="Concepts to revisit">
      <h3>Helpful reminders</h3>
      {summary.concepts_to_revisit.map((item, index) => <div key={index}>
        <Markdown>{item.correction}</Markdown>
        {reading(steps.find(step => step.source?.title === item.source_title)?.source)}
        {item.source_title && <small>Course source: {item.source_title}</small>}
      </div>)}
    </section> : summary.misconception_correction && <><h3>A helpful reminder</h3><Markdown>{summary.misconception_correction}</Markdown></>}
    {Object.keys(metrics).length > 0 && <details className="learning-chat-evidence">
      <summary>View activity details</summary>
      <ul>{Object.entries(metrics).map(([index, metric]) =>
        <li key={index}>Step {Number(index) + 1} · {Math.round(metric.elapsed_seconds / 60)} min elapsed · {metric.student_questions} student questions{metric.difficulty ? ` · Difficulty: ${metric.difficulty}` : ""}</li>)}</ul>
    </details>}
    <section className="learning-overall-feedback" aria-label="Overall tutor feedback">
      <span className="learning-overall-label">YOUR JOURNEY, TOGETHER</span>
      <h3>Overall tutor feedback</h3>
      <div className="learning-tutor-feedback"><Markdown>{emphasizeFeedbackReason(summary.final_comment)}</Markdown></div>
    </section>
  </section>;
}
