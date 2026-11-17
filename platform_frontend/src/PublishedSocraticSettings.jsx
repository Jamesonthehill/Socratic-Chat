import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "./api";
import { Notice } from "./ui";

export default function PublishedSocraticSettings({ assignment, onSaved }) {
  const config = assignment.config || {};
  const [form, setForm] = useState(() => ({
    instructions: assignment.instructions || "",
    prompt: config.prompt || "",
    tutor_mode: config.tutor_mode === "javis" ? "jarvis" : config.tutor_mode || "socrates",
    minimum_step_questions: config.minimum_step_questions ?? 1,
    learning_steps: (config.learning_steps || []).map(({ title, goal, scenario, question }) => ({
      title, goal, scenario: scenario || "", question: question || "",
    })),
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);
  const steps = config.learning_steps || [];
  if (assignment.status !== "published" || assignment.tool !== "socratic" || !steps.length) return null;

  function updateStep(index, key, value) {
    setForm((current) => ({ ...current, learning_steps: current.learning_steps.map((step, position) =>
      position === index ? { ...step, [key]: value } : step),
    }));
  }

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await api(`/platform/assignments/${assignment.id}/socratic-settings`, {
        method: "PATCH", body: form,
      });
      onSaved(updated);
      setNotice("Published settings saved. New chats use the updated opening; messages already sent stay as they were.");
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel published-socratic-settings" aria-label="Published Socratic settings">
    {notice && createPortal(
      <div className="published-settings-toast" role="status">
        <span aria-hidden="true">✓</span>
        <div><strong>Published settings saved</strong><p>Your changes are ready.</p></div>
        <button type="button" className="quiet compact" aria-label="Dismiss save confirmation" onClick={() => setNotice("")}>×</button>
      </div>, document.body,
    )}
    <h2>Edit published Socratic settings</h2>
    <p className="help">Adjust the questions and scenes students will see next. Saved conversations and course-material references remain in place.</p>
    <Notice error={error} />
    <form onSubmit={save}>
      <fieldset disabled={busy}>
        <label>Tutor style
          <select value={form.tutor_mode} onChange={(event) => setForm((current) => ({ ...current, tutor_mode: event.target.value }))}>
            <option value="socrates">Socrates — formal</option>
            <option value="jarvis">Jarvis — friendly with slang</option>
          </select>
        </label>
        <label>Student instructions
          <textarea rows={4} maxLength={10000} value={form.instructions} onChange={(event) => setForm((current) => ({ ...current, instructions: event.target.value }))} />
        </label>
        <label>Opening question or prompt
          <textarea rows={3} maxLength={10000} value={form.prompt} onChange={(event) => setForm((current) => ({ ...current, prompt: event.target.value }))} />
          <small className="help">A revised opening appears when a student starts a new conversation. It does not rewrite messages already sent.</small>
        </label>
        <div className="published-socratic-settings-counts">
          <label>Tutor questions before continuing
            <input type="number" min={1} max={10} value={form.minimum_step_questions} onChange={(event) => setForm((current) => ({ ...current, minimum_step_questions: Number(event.target.value) }))} />
          </label>
        </div>
        <h3>Learning steps</h3>
        {form.learning_steps.map((step, index) => <details key={index} className="published-socratic-step">
          <summary>{index + 1}. {step.title}</summary>
          <label>Step title<input required minLength={3} maxLength={120} value={step.title} onChange={(event) => updateStep(index, "title", event.target.value)} /></label>
          <label>Learning goal<textarea required minLength={8} maxLength={500} rows={2} value={step.goal} onChange={(event) => updateStep(index, "goal", event.target.value)} /></label>
          <label>Source context students will see<textarea maxLength={700} rows={4} value={step.scenario} onChange={(event) => updateStep(index, "scenario", event.target.value)} /></label>
          <label>Question for this step<textarea maxLength={500} rows={2} value={step.question} onChange={(event) => updateStep(index, "question", event.target.value)} /></label>
          <p className="help">The cited course passage for this step stays the same.</p>
        </details>)}
        <button type="submit">{busy ? "Saving…" : "Save published settings"}</button>
      </fieldset>
    </form>
  </section>;
}
