export default function MissionObjectiveProgress({ objectives = [], saved, mission, compact = false }) {
  if (!objectives.length && !compact) return null;
  const met = JSON.stringify(saved?.objectives) === JSON.stringify(objectives) ? saved?.met || {} : {};
  const demonstrated = objectives.map((_, i) => Boolean(met[String(i)]?.quote && met[String(i)]?.reason));
  const count = demonstrated.filter(Boolean).length;
  const percent = objectives.length ? Math.round(count / objectives.length * 100) : 0;
  return <section className={`mission-objective-progress${compact ? " is-compact" : ""}`} aria-label={`Mission ${mission} objectives`}>
    <div className="mission-objective-heading"><strong>Mission progress</strong><b>{objectives.length ? `${percent}%` : "Objectives not configured"}</b></div>
    <div className="mission-objective-track" role="progressbar" aria-label={`Mission ${mission} objective progress`}
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={objectives.length ? percent : undefined}
      aria-valuetext={objectives.length ? `${count} of ${objectives.length} objectives demonstrated` : "No mission objectives configured"}>
      <div style={{ width: `${percent}%` }} />
    </div>
    {objectives.length > 0 && <>
      {compact ? <details><summary>{count} of {objectives.length} objectives demonstrated</summary>
        <ObjectiveList objectives={objectives} demonstrated={demonstrated} /></details>
        : <><p>{count} of {objectives.length} objectives demonstrated</p>
          <ObjectiveList objectives={objectives} demonstrated={demonstrated} /></>}
    </>}

  </section>;
}

function ObjectiveList({ objectives, demonstrated }) {
  return <ul>{objectives.map((objective, i) => <li key={`${i}-${objective}`} className={demonstrated[i] ? "is-demonstrated" : ""}>
    <span aria-hidden="true">{demonstrated[i] ? "✓" : "○"}</span>
    <div><span className="sr-only">{demonstrated[i] ? "Demonstrated: " : "Working toward: "}</span>{objective}</div>
  </li>)}</ul>;
}
