import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { GenerationStatus } from "./ui";
import "./pipeline-logs.css";

const STAGES = {
  1: "Receive request", 2: "Session context", 3: "Resolve context",
  4: "Classify message", 5: "Retrieve evidence", 6: "Evaluate answer",
  7: "Check readiness / prepare prompt", 8: "Generate response",
  9: "Build response", 10: "Check response", 11: "Save result", 12: "Return response",
};
const labels = { complete: "Finished", attention: "Needs attention", in_progress: "In progress" };
const duration = ms => `${(Math.max(0, Number(ms) || 0) / 1000).toFixed(2)}s`;
const isError = event => event.event.endsWith("_failed") || event.fields?.error_type;

export default function PipelineLogs() {
  const [traces, setTraces] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [assignment, setAssignment] = useState("");
  const [query, setQuery] = useState("");
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [live, setLive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState(null);
  const [copied, setCopied] = useState("");
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState("");
  const refreshRef = useRef(null);
  const testSelection = useRef(null);
  useEffect(() => {
    let active = true, pending = false;
    const refresh = async () => {
      if (pending) return;
      pending = true;
      setRefreshing(true);
      try {
        const result = await api("/platform/pipeline-logs?limit=100");
        if (!Array.isArray(result.traces)) throw Error("The server returned an invalid log response.");
        if (active) {
          setTraces(result.traces);
          const preferred = testSelection.current && result.traces.some(trace => trace.trace_id === testSelection.current)
            ? testSelection.current : null;
          if (preferred) testSelection.current = null;
          setSelectedId(current => preferred || (result.traces.some(trace => trace.trace_id === current)
            ? current : result.traces[0]?.trace_id || ""));
          setUpdated(new Date());
          setError("");
        }
      } catch (failure) {
        if (active) setError(failure.message || "Pipeline logs are unavailable.");
      } finally {
        pending = false;
        if (active) { setLoading(false); setRefreshing(false); }
      }
    };
    refreshRef.current = refresh;
    refresh();
    const timer = live ? window.setInterval(refresh, 5000) : null;
    return () => { active = false; window.clearInterval(timer); refreshRef.current = null; };
  }, [live]);
  const assignments = [...new Map(traces.map(trace => [trace.assignment_id, trace.assignment_title])).entries()];
  const visible = traces.filter(trace => (!assignment || trace.assignment_id === assignment)
    && (!attentionOnly || trace.status === "attention")
    && (!query.trim() || JSON.stringify([trace.trace_id, trace.assignment_title,
      ...trace.events.map(event => [event.event, event.fields?.provider, event.fields?.model])])
      .toLowerCase().includes(query.trim().toLowerCase())));
  const selected = visible.find(trace => trace.trace_id === selectedId) || visible[0];
  const models = selected ? [...new Set(selected.events.map(event => event.fields?.model).filter(Boolean))] : [];
  const copyLog = async () => {
    try { await navigator.clipboard.writeText(JSON.stringify(selected, null, 2)); setCopied("Log copied."); }
    catch { setCopied("Could not copy the log. Please try again."); }
  };
  const generateTest = async () => {
    if (!selected || testing) return;
    setTesting(true); setTestError("");
    try {
      const result = await api("/platform/pipeline-logs/test", {method: "POST", body: {assignment_id: selected.assignment_id}});
      testSelection.current = result.trace_id;
      setAttentionOnly(false); setQuery("");
      await refreshRef.current?.();
      if (result.failed) setTestError("The test reported a pipeline error. Inspect its events below.");
    } catch (failure) { setTestError(failure.message || "The test request could not run."); }
    finally { setTesting(false); }
  };
  return <div className="pipeline-logs-page">
    <header className="pipeline-logs-heading">
      <div><span className="pipeline-eyebrow">INSTRUCTOR WORKSPACE</span><h1>Pipeline logs</h1>
        <p>Follow each Socratic assignment request from the student message to the tutor response.</p></div>
      <div className="pipeline-live-controls">
        <label><input type="checkbox" checked={live} onChange={event => setLive(event.target.checked)} />Refresh every 5 seconds</label>
        <button type="button" className="secondary" disabled={refreshing} onClick={() => refreshRef.current?.()}>
          {refreshing ? "Refreshing…" : "Refresh logs"}
        </button>
      </div>
    </header>
    <p className="help">Only requests from courses you teach are shown. Expand a prompt event to read the system and developer instructions. User-message payloads are excluded; emails and credentials are redacted. The server retains its latest 100 requests.</p>
    {error && <p className="notice error" role="alert">{error} {traces.length > 0 && "Showing the last available logs."}</p>}
    <div className="pipeline-test-controls"><div><strong>Inspect prompts without switching accounts</strong>
      <p className="help">Run one AI test on the selected assignment’s first learning step. No student work is saved.</p></div>
      <button type="button" disabled={!selected || testing} onClick={generateTest}>{testing ? "Generating test log…" : "Generate test log"}</button></div>
    {testError && <p className="notice error" role="alert">{testError}</p>}
    <div className="pipeline-log-filters">
      <label>Assignment<select value={assignment} onChange={event => setAssignment(event.target.value)}>
        <option value="">All assignments</option>{assignments.map(([id, title]) => <option key={id} value={id}>{title}</option>)}
      </select></label>
      <label>Search logs<input value={query} placeholder="Request ID, model, or event" onChange={event => setQuery(event.target.value)} /></label>
      <label className="pipeline-attention-filter"><input type="checkbox" checked={attentionOnly} onChange={event => setAttentionOnly(event.target.checked)} />Needs attention only</label>
    </div>
    <p className="help" aria-live="polite">{visible.length} requests{updated ? ` · Last refreshed ${updated.toLocaleTimeString()}` : ""}</p>
    {loading ? <GenerationStatus title="Loading pipeline logs" message="Reading recent requests…" /> : !selected ?
      <section className="panel pipeline-log-empty"><h2>{traces.length ? "No matching requests" : "No assignment logs yet"}</h2>
        <p>{traces.length ? "Adjust the filters to see more requests." : "Send a message in a Socratic assignment from one of your courses. Its pipeline events will appear here automatically."}</p></section> :
      <div className="pipeline-logs-layout">
        <aside className="panel pipeline-log-list" aria-label="Recent requests">
          {visible.map(trace => <button type="button" key={trace.trace_id} aria-pressed={selected.trace_id === trace.trace_id}
            className={`pipeline-request ${selected.trace_id === trace.trace_id ? "is-selected" : ""}`} onClick={() => { setSelectedId(trace.trace_id); setCopied(""); }}>
            <span className={`pipeline-status is-${trace.status}`}>{labels[trace.status] || trace.status}</span>
            <strong>{trace.assignment_title}</strong>
            {trace.diagnostic && <small>Instructor test · No student work saved</small>}
            <span>{new Date(trace.started_at).toLocaleString()}</span>
            <small>{trace.step_index == null ? "Learning step not recorded" : `Learning step ${trace.step_index + 1}`} · {duration(trace.duration_ms)}</small>
            <code>{trace.trace_id.slice(0, 12)}</code>
          </button>)}
        </aside>
        <section className="panel pipeline-log-detail" aria-label="Request details">
          <header><div><h2>{selected.assignment_title}</h2><p className="help">{selected.course_title} · {duration(selected.duration_ms)}</p></div>
            <button type="button" className="secondary" onClick={copyLog}>Copy log</button></header>
          <p className="pipeline-request-id">Request <code>{selected.trace_id}</code></p>
          {selected.diagnostic && <p className="help">Instructor test using the published assignment. This is separate from student attempts.</p>}
          <div className="pipeline-models">{models.map(model => <span key={model}>{model}</span>)}</div>
          {!selected.events.some(event => event.prompt) && <p className="help">Prompt instructions were not captured for this request. Send a new message in the assignment to see its prompts.</p>}
          {copied && <p role="status">{copied}</p>}
          {selected.status === "attention" && <p className="notice">A pipeline stage reported an error. Check the events below for the failed stage and any fallback.</p>}
          <ol className="pipeline-event-list" aria-label="Pipeline events">
            {selected.events.map((event, index) => <li key={`${selected.trace_id}-${index}-${event.event}`} className={isError(event) ? "has-error" : ""}>
              <div className="pipeline-event-heading"><span className="pipeline-stage">{STAGES[event.stage] || `Stage ${event.stage}`}</span><time>+{duration(event.elapsed_ms)}</time></div>
              <strong className="pipeline-event-name">{event.event.replaceAll("_", " ")}</strong>
              <div className="pipeline-event-fields">{Object.entries(event.fields || {}).map(([key, value]) => <span key={key}><span>{key.replaceAll("_", " ")}</span><code>{String(value)}</code></span>)}</div>
              {event.prompt && <details className="pipeline-prompt"><summary>View prompt instructions ({event.prompt.role})</summary>
                <pre>{event.prompt.text}</pre>
                {event.prompt.truncated && <p className="help">This instruction exceeded the log limit; showing the first 32,000 characters.</p>}
              </details>}
            </li>)}
          </ol>
        </section>
      </div>}
  </div>;
}
