import { useEffect, useId, useRef, useState } from "react";
import { api } from "./api";
import { GenerationStatus, Notice } from "./ui";
import CourseLearningMaterials from "./CourseLearningMaterials";

export const defaults = {
  socratic: {
    scope_mode: "assignment",
    guidance_mode: "basic",
    keywords: [],
    optional_keywords: [],
    dismissed_keywords: [],
    document_ids: [],
    learning_steps: [],
    prompt: "",
    minimum_messages: 1,
  },
  debate: {
    document_ids: [],
    scenario: "",
    opening_prompt: "",
    minimum_messages: 3,
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
  "student-agent": { topic: null, provider: "openai", personality: "confused" },
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
  const guidanceMode = value.guidance_mode || (value.learning_steps?.length ? "guided" : "basic");
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
      <fieldset className="socratic-guidance-mode">
        <legend>How should the tutor guide students?</legend>
        <label>
          <input type="radio" name="socratic-guidance-mode" value="basic" checked={guidanceMode === "basic"} disabled={frozen} onChange={() => change("guidance_mode", "basic")} />
          <span><strong>Basic conversation</strong><small>Use the selected documents and your opening question. Students choose where the discussion goes.</small></span>
        </label>
        <label>
          <input type="radio" name="socratic-guidance-mode" value="guided" checked={guidanceMode === "guided"} disabled={frozen} onChange={() => change("guidance_mode", "guided")} />
          <span><strong>Guided learning path</strong><small>Generate and review ordered steps from the selected documents. Students work through them one by one.</small></span>
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
            AI drafts a beginning-to-end learning path, opening question, student/submission instructions, and a completion-message count from the selected indexed documents. Review and edit these before publishing.
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
          <p className="help">Scan the path below. Select a step to edit its details, or drag a row or use the arrows to change the order. Students can still ask related questions at any point.</p>
          {!value.learning_steps?.length && <p className="help">No steps generated yet. Generate the guided setup before publishing.</p>}
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
                <label>{index === 0 ? "First example students will see" : "Detailed scene students will see"}
                  <textarea rows={5} maxLength={700} value={step.scenario || ""} disabled={frozen}
                    onChange={(event) => updateStep("scenario", event.target.value)}
                    placeholder={index === 0 ? "Set a concrete scene from the selected material: who is involved, what they are doing, and what they need to decide." : "Continue the same example: what happened before, what is happening now, and what decision remains?"} />
                </label>
                <p className="help">Give students enough context to picture this step before its question. Continue the same example, use only details supported by this step’s selected material, and leave the answer open.</p>
                <label>Question for this step<textarea rows={2} maxLength={500} value={step.question || ""} disabled={frozen} onChange={(event) => updateStep("question", event.target.value)} placeholder="What should the student reason about next?" /></label>
                <details className="socratic-step-evidence"><summary>View supporting passage</summary><p>{step.evidence_quote}</p></details>
              </div>}
            </li>;
          })}
          </ol>
        </section>}
        <label>
          Messages required before completion
          <input
            type="number"
            min={1}
            max={100}
            value={value.minimum_messages ?? 1}
            onChange={(e) =>
              change("minimum_messages", Number(e.target.value))
            }
          />
        </label>
        <p className="help">
          Students mark the assignment complete after the minimum number of
          messages.
        </p>
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

const blankTopic = () => ({
  id: `topic_${crypto.randomUUID().slice(0, 8)}`,
  name: "",
  resource: { title: "", url: "" },
  alt_resource: { title: "", url: "" },
  practice_label: "",
  practice_prompt: "",
  practice_stages: [{ label: "", focus: "" }],
  practice_options: [],
  check_questions: [],
  final_example: "",
});
function cleanTopic(topic) {
  const allowed = [
    "id",
    "name",
    "resource",
    "alt_resource",
    "practice_label",
    "practice_prompt",
    "practice_stages",
    "practice_options",
    "check_questions",
    "final_example",
    "number",
  ];
  return Object.fromEntries(
    Object.entries(topic).filter(([k]) => allowed.includes(k)),
  );
}
export function TutorConfig({ value, onChange, frozen }) {
  const [templates, setTemplates] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [topicName, setTopicName] = useState("");
  useEffect(() => {
    api("/platform/topic-templates")
      .then(setTemplates)
      .catch((e) => setError(e.message));
  }, []);
  const topic = value.topic,
    change = (k, v) => onChange({ ...value, [k]: v });
  const editTopic = (k, v) => change("topic", { ...topic, [k]: v });
  return (
    <>
      <Notice error={error} />
      <div className="form-columns">
        <label>
          Model provider
          <select
            value={value.provider}
            onChange={(e) => change("provider", e.target.value)}
          >
            <option value="openai">OpenAI</option>
            <option value="groq">Groq</option>
          </select>
        </label>
        {!frozen && (
          <label>
            Start from a topic
            <select
              value=""
              onChange={(e) => {
                const t = templates.find((t) => t.id === e.target.value);
                if (t) change("topic", cleanTopic(structuredClone(t)));
              }}
            >
              <option value="">Select a template</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {!frozen && (
        <div className="topic-tools">
          <button
            type="button"
            className="secondary"
            onClick={() => change("topic", blankTopic())}
          >
            Create custom topic
          </button>
          <label className="file-input">
            Import topic JSON
            <input
              type="file"
              accept=".json"
              onChange={async (e) => {
                try {
                  const f = e.target.files[0];
                  if (!f) return;
                  if (f.size > 100000)
                    throw new Error("Use a topic file smaller than 100 KB.");
                  const parsed = JSON.parse(await f.text());
                  if (
                    Array.isArray(parsed) ||
                    !parsed?.name ||
                    !parsed?.resource ||
                    !Array.isArray(parsed.practice_stages)
                  )
                    throw new Error(
                      "Import one topic object with a name, resources, and practice stages.",
                    );
                  change("topic", cleanTopic({ ...blankTopic(), ...parsed }));
                  setError("");
                } catch (err) {
                  setError(err.message);
                }
                e.target.value = "";
              }}
            />
          </label>
        </div>
      )}
      {!frozen && (
        <div className="generate-row">
          <label>
            Generate a topic draft
            <input
              value={topicName}
              onChange={(e) => setTopicName(e.target.value)}
              placeholder="e.g. Software requirements"
            />
          </label>
          <button
            type="button"
            className="secondary"
            disabled={busy || !topicName.trim()}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                const data = await api("/platform/generate-topic", {
                  method: "POST",
                  body: { name: topicName, provider: value.provider },
                });
                change("topic", cleanTopic({ ...blankTopic(), ...data.draft }));
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Generating…" : "Generate draft"}
          </button>
          {busy && <GenerationStatus message="Generating topic draft…" fullScreen />}
        </div>
      )}
      {topic ? (
        <div className="topic-editor">
          <label>
            Topic name
            <input
              value={topic.name}
              onChange={(e) => editTopic("name", e.target.value)}
            />
          </label>
          <div className="form-columns">
            {["resource", "alt_resource"].map((key, i) => (
              <div key={key}>
                <h3>{i ? "Alternative reading" : "Primary reading"}</h3>
                <label>
                  Resource title
                  <input
                    value={topic[key]?.title || ""}
                    onChange={(e) =>
                      editTopic(key, { ...topic[key], title: e.target.value })
                    }
                  />
                </label>
                <label>
                  Resource URL
                  <input
                    type="url"
                    value={topic[key]?.url || ""}
                    onChange={(e) =>
                      editTopic(key, { ...topic[key], url: e.target.value })
                    }
                  />
                </label>
              </div>
            ))}
          </div>
          <label>
            Practice label
            <input
              value={topic.practice_label || ""}
              onChange={(e) => editTopic("practice_label", e.target.value)}
            />
          </label>
          <label>
            Practice prompt
            <textarea
              rows={4}
              value={topic.practice_prompt || ""}
              onChange={(e) => editTopic("practice_prompt", e.target.value)}
            />
          </label>
          <h3>Practice stages</h3>
          {(topic.practice_stages || []).map((s, i) => (
            <div className="stage-row" key={i}>
              <label>
                Stage {i + 1}
                <input
                  value={s.label}
                  onChange={(e) =>
                    editTopic(
                      "practice_stages",
                      topic.practice_stages.map((x, j) =>
                        j === i ? { ...x, label: e.target.value } : x,
                      ),
                    )
                  }
                />
              </label>
              <label>
                Focus
                <input
                  value={s.focus}
                  onChange={(e) =>
                    editTopic(
                      "practice_stages",
                      topic.practice_stages.map((x, j) =>
                        j === i ? { ...x, focus: e.target.value } : x,
                      ),
                    )
                  }
                />
              </label>
              <button
                type="button"
                className="quiet"
                disabled={topic.practice_stages.length < 2}
                onClick={() =>
                  editTopic(
                    "practice_stages",
                    topic.practice_stages.filter((_, j) => j !== i),
                  )
                }
              >
                Remove
              </button>
            </div>
          ))}
          {!frozen && (
            <button
              type="button"
              className="secondary compact"
              onClick={() =>
                editTopic("practice_stages", [
                  ...topic.practice_stages,
                  { label: "", focus: "" },
                ])
              }
            >
              Add stage
            </button>
          )}
          <div className="form-columns">
            <Lines
              label="Practice scenarios"
              value={topic.practice_options}
              onChange={(v) => editTopic("practice_options", v)}
            />
            <Lines
              label="Check questions"
              value={topic.check_questions}
              onChange={(v) => editTopic("check_questions", v)}
            />
          </div>
          <label>
            Worked example (available at wrap-up)
            <textarea
              rows={5}
              value={topic.final_example || ""}
              onChange={(e) => editTopic("final_example", e.target.value)}
            />
          </label>
        </div>
      ) : (
        <p className="empty">
          Select a topic template, import one, or create your own.
        </p>
      )}
    </>
  );
}
