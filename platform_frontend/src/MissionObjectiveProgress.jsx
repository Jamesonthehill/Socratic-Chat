export default function MissionObjectiveProgress({ objectives = [], saved, mission, compact = false }) {
  if (!objectives.length && !compact) return null;
  const met = JSON.stringify(saved?.objectives) === JSON.stringify(objectives) ? saved?.met || {} : {};
  const demonstrated = objectives.map((_, i) => Boolean(met[String(i)]?.quote && met[String(i)]?.reason));
  const count = demonstrated.filter(Boolean).length;
  const percent = objectives.length ? Math.round(count / objectives.length * 100) : 0;
  const complete = objectives.length > 0 && count === objectives.length;
  return <section className={`mission-objective-progress mission-game-gauge${compact ? " is-compact" : ""}${complete ? " is-complete" : ""}`} aria-label={`Mission ${mission} objectives`}>
    <div className="mission-objective-heading">
      <div className="mission-gauge-identity">
        <div className="mission-gauge-emblem" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none">
          <path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z" />
          {complete ? <path d="m8 12 3 3 5-6" /> : <path d="m12 7 1.5 3 3.5.5-2.5 2.5.5 3.5-3-1.5-3 1.5.5-3.5L7 10.5l3.5-.5L12 7Z" />}
        </svg></div>
        <div><strong>Mission progress</strong>
          <span className="mission-gauge-state">{!objectives.length ? "Set objectives to begin" : complete ? "Mission cleared" : count ? "Building understanding" : "Your next discovery awaits"}</span>
        </div>
      </div>
      {objectives.length > 0 && <b className="mission-gauge-percent">{percent}<small>%</small></b>}
    </div>
    <div className="mission-gauge-runway">
      <div className="mission-objective-track" role="progressbar" aria-label={`Mission ${mission} objective progress`}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={objectives.length ? percent : undefined}
        aria-valuetext={objectives.length ? `${count} of ${objectives.length} objectives demonstrated` : "No mission objectives configured"}>
        <div className="mission-gauge-fill" style={{ width: `${percent}%` }}>
          {percent > 0 && <i key={count} className="mission-gauge-sweep" />}
        </div>
        <div className="mission-gauge-divisions" aria-hidden="true" style={{gridTemplateColumns:`repeat(${objectives.length || 1}, 1fr)`}}>
          {objectives.map((_, i) => <i key={i} />)}
        </div>
      </div>
      {objectives.length > 0 && <div className="mission-gauge-milestones" aria-hidden="true">
        {objectives.map((_, i) => <span key={i} className={i < count ? "is-earned" : ""}
          style={{left:`${(i + 1) / objectives.length * 100}%`}}>{i < count ? "✓" : "·"}</span>)}
      </div>}
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
