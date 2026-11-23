import { useEffect, useId, useRef, useState } from "react";
import { api } from "./api";
import { GenerationStatus, Notice } from "./ui";
import CourseLearningMaterials from "./CourseLearningMaterials";

export const defaults = {
  socratic: {
    scope_mode: "assignment",
    guidance_mode: "guided",
    tutor_mode: "socrates",
    keywords: [],
    optional_keywords: [],
    dismissed_keywords: [],
    document_ids: [],
    learning_steps: [],
    prompt: "",
    minimum_step_questions: 2,
  },
  debate: {
    document_ids: [],
    scenario: "",
    opening_prompt: "",
    minimum_messages: 3,
    reflection_prompt:
      "What changed or became more nuanced in your thinking, which counterargument or tradeoff mattered most, and what would you revise in your final position?",
  },
  reflections: {
    module_type: "topic_based",
    required_topics: [],
    sub_topics: [],
    expected_depth: "surface",
    probing_style: "supportive",
    must_include_application: false,
    custom_notes: "",
    milestone_prompt: "",
    historical_data: "",
  },
};

function Lines({ label, value = [], onChange, rows = 4, description, publishTarget, invalid = false }) {
  return (
    <label>
      {label}
      <textarea
        data-publish-target={publishTarget}
        aria-invalid={invalid || undefined}
        rows={rows}
        value={value.join("\n")}
        onChange={(e) => onChange(e.target.value.split("\n"))}
      />
      <span className="help">{description} {"One item per line."}</span>
    </label>
  );
}

export function SocraticConfig({
  value,
  onChange,
  courseId,
  frozen,
  onMaterialsChange,
  hideConversation = false,
  hideDocuments = false,
  documents,
  hideMaterials = false,
  onGenerateSetup,
  onGenerateOpening,
  publishIssue,
  setupError = "",
  generatingSetup = false,
  canGenerateSetup = false,
}) {
  const change = (key, next) => onChange({ ...value, [key]: next });
  const guidanceMode = "guided";
  const draggedStep = useRef(null);
  const [dragOverStep, setDragOverStep] = useState(null);
  const [expandedStep, setExpandedStep] = useState(0);
  const stepCount = value.learning_steps?.length || 0;
  useEffect(() => {
    setExpandedStep((current) => Math.min(current, Math.max(0, stepCount - 1)));
  }, [stepCount]);
  const openingPromptId = useId();
  const reorderStep = (from, to) => {
    const steps = value.learning_steps || [];
    if (from === to || from < 0 || to < 0 || from >= steps.length || to >= steps.length) return;
    const next = [...steps];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setExpandedStep((current) => {
      if (current === from) return to;
      if (from < to && current > from && current <= to) return current - 1;
      if (from > to && current >= to && current < from) return current + 1;
      return current;
    });
    change("learning_steps", next);
  };
  const removeStep = (index) => {
    const next = value.learning_steps.filter((_, position) => position !== index);
    setExpandedStep((current) => current === index
      ? Math.min(index, Math.max(0, next.length - 1))
      : current > index ? current - 1 : current);
    change("learning_steps", next);
  };
  const dropPosition = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return event.clientY < rect.top + rect.height / 2 ? "before" : "after";
  };
  return (
    <>
      <p className="help"><strong>Teaching scope:</strong> Selected assignment materials.</p>
      <p className="help">
        Students can move among topics supported by the selected documents. Canvas links alone are not indexed; upload the PDF and any source files below.
      </p>
      <h3>Guided learning path</h3>
      <fieldset className="socratic-guidance-mode">
        <legend>Tutor style</legend>
        <label>
          <input type="radio" name="tutor-mode" checked={["jarvis", "javis"].includes(value.tutor_mode)} disabled={frozen} onChange={() => change("tutor_mode", "jarvis")} />
          <span><strong>Jarvis</strong><small>A friendly tutor who speaks naturally, like a conversation.</small></span>
        </label>
        <label>
          <input type="radio" name="tutor-mode" checked={(value.tutor_mode || "socrates") === "socrates"} disabled={frozen} onChange={() => change("tutor_mode", "socrates")} />
          <span><strong>Socrates</strong><small>A tutor who uses formal, professional language.</small></span>
        </label>
      </fieldset>
      {!frozen && guidanceMode === "guided" && (
        <div className="socratic-source-generation" data-publish-target="learning-path">
          <button
            type="button"
            className="secondary socratic-generate-setup"
            disabled={!canGenerateSetup || generatingSetup}
            onClick={onGenerateSetup}
          >
            {generatingSetup ? "Generating setup…" : "Generate setup from selected sources"}
          </button>
          <p className="help">
            AI drafts a beginning-to-end learning path, an opening question, student/submission instructions, from the selected indexed documents. Review and edit these before publishing.
          </p>
          {setupError && <p className="publish-inline-error" role="alert">{setupError}</p>}
          {publishIssue?.target === "learning-path" && <p className="publish-inline-error">{publishIssue.message}</p>}
        </div>
      )}
      {!hideConversation && (
        <section
          className="socratic-conversation-settings"
          aria-label="Conversation settings"
        >
        {!hideMaterials && <h3>Conversation settings</h3>}
        <div className="socratic-opening-heading">
          <label htmlFor={openingPromptId}>Opening question or prompt</label>
          {!frozen && guidanceMode === "basic" && onGenerateOpening && <button
            type="button"
            className="secondary socratic-generate-opening"
            disabled={!canGenerateSetup || generatingSetup}
            onClick={onGenerateOpening}
          >{generatingSetup ? "Generating question…" : "Generate opening question"}</button>}
        </div>
          <textarea
            id={openingPromptId}
            rows={4}
            value={value.prompt || ""}
            onChange={(e) => change("prompt", e.target.value)}
            placeholder="What assumptions does this design make?"
          />
        {guidanceMode === "basic" && !frozen && onGenerateOpening && <p className="help">Generate one opening question from the selected indexed documents, then review or edit it. Other settings stay as they are.</p>}
        {guidanceMode === "guided" && <section className="socratic-learning-steps" aria-label="Learning steps">
          <h3>Learning steps</h3>
          {!frozen && <button type="button" className="secondary compact"
            disabled={stepCount >= 10}
            onClick={() => {
              setExpandedStep(stepCount);
              onChange({ ...value, guidance_mode: "guided", learning_steps: [
                ...(value.learning_steps || []),
                { title: "", goal: "", objectives: [], scenario: "", question: "", evidence_quote: "", source_chunk_id: "", source_file: "", checks: [] },
              ] });
            }}>Add blank step</button>}
          <p className="help">Scan the path below. Select a step to edit its details, or drag a row or use the arrows to change the order. Students can still ask related questions at any point.</p>
          {!value.learning_steps?.length && <p className="help">Generate a learning path or add a blank step to write your own.</p>}
          <ol className="socratic-step-list">
          {(value.learning_steps || []).map((step, index) => {
            const updateStep = (field, next) => change("learning_steps", value.learning_steps.map((item, position) => position === index ? { ...item, [field]: next } : item));
            const isExpanded = expandedStep === index;
            const dropClass = dragOverStep?.index === index && draggedStep.current !== index
              ? ` is-drag-over-${dragOverStep.position}` : "";
            return <li
              className={`socratic-learning-step${isExpanded ? " is-expanded" : ""}${dropClass}`}
              key={`${step.source_chunk_id}-${index}`}
              draggable={!frozen}
              onDragStart={(event) => {
                if (frozen || event.target.closest("input, textarea, select, a, .socratic-step-control, [contenteditable='true']")) {
                  event.preventDefault();
                  return;
                }
                draggedStep.current = index;
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData("text/plain", String(index));
              }}
              onDragEnd={() => {
                draggedStep.current = null;
                setDragOverStep(null);
              }}
              onDragOver={(event) => {
                if (frozen || draggedStep.current === null) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                if (draggedStep.current === index) {
                  setDragOverStep(null);
                  return;
                }
                const position = dropPosition(event);
                setDragOverStep((current) => current?.index === index && current.position === position
                  ? current : { index, position });
              }}
              onDrop={(event) => {
                if (frozen || draggedStep.current === null) return;
                event.preventDefault();
                const from = draggedStep.current;
                const insertion = index + (dropPosition(event) === "after" ? 1 : 0);
                reorderStep(from, insertion > from ? insertion - 1 : insertion);
                draggedStep.current = null;
                setDragOverStep(null);
              }}
            >
              <div className="socratic-learning-step-heading">
                <button
                  type="button"
                  className="socratic-step-summary"
                  draggable={!frozen}
                  aria-label={`Step ${index + 1}: ${step.title || "Untitled step"}. ${step.question || step.goal || "Add a question for this step"}. Source: ${step.source_file || "Selected document"}`}
                  aria-expanded={isExpanded}
                  aria-controls={`${openingPromptId}-step-${index}`}
                  onClick={() => setExpandedStep(isExpanded ? -1 : index)}
                >
                  <span className="socratic-step-summary-main">
                    {!frozen && <span className="socratic-step-drag-handle" aria-hidden="true" title={`Drag step ${index + 1} card to reorder`}>⋮⋮</span>}
                    <span className="socratic-step-number"><span className="sr-only">Step </span>{index + 1}</span>
                    <strong className="socratic-step-name">{step.title || "Untitled step"}</strong>
                    <span className="socratic-step-expand-icon" aria-hidden="true">{isExpanded ? "▾" : "▸"}</span>
                  </span>
                  <span className="socratic-step-question">{step.question || step.goal || "Add a question for this step"}</span>
                  <span className="socratic-step-source">{step.source_file || "Selected document"}</span>
                </button>
                {!frozen && <div className="socratic-step-controls">
                  <button type="button" className="quiet compact socratic-step-control socratic-step-move" disabled={index === 0} onClick={() => reorderStep(index, index - 1)} aria-label={`Move step ${index + 1} up`} title="Move up">↑</button>
                  <button type="button" className="quiet compact socratic-step-control socratic-step-move" disabled={index === value.learning_steps.length - 1} onClick={() => reorderStep(index, index + 1)} aria-label={`Move step ${index + 1} down`} title="Move down">↓</button>
                  <button type="button" className="quiet compact socratic-step-control socratic-step-remove" onClick={() => removeStep(index)} aria-label={`Remove step ${index + 1}`} title="Remove step">×</button>
                </div>}
              </div>
              {isExpanded && <div id={`${openingPromptId}-step-${index}`} className="socratic-step-editor">
                <label>Step title<input value={step.title} disabled={frozen} onChange={(event) => updateStep("title", event.target.value)} /></label>
                <label>What the student should reason about<textarea rows={2} value={step.goal} disabled={frozen} onChange={(event) => updateStep("goal", event.target.value)} /></label>
                <label>Mission objectives (one per line)
                  <textarea rows={4} value={(step.objectives || []).join("\n")} disabled={frozen}
                    onChange={(event) => updateStep("objectives", event.target.value.split("\n"))}
                    placeholder={"Explain what evidence would justify a change.\nConnect that change to the team's goal."} />
                </label>
                <p className="help">Use 2–4 distinct objectives students can demonstrate through reasoning. Each objective needs 8–300 characters; up to 6 are allowed. Progress is saved as students demonstrate them.</p>
                <label>{index === 0 ? "First source context students will see" : "Source context students will see"}
                  <textarea rows={5} maxLength={700} value={step.scenario || ""} disabled={frozen}
                    onChange={(event) => updateStep("scenario", event.target.value)}
                    placeholder="Explain the relevant topic, requirement, or example from this step's selected material." />
                </label>
                <p className="help">Explain the selected material in plain language before the question. Use its own example when available, and leave the answer open.</p>
                <label>Question for this step<textarea rows={2} maxLength={500} value={step.question || ""} disabled={frozen} onChange={(event) => updateStep("question", event.target.value)} placeholder="What should the student reason about next?" /></label>
                <details className="socratic-step-evidence"><summary>View supporting passage</summary><p>{step.evidence_quote}</p></details>
              </div>}
            </li>;
          })}
          </ol>
        </section>}
        {guidanceMode === "guided" && <label>
          Tutor questions before continuing
          <input type="number" min={1} max={10}
            value={value.minimum_step_questions ?? 2}
            onChange={(event) => change("minimum_step_questions", Number(event.target.value))} />
          <small className="help">The first question in each step counts. Repeating the same question does not. For missions without objectives, students continue after this minimum and a readiness check. Missions with objectives can finish as soon as every objective is demonstrated, without extra questions.</small>
        </label>}
        </section>
      )}
      {!hideMaterials &&
        (courseId ? (
          <CourseLearningMaterials
            key={courseId}
            courseId={courseId}
            onChange={onMaterialsChange}
            assignmentConfig={{ ...value, scope_mode: "assignment" }}
            onAssignmentChange={onChange}
            frozen={frozen}
            embedded
            hideDocuments={hideDocuments}
            documents={documents}
          />
        ) : (
          <p>Choose a course to manage its documents and learning objectives.</p>
        ))}
    </>
  );
}

function ReflectionHelp({ text }) {
  const id = useId();
  return (
    <span className="reflection-help" tabIndex={0} role="img" aria-label={text} aria-describedby={id}>
      ⓘ
      <span id={id} role="tooltip" className="reflection-help-content">{text}</span>
    </span>
  );
}

export function ReflectionConfig({ value, onChange, publishIssue }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const change = (k, v) => onChange({ ...value, [k]: v });
  return (
    <>
      <Notice error={error} />
      <p className="help">Choose a reflection format, then configure the guidance students will receive.</p>
      <label>
        Reflection type
        <select
          value={value.module_type}
          onChange={(e) => change("module_type", e.target.value)}
        >
          <option value="topic_based">Topic-based conversation</option>
          <option value="milestone_based">Milestone reflection</option>
        </select>
      </label>
      <p className="help">
        <strong>Topic-based conversation:</strong> An AI-guided discussion of course concepts using follow-up questions.
        <br />
        <strong>Milestone reflection:</strong> Students reflect on a challenge and their solution; past responses help inform recommendations.
      </p>
      {value.module_type === "topic_based" ? (
        <>
          <div className="form-columns">
            <Lines
              label="Learning topics"
              description="List the main concepts students should reflect on, such as neural networks."
              value={value.required_topics}
              onChange={(v) => change("required_topics", v)}
            />
            <div>
              <Lines
                label="Sub-topics to explore"
                publishTarget="reflection-subtopics"
                invalid={publishIssue?.target === "reflection-subtopics"}
                description="Add specific concepts to discuss in order. Generate a draft from your learning topics, then review it."
                value={value.sub_topics}
                onChange={(v) => change("sub_topics", v)}
              />
              {publishIssue?.target === "reflection-subtopics" && <p className="publish-inline-error">{publishIssue.message}</p>}
              <button
                className="secondary compact"
                type="button"
                disabled={busy || !value.required_topics.some((t) => t.trim())}
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  try {
                    const data = await api("/platform/generate-subtopics", {
                      method: "POST",
                      body: {
                        main_topics: value.required_topics.filter((t) =>
                          t.trim(),
                        ),
                      },
                    });
                    change("sub_topics", data.sub_topics);
                  } catch (e) {
                    setError(e.message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? "Generating…" : "Generate sub-topics"}
              </button>
              {busy && <GenerationStatus message="Generating reflection sub-topics…" fullScreen />}
            </div>
          </div>
          <div className="form-columns">
            <label>
              Expected depth <ReflectionHelp text="Sets the level of detail the AI asks for. Surface: explain the basics. Applied: connect concepts to real situations. Analytical: compare ideas and critically evaluate them." />
              <select
                aria-label="Expected depth"
                value={value.expected_depth}
                onChange={(e) => change("expected_depth", e.target.value)}
              >
                <option value="surface">Surface</option>
                <option value="applied">Applied</option>
                <option value="analytical">Analytical</option>
              </select>
            </label>
            <label>
              Probing style <ReflectionHelp text="Sets how the AI follows up. Supportive: warm encouragement and gentle guidance. Socratic: probing questions that ask students to explain their reasoning and assumptions." />
              <select
                aria-label="Probing style"
                value={value.probing_style}
                onChange={(e) => change("probing_style", e.target.value)}
              >
                <option value="supportive">Supportive</option>
                <option value="socratic">Socratic</option>
              </select>
            </label>
          </div>
          <p className="help">{({surface: "Surface: explain the basics in a brief summary.", applied: "Applied: connect concepts to real situations.", analytical: "Analytical: compare, contrast, and critically evaluate ideas."})[value.expected_depth]} {value.probing_style === "socratic" ? "Socratic: follow-up questions explore reasoning and assumptions." : "Supportive: warm encouragement and gentle guidance."}</p>
          <label className="check">
            <input
              type="checkbox"
              aria-label="Require a practical application"
              checked={value.must_include_application}
              onChange={(e) =>
                change("must_include_application", e.target.checked)
              }
            />
            Require a practical application <ReflectionHelp text="Instructs the AI to ask at least one question where students apply a concept to a real scenario. For example: How would you use this approach in a class project?" />
          </label>
          <label>
            Professor notes <ReflectionHelp text="These notes are sent to the AI as priority instructions for the conversation. Use them to specify concepts to emphasize or misconceptions to revisit; they are not a private reminder pad." />
            <textarea
              rows={3}
              placeholder="For example: Ask students to explain backpropagation before moving to other topics."
              aria-label="Professor notes"
              value={value.custom_notes}
              onChange={(e) => change("custom_notes", e.target.value)}
            />
          </label>
          <p className="help">These notes guide the AI’s questions and feedback, including concepts to emphasize or revisit.</p>
        </>
      ) : (
        <>
          <label>
            Milestone prompt
            <textarea
              data-publish-target="milestone-prompt"
              aria-invalid={publishIssue?.target === "milestone-prompt" || undefined}
              rows={5}
              placeholder="What was your biggest challenge this week, and what solution did you try?"
              value={value.milestone_prompt}
              onChange={(e) => change("milestone_prompt", e.target.value)}
            />
          </label>
          {publishIssue?.target === "milestone-prompt" && <p className="publish-inline-error">{publishIssue.message}</p>}
          <p className="help">Students see this prompt when they open the reflection. Ask them to describe a challenge and the solution they tried.</p>
          <label>
            Historical responses (CSV)
            <input
              data-publish-target="historical-csv"
              aria-invalid={publishIssue?.target === "historical-csv" || undefined}
              type="file"
              accept=".csv,text/csv"
              onChange={async (e) => {
                const f = e.target.files[0];
                if (!f) return;
                if (f.size > 2_000_000) {
                  setError("Use a CSV smaller than 2 MB.");
                  return;
                }
                change("historical_data", await f.text());
                setError("");
              }}
            />
          </label>
          {publishIssue?.target === "historical-csv" && <p className="publish-inline-error">{publishIssue.message}</p>}
          <p className="help">
            Required columns: name, challenge, solution. Historical responses
            are used for recommendations and are not exposed as assignment
            configuration to students.
          </p>
          {value.historical_data && (
            <p className="notice">
              Historical CSV attached (
              {Math.round(value.historical_data.length / 1024)} KB).
            </p>
          )}
        </>
      )}
    </>
  );
}
