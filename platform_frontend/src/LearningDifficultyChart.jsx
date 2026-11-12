import { useEffect, useState } from "react";
import { api } from "./api";

const RATINGS = [["easy", "Easy"], ["moderate", "Moderate"], ["hard", "Hard"]];

export default function LearningDifficultyChart({ assignmentId, metrics = {} }) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [preview, setPreview] = useState(false);
  const localPreview = ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
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

  const displayData = preview && data ? {
    ...data,
    steps: data.steps.map((step, index) => {
      const patterns = [[8, 3, 1], [3, 6, 3], [2, 4, 6], [5, 5, 2], [1, 4, 7]];
      const [easy, moderate, hard] = patterns[index % patterns.length];
      return { ...step, available: true, responses: 12, counts: { easy, moderate, hard } };
    }),
  } : data;

  return <section className="journey-difficulty" aria-label="Step difficulty comparison">
    <div className="journey-chart-heading"><div><span className="journey-chart-eyebrow">YOUR CLASS, STEP BY STEP</span>
      <h3>How did each step feel?</h3></div><span className="journey-chart-live"><i />{preview ? "Sample preview" : "Updates every 30s"}</span></div>
    {localPreview && <label className="journey-preview-toggle"><input type="checkbox" checked={preview} onChange={event => setPreview(event.target.checked)} />Preview sample ratings</label>}
    {preview && <p className="journey-preview-notice" role="status">Sample data: 12 fictional classmates per step. Your saved ratings stay unchanged. These samples are not saved.</p>}
    <p>How you and your classmates experienced each step.</p>
    <div className="journey-chart-legend">{RATINGS.map(([key, label]) => <span key={key}><i className={`difficulty-${key}`} />{label}</span>)}</div>
    {!data && <p role="status">{failed ? "Class ratings are unavailable right now. We’ll try again shortly." : "Loading class ratings…"}</p>}
    {displayData?.steps.some(step => !step.available) && <p className="journey-chart-pending">Class comparison appears after {displayData.minimum_responses} classmates rate each step.</p>}
    <div className="journey-chart-grid">{displayData?.steps.map(step => {
      const own = metrics[String(step.step_index)]?.difficulty;
      return <div className="journey-chart-row" key={step.step_index}>
        <div className="journey-chart-label"><strong><span>{step.step_index + 1}</span>{step.title}</strong>
          <span className={`journey-own-rating difficulty-${own || "none"}${RATINGS.some(([key]) => key === own) ? " is-your-difficulty" : ""}`}>You: {RATINGS.find(([key]) => key === own)?.[1] || "Not rated"}</span></div>
        {step.available ? <>
          <div className="journey-chart-bar" role="img" aria-label={RATINGS.map(([key, label]) => `${label}: ${step.counts[key]} of ${step.responses}`).join(", ")}>
            {RATINGS.map(([key, label]) => step.counts[key] > 0 && <div className={`difficulty-${key}${own === key ? " is-your-difficulty" : ""}`} key={key}
              style={{ width: `${step.counts[key] / step.responses * 100}%` }} title={`${label}: ${step.counts[key]} ratings${own === key ? " · Your difficulty rating" : ""}`}>
              <span>{Math.round(step.counts[key] / step.responses * 100)}%</span>{own === key && <b className="journey-you-marker" aria-hidden="true">You</b>}</div>)}
          </div>
          <div className="journey-chart-counts"><span>{step.responses} classmates rated</span><span>{RATINGS.map(([key, label]) => `${label} ${step.counts[key]}`).join(" · ")}</span></div>
          {RATINGS.some(([key]) => key === own) && step.counts[own] === 0 && <small>No classmates have selected your difficulty level yet.</small>}
        </> : <div className="journey-chart-waiting">Awaiting class ratings</div>}
      </div>;
    })}</div>
    {data && failed && <p role="status">Showing the last available ratings. Reconnecting…</p>}
    <small>Anonymous class ratings exclude yours. Difficulty is self-reported, not a measure of mastery.</small>
  </section>;
}
