import { useState } from "react";
import { api } from "./api";
import { GenerationStatus, Notice } from "./ui";

export default function PublishedStepChecks({ assignment, onSaved }) {
  const steps = assignment.config?.learning_steps || [];
  const [proposed, setProposed] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  if (assignment.status !== "published" || assignment.tool !== "socratic" || !steps.length) return null;
  const prepared = steps.every((step) => step.checks?.length > 0);

  async function generate() {
    setBusy("Generating one application check for each learning step");
    setError("");
    setNotice("");
    try {
      const result = await api(`/platform/assignments/${assignment.id}/step-checks/draft`, { method: "POST" });
      setProposed(result.steps);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy("");
    }
  }

  function update(stepIndex, checkIndex, field, value, optionIndex = null) {
    setProposed((current) => current.map((step, s) => s !== stepIndex ? step : {
      ...step,
      checks: step.checks.map((check, c) => c !== checkIndex ? check : optionIndex === null
        ? { ...check, [field]: value }
        : { ...check, options: check.options.map((option, o) => o === optionIndex ? value : option) }),
    }));
  }

  async function save() {
    setBusy("Saving reviewed step checks");
    setError("");
    try {
      const updated = await api(`/platform/assignments/${assignment.id}/step-checks`, {
        method: "PUT", body: { checks: proposed.map((step) => step.checks.slice(0, 1)) },
      });
      onSaved(updated);
      setProposed(null);
      setNotice("Step checks saved. Students will see a check before continuing from each step.");
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy("");
    }
  }

  return <section id="learning-step-checks" className="panel published-step-checks" aria-label="Learning step checks">
    <h2>Learning step checks</h2>
    <p className="help">Students find the action that causes a problem and explain why. They get two chances on this question; after a second miss, they can continue with support.</p>
    <Notice error={error} />
    <Notice>{notice}</Notice>
    {busy && <GenerationStatus message={busy} fullScreen />}
    {!proposed ? <>
      <p>{prepared ? "All learning steps have a check." : `${steps.filter((step) => step.checks?.length > 0).length} of ${steps.length} steps have checks.`}</p>
      <button type="button" className="secondary" disabled={!!busy} onClick={generate}>{prepared ? "Review or regenerate checks" : "Generate checks for this assignment"}</button>
    </> : <>
      <p className="help">Review the answer key and wording before saving. Existing conversations stay in place.</p>
      {proposed.map((step, stepIndex) => <div className="published-step-checks-step" key={stepIndex}>
        <h3>{stepIndex + 1}. {step.title}</h3>
        {step.checks.slice(0, 1).map((check, checkIndex) => <fieldset className="socratic-step-check-editor" key={checkIndex}>
          <legend>Application check</legend>
          <label>Situation<textarea value={check.scenario} onChange={(event) => update(stepIndex, checkIndex, "scenario", event.target.value)} /></label>
          <label>Question<textarea value={check.question} onChange={(event) => update(stepIndex, checkIndex, "question", event.target.value)} /></label>
          {check.options.map((option, optionIndex) => <label key={optionIndex}>Choice {optionIndex + 1}<input value={option} onChange={(event) => update(stepIndex, checkIndex, "options", event.target.value, optionIndex)} /></label>)}
          <label>Incorrect choice<select value={check.incorrect_option_index} onChange={(event) => update(stepIndex, checkIndex, "incorrect_option_index", Number(event.target.value))}>
            {check.options.map((_, index) => <option value={index} key={index}>Choice {index + 1}</option>)}
          </select></label>
          <label>Why it is incorrect<textarea value={check.expected_reason} onChange={(event) => update(stepIndex, checkIndex, "expected_reason", event.target.value)} /></label>
        </fieldset>)}
      </div>)}
      <div className="editor-actions"><button type="button" className="secondary" onClick={() => setProposed(null)}>Discard draft</button><button type="button" onClick={save} disabled={!!busy}>Save reviewed checks</button></div>
    </>}
  </section>;
}
