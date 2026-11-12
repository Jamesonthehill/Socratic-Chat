import { useEffect, useState } from "react";
import { api } from "./api";

import { STEP_DIFFICULTY_OPTIONS } from "./stepDifficulty";

const RATINGS = STEP_DIFFICULTY_OPTIONS.map(({ value, label }) => [value, label]);

export default function LearningDifficultyChart({ assignmentId, metrics = {} }) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const result = await api(`/platform/assignments/${assignmentId}/learning-journey`);
        if (active) { setData(result); setFailed(false); }
      } catch { if (active) setFailed(true); }
    }
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => { active = false; clearInterval(interval); };
  }, [assignmentId]);

  return <section className="journey-difficulty" aria-label="Step difficulty comparison">
    <div className="journey-chart-heading"><div><span className="journey-chart-eyebrow">YOUR CLASS, STEP BY STEP</span>
      <h3>How did each step feel?</h3></div><span className="journey-chart-live"><i />Updates every 30s</span></div>
    <p>See how everyone rated each step, including you and classmates still working on the assignment.</p>
    <div className="journey-chart-legend">{RATINGS.map(([key, label]) => <span key={key}><i className={`difficulty-${key}`} />{label}</span>)}</div>
    {!data && <p role="status">{failed ? "Class ratings are unavailable right now. We’ll try again shortly." : "Loading class ratings…"}</p>}
    <div className="journey-chart-grid">{data?.steps.map(step => {
      const own = metrics[String(step.step_index)]?.difficulty;
      const ownLabel = RATINGS.find(([key]) => key === own)?.[1];
      const responses = (step.responses ?? 0) + Number(Boolean(ownLabel));
      const distribution = RATINGS.map(([key, label]) => ({
        key, label, count: (step.counts?.[key] ?? 0) + Number(key === own),
      }));
      return <div className="journey-chart-row" key={step.step_index}>
        <div className="journey-chart-label"><strong><span>{step.step_index + 1}</span>{step.title}</strong>
          <span className={`journey-own-rating difficulty-${own || "none"}${ownLabel ? " is-your-difficulty" : ""}`}>You: {ownLabel || "Not rated"}</span></div>
        {responses > 0 ? <>
          <div className="journey-chart-bar" role="img" aria-label={distribution.map(({ label, count }) => `${label}: ${count} of ${responses}`).join(", ")}>
            {distribution.filter(({ count }) => count > 0).map(({ key, label, count }) => <div className={`difficulty-${key}${own === key ? " is-your-difficulty" : ""}`} key={key}
              style={{ width: `${count / responses * 100}%` }} title={`${label}: ${count} ${count === 1 ? "rating" : "ratings"}${own === key ? " · Includes your rating" : ""}`}>
              <span>{Math.round(count / responses * 100)}%</span>{own === key && <b className="journey-you-marker" aria-hidden="true">You</b>}</div>)}
          </div>
          <div className="journey-chart-counts"><span>{responses === 1 ? `1 response${ownLabel ? " (yours)" : ""}` : `${responses} responses${ownLabel ? ", including yours" : ""}`}</span><span>{distribution.map(({ label, count }) => `${label} ${count}`).join(" · ")}</span></div>
        </> : <p className="journey-chart-waiting">No ratings yet.</p>}
      </div>;
    })}</div>
    {data && failed && <p role="status">Showing the last available ratings. Reconnecting…</p>}
    <small>Percentages show the share of responses at each difficulty level.</small>
  </section>;
}
