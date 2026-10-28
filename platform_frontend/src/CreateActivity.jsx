import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, TOOLS, date } from "./api";
import { SocraticConfig, ReflectionConfig, defaults } from "./ToolConfig";
import { GenerationStatus, Notice } from "./ui";
import LessonPreview from "./LessonPreview";
import ActivityRail from "./ActivityRail";
import ActivityIcon from "./ActivityIcon";
import ActivityTutorial from "./ActivityTutorial";
import { loadCourseContext } from "./courseContext";

const initial = {
  course_id: "",
  title: "",
  instructions: "",
  due: "",
  tool: "",
  config: {},
};
const ACTIVITY_TYPES = [
  "socratic",
  "reflections",
  "self-directed-learning",
  "debate",
  "aiducate",
];
const configFor = (tool) =>
  structuredClone(
    defaults[tool] ||
      (tool === "debate"
        ? { scenario: "", minimum_messages: 3 }
        : { prompt: "" }),
  );
function restoreDraft(item) {
  if (!item) return initial;
  const d = item.due_at ? new Date(item.due_at) : null;
  return {
    ...item,
    due: d
      ? new Date(d.getTime() - d.getTimezoneOffset() * 60000)
          .toISOString()
          .slice(0, 16)
      : "",
  };
}
export default function CreateActivity({
  initialActivity = null,
  initialContext = null,
}) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(() => restoreDraft(initialActivity));
  const [initializing, setInitializing] = useState(!initialActivity);
  const [courses, setCourses] = useState(
    initialContext ? [initialContext] : [],
  );
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState(
    initialActivity?.config.document_ids || [],
  );
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [error, setError] = useState("");
  const [setupError, setSetupError] = useState("");
  const [notice, setNotice] = useState("");
  const [publishIssue, setPublishIssue] = useState(null);
  const [showTutorial, setShowTutorial] = useState(false);
  const [coursePickerOpen, setCoursePickerOpen] = useState(false);
  const fileInput = useRef(null);
  const tutorialButton = useRef(null);
  const chatConfigs = useRef({});
  const settingsRef = useRef(null);
  const reviewRef = useRef(null);
  const feedbackRef = useRef(null);
  useEffect(() => {
    if (initialActivity && initialContext && initialActivity.id === id) return;
    // Saving a new draft already loaded this item; do not overwrite later chat selections.
    if (id && draft.id === id && courses.length) return;
    let active = true;
    setInitializing(true);
    const load = async () => {
      const item = id ? await api(`/platform/assignments/${id}`) : null;
      const requestedCourse = new URLSearchParams(window.location.search).get("course");
      const context = item || requestedCourse
        ? await loadCourseContext(item?.course_id || requestedCourse)
        : initialContext || await loadCourseContext().catch(() => null);
      const available = item ? [context] : (await api("/courses")).courses.filter(
        (course) => course.membership_role === "instructor" && course.membership_status === "approved",
      );
      if (!active) return;
      if (item && String(item.course_id) !== String(context.course_id))
        throw Error("Open this activity from its Canvas course.");
      setCourses(available);
      if (!item) {
        const selectedCourse = context?.course_id || (available.length === 1 ? available[0].course_id : "");
        if (selectedCourse && !available.some((course) => String(course.course_id) === String(selectedCourse)))
          throw Error("You do not manage the selected course.");
        setDraft((d) => ({ ...d, course_id: selectedCourse }));
        return;
      }
      const d = item.due_at ? new Date(item.due_at) : null;
      setDraft({
        ...item,
        due: d
          ? new Date(d.getTime() - d.getTimezoneOffset() * 60000)
              .toISOString()
              .slice(0, 16)
          : "",
      });
      setSelected(item.config.document_ids || []);
      if (item.status !== "draft") setStage(3);
    };
    load()
      .catch((e) => active && setError(e.message))
      .finally(() => active && setInitializing(false));
    return () => {
      active = false;
    };
  }, [id]);
  useEffect(() => {
    let active = true;
    setFiles([]);
    if (!draft.course_id) {
      setLoadingFiles(false);
      return;
    }
    setLoadingFiles(true);
    api(`/platform/courses/${draft.course_id}/documents`)
      .then((data) => {
        if (active) setFiles(data.files);
      })
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoadingFiles(false));
    return () => {
      active = false;
    };
  }, [draft.course_id]);
  const change = (key, value) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setStage(1);
    setPublishIssue(null);
    setError("");
  };
  const chooseCourse = (courseId) => {
    if (!courses.some((course) => String(course.course_id) === courseId)) return;
    if (String(draft.course_id) !== courseId) {
      chatConfigs.current = {};
      setSelected([]);
      setFiles([]);
      setSearch("");
      setDraft((current) => ({ ...current, course_id: courseId, config: current.tool ? configFor(current.tool) : {} }));
      setStage(1);
      setPublishIssue(null);
      setError("");
      setNotice("Course changed. Select materials from this course before publishing.");
    }
    setCoursePickerOpen(false);
  };
  const setConfig = (value) => {
    setDraft((d) => ({ ...d, config: value }));
    setStage(2);
    setPublishIssue(null);
    setError("");
  };
  const chooseTool = (key) => {
    chatConfigs.current[draft.tool] = draft.config;
    setDraft((d) => ({
      ...d,
      tool: key,
      config:
        d.tool === key
          ? d.config
          : structuredClone(chatConfigs.current[key] || configFor(key)),
    }));
    setStage(2);
    setNotice("");
    setPublishIssue(null);
    setError("");
  };
  const ready = !!draft.title.trim() && !!draft.course_id && !!draft.tool;
  const connected = draft.tool !== "aiducate";
  const frozen = draft.status && draft.status !== "draft";
  const closeTutorial = () => {
    setShowTutorial(false);
    requestAnimationFrame(() => tutorialButton.current?.focus({ preventScroll: true }));
  };
  const run = async (fn, label = "Saving activity") => {
    setBusy(true);
    setBusyLabel(label);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      setBusyLabel("");
    }
  };
  const save = async (publish, quiet = false) => {
    const config =
      draft.tool === "debate"
        ? {
            document_ids: selected,
            scenario: draft.config.scenario || draft.title,
            opening_prompt: draft.config.opening_prompt || "",
            minimum_messages: draft.config.minimum_messages || 3,
          }
        : draft.tool === "self-directed-learning"
          ? {
              document_ids: selected,
              prompt: draft.config.prompt || "",
              custom_questions: draft.config.custom_questions || [],
              learning_plan: draft.config.learning_plan || {},
            }
          : draft.tool === "socratic"
            ? { ...draft.config, guidance_mode: draft.config.guidance_mode || (draft.config.learning_steps?.length ? "guided" : "basic"), learning_steps: draft.config.guidance_mode === "basic" ? [] : (draft.config.learning_steps || []), document_ids: selected }
            : { ...draft.config, document_ids: selected };
    const payload = {
      course_id: draft.course_id,
      title: draft.title,
      instructions: draft.instructions,
      due_at: draft.due ? new Date(draft.due).toISOString() : null,
      tool: draft.tool,
      audience: "course",
      config,
    };
    const saved = await api(
      `/platform/assignments${draft.id ? `/${draft.id}` : ""}`,
      { method: draft.id ? "PUT" : "POST", body: payload },
    );
    setDraft((d) => ({ ...d, ...saved }));
    if (publish) {
      await api(`/platform/assignments/${saved.id}/publish`, {
        method: "POST",
      });
      navigate(`/professor/activities/${saved.id}`, { state: { showStudentPreview: true } });
    } else if (!quiet) {
      navigate("/professor", { state: { notice: "Draft saved." } });
    }
    return saved;
  };
  const review = () =>
    run(async () => {
      if (draft.tool === "self-directed-learning") {
        const saved = await save(false, true);
        const prepared = await api(
          `/platform/assignments/${saved.id}/prepare-sdl`,
          { method: "POST" },
        );
        setDraft((d) => ({
          ...d,
          ...saved,
          config: { ...saved.config, learning_plan: prepared.learning_plan },
        }));
      }
      setStage(3);
      setNotice(
        "Review the activity below, then select Publish activity to confirm.",
      );
      requestAnimationFrame(() =>
        reviewRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        }),
      );
    }, draft.tool === "self-directed-learning" ? "Generating lesson review" : "Preparing activity review");
  const generateSocraticSetup = () =>
    run(async () => {
      setSetupError("");
      if (!selected.length)
        throw new Error("Select at least one indexed course document before generating the setup.");
      let generated;
      try {
        generated = await api(`/courses/${draft.course_id}/socratic-setup/generate`, {
          method: "POST",
          body: {
            document_ids: selected,
            title: draft.title,
            assignment_instructions: draft.instructions,
          },
        });
      } catch (exc) {
        setSetupError(exc.message);
        throw exc;
      }
      setDraft((current) => ({
        ...current,
        instructions: generated.instructions,
        keyword_preparation: null,
        config: {
          ...current.config,
          scope_mode: "assignment",
          guidance_mode: "guided",
          keywords: [],
          optional_keywords: [],
          prompt: generated.prompt,
          minimum_messages: generated.minimum_messages,
          learning_steps: generated.learning_steps || [],
        },
      }));
      setStage(2);
      setPublishIssue(null);
      const briefSteps = generated.brief_steps_needing_review || (generated.first_example_needs_review ? [1] : []);
      setNotice(`AI drafted ${(generated.learning_steps || []).length} learning steps from ${(generated.source_files || []).join(", ")}. ${briefSteps.length ? `Steps ${briefSteps.join(", ")} need a more detailed scene before publishing.` : "Review each scene and question before publishing."}`);
    }, "Generating setup from selected documents");
  const generateSocraticOpening = () =>
    run(async () => {
      if (!selected.length)
        throw new Error("Select at least one indexed course document before generating an opening question.");
      const generated = await api(`/courses/${draft.course_id}/socratic-opening/generate`, {
        method: "POST",
        body: {
          document_ids: selected,
          title: draft.title,
          assignment_instructions: draft.instructions,
        },
      });
      setDraft((current) => ({
        ...current,
        config: { ...current.config, prompt: generated.prompt },
      }));
      setNotice("AI drafted an opening question from your selected documents. Review or edit it before publishing.");
    }, "Generating opening question from selected documents");
  const upload = async (event) => {
    const uploads = [...event.target.files];
    event.target.value = "";
    if (!uploads.length) return;
    setUploading(true);
    setBusy(true);
    setBusyLabel("Uploading and indexing course materials");
    setError("");
    setUploadError("");
    setNotice("");
    try {
      const body = new FormData();
      uploads.forEach((f) => body.append("files", f));
      const result = await api(
        `/platform/courses/${draft.course_id}/documents/upload`,
        { method: "POST", body },
      );
      const data = await api(`/platform/courses/${draft.course_id}/documents`);
      setFiles(data.files);
      const savedIds = new Set(data.files.map((file) => String(file.file_id)));
      if (!Array.isArray(result.files) || result.files.some((file) => !savedIds.has(String(file.file_id || file.id)))) {
        throw new Error("The upload request finished, but the document is not in this course's library. Please retry or contact the administrator.");
      }
      const uploadedIds = new Set(result.files.map((file) => String(file.file_id || file.id)));
      setSelected((current) => [
        ...new Set([
          ...current,
          ...data.files
            .filter((file) => uploadedIds.has(String(file.file_id)) && file.document_id)
            .map((file) => file.document_id),
        ]),
      ]);
      setStage(1);
      setNotice("Documents uploaded and ready to select.");
      setPublishIssue(null);
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
      setBusy(false);
      setBusyLabel("");
    }
  };
  const deleteDocument = (file) => {
    if (
      !window.confirm(
        `Delete ${file.filename} from this course? Published assignments keep their saved copy.`,
      )
    )
      return;
    run(async () => {
      await api(
        `/courses/${draft.course_id}/documents/${file.file_id}`,
        { method: "DELETE" },
      );
      setFiles((current) =>
        current.filter((item) => item.file_id !== file.file_id),
      );
      if (file.document_id)
        setSelected((current) =>
          current.filter((documentId) => documentId !== file.document_id),
        );
      setDraft((current) => ({
        ...current,
        keyword_preparation: null,
      }));
      setStage(1);
      setNotice(`${file.filename} was deleted.`);
    });
  };
  if (initializing)
    return (
      <>
        <Link className="back" to="/professor">
          ← All assignments
        </Link>
        <GenerationStatus message={id ? "Loading saved activity…" : "Opening activity creation…"} fullScreen />
      </>
    );
  const focusPublishIssue = (issue) => {
    setPublishIssue(issue);
    requestAnimationFrame(() => {
      const selectors = {
        course: '[data-publish-target="course"]',
        title: '[data-publish-target="title"]',
        activity: '[data-activity-tutorial="activity"] .activity-choice',
        "learning-path": '[data-publish-target="learning-path"] .socratic-generate-setup',
        "debate-scenario": '[data-publish-target="debate-scenario"]',
        "reflection-subtopics": '[data-publish-target="reflection-subtopics"]',
        "milestone-prompt": '[data-publish-target="milestone-prompt"]',
        "historical-csv": '[data-publish-target="historical-csv"]',
      };
      const selector = selectors[issue.target];
      const target = issue.target === "materials"
        ? document.querySelector('.activity-document-row input:not(:disabled)')
          || document.querySelector('[data-activity-tutorial="materials"] .activity-material-heading button')
        : selector ? document.querySelector(selector) : null;
      const destination = target?.disabled
        ? document.querySelector('input[name="socratic-guidance-mode"][value="guided"]')
        : target;
      (destination || feedbackRef.current)?.scrollIntoView?.({ behavior: "smooth", block: "center" });
      (destination || feedbackRef.current)?.focus({ preventScroll: true });
    });
  };
  const serverPublishIssue = (message) => {
    if (/learning.step|learning.path|guidance_mode/i.test(message)) return "learning-path";
    if (/document|course material|indexed|embedding/i.test(message)) return "materials";
    if (/sub.?topic/i.test(message)) return "reflection-subtopics";
    if (/milestone.*prompt/i.test(message)) return "milestone-prompt";
    if (/historical|csv|required columns/i.test(message)) return "historical-csv";
    if (/scenario/i.test(message)) return "debate-scenario";
    if (/title/i.test(message)) return "title";
    if (/chatbot|activity type|aiducate/i.test(message)) return "activity";
    return null;
  };
  const publishActivity = () => {
    const missing = [];
    if (!draft.title.trim()) missing.push({ target: "title", message: "Enter an activity title." });
    if (!draft.course_id)
      missing.push({ target: "course", message: "Choose a course for this assignment." });
    if (!draft.tool) missing.push({ target: "activity", message: "Select an activity type." });
    if (
      ["socratic", "self-directed-learning"].includes(draft.tool) &&
      !selected.length
    )
      missing.push({ target: "materials", message: "Select at least one indexed course document or upload course materials." });
    if (draft.tool === "socratic" && draft.config.guidance_mode === "guided" && !(draft.config.learning_steps || []).length)
      missing.push({ target: "learning-path", message: "Generate a learning path before publishing Guided learning path, or choose Basic conversation." });
    if (
      draft.tool === "debate" &&
      (draft.config.scenario || draft.title).trim().length < 10
    )
      missing.push({ target: "debate-scenario", message: "Enter a Debate scenario of at least 10 characters." });
    if (draft.tool === "reflections") {
      if (draft.config.module_type === "milestone_based") {
        if (!draft.config.milestone_prompt?.trim())
          missing.push({ target: "milestone-prompt", message: "Enter the milestone reflection prompt." });
        if (!draft.config.historical_data?.trim())
          missing.push({ target: "historical-csv", message: "Upload the historical CSV for milestone reflections." });
      } else if (!(draft.config.sub_topics || []).some((topic) => topic.trim()))
        missing.push({ target: "reflection-subtopics", message: "Add at least one reflection sub-topic." });
    }
    if (draft.tool === "aiducate")
      missing.push({ target: "activity", message: "AIducate needs a backend connection before publishing. You can save a draft." });
    if (missing.length) {
      setError(missing.map(({ message }) => message).join(" "));
      setNotice("");
      focusPublishIssue(missing[0]);
      return;
    }
    setPublishIssue(null);
    if (stage === 3) run(async () => {
      try {
        await save(true);
      } catch (error) {
        const target = serverPublishIssue(error.message);
        if (target) focusPublishIssue({ target, message: error.message });
        throw error;
      }
    });
    else review();
  };
  const course = courses.find((c) => c.course_id === draft.course_id);
  return (
    <>
      <Link className="back" to="/professor">
        ← All assignments
      </Link>
      <div className="page-heading">
        <div>
          <p className="context">Professor studio</p>
          <h1>Assignment Configuration</h1>
          <p>
            Confirm the assignment details, add materials, choose an
            activity, then review and publish.
          </p>
        </div>
      </div>
      <div ref={feedbackRef} tabIndex={-1}>
        <Notice error={error} />
        <Notice>{notice}</Notice>
      </div>
      {busy && <GenerationStatus message={busyLabel || "Working on your activity"} fullScreen />}
      {showTutorial && <ActivityTutorial tool={draft.tool} onClose={closeTutorial} />}
      <fieldset className="editor-fieldset" disabled={busy || frozen}>
        <section className="panel">
          <div className="activity-details-heading">
            <h2>Activity details</h2>
            <button ref={tutorialButton} type="button" className="compact" aria-label="Open assignment tutorial" onClick={() => setShowTutorial(true)}>Tutorial</button>
          </div>
          {!id && !draft.id && <div className="activity-course-choice">
            <div>
              <strong>Course</strong>
              <p>{course ? `${course.course_code} — ${course.title}` : "No course selected"}</p>
              <small>Students and course materials will come from the selected course.</small>
            </div>
            {!new URLSearchParams(window.location.search).has("course") && <button type="button" className="secondary compact" data-publish-target="course"
              aria-expanded={coursePickerOpen} aria-controls="activity-course-picker"
              onClick={() => setCoursePickerOpen((open) => !open)}>
              {draft.course_id ? "Change course" : "Choose course"}
            </button>}
            {coursePickerOpen && <div id="activity-course-picker" className="activity-course-picker">
              <label>Choose an existing course
                <select value={draft.course_id} onChange={(event) => chooseCourse(event.target.value)}>
                  <option value="">Select a course</option>
                  {courses.map((item) => <option key={item.course_id} value={item.course_id}>
                    {item.course_code} — {item.title}
                  </option>)}
                </select>
              </label>
              {!courses.length && <p className="help">No courses you teach are available yet.</p>}
            </div>}
          </div>}
          <div className="activity-title-date-row">
            <div>
              <label data-activity-tutorial="title">
                Assignment title
                <input
                  data-publish-target="title"
                  aria-invalid={publishIssue?.target === "title" || undefined}
                  maxLength={200}
                  value={draft.title}
                  onChange={(e) => change("title", e.target.value)}
                  placeholder="Enter activity title"
                />
              </label>
              {publishIssue?.target === "title" && <span className="publish-inline-error">{publishIssue.message}</span>}
            </div>
            <label data-activity-tutorial="due">
              Due date
              <input
                type="datetime-local"
                value={draft.due}
                onInput={(e) => change("due", e.currentTarget.value)}
                onChange={(e) => change("due", e.target.value)}
              />
            </label>
          </div>
          <p className="help">
            Canvas assignment launches apply the assignment title and due date
            automatically. You can enter them here for assignments created
            directly in ClubALL.
          </p>
          <label data-activity-tutorial="instructions">
              {draft.tool === "socratic" ? "Student instructions and submission" : "Description"}
            <textarea
              rows={4}
              value={draft.instructions}
              onChange={(e) => change("instructions", e.target.value)}
              placeholder="Describe the activity and what students should do."
            />
          </label>
            {draft.tool === "socratic" && (
              <p className="help">Describe what students do in this chat and any Canvas submission. BrainTutor completion does not submit files to Canvas.</p>
            )}
        </section>
        <section className="panel" data-activity-tutorial="materials">
          <h2>Course materials</h2>
          {publishIssue?.target === "materials" && <p className="publish-inline-error">{publishIssue.message}</p>}
          <div className="activity-material-heading">
            <h3>Existing documents</h3>
            <button
              type="button"
              disabled={!draft.course_id || busy || uploading}
              onClick={() => fileInput.current.click()}
            >
              {uploading ? "Processing documents…" : "Upload new documents"}
            </button>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept=".txt,.md,.pdf,.py,.tex,.latex,.html,.htm,.doc,.docx,.ppt,.pptx"
              hidden
              onChange={upload}
            />
          </div>
          <Notice error={uploadError} />
          <label>
            Search documents
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by document name"
            />
          </label>
          <div
            className="activity-document-list"
            aria-label="Existing documents"
          >
            {loadingFiles ? (
              <p role="status">Loading documents…</p>
            ) : (
              files
                .filter((f) =>
                  f.filename.toLowerCase().includes(search.toLowerCase()),
                )
                .sort((a, b) => a.filename.localeCompare(b.filename))
                .map((f) => (
                  <div className="activity-document-row" key={f.file_id}>
                    <label className="check">
                      <input
                        type="checkbox"
                        disabled={!f.document_id}
                        checked={selected.includes(f.document_id)}
                        onChange={(e) => {
                          setSelected((s) =>
                            e.target.checked
                              ? [...s, f.document_id]
                              : s.filter((v) => v !== f.document_id),
                          );
                          setStage(1);
                          setPublishIssue(null);
                          setError("");
                        }}
                      />
                      <span>
                        {f.filename}
                        {!f.document_id && <small>Not indexed</small>}
                      </span>
                      <small>{Math.round((f.file_size || 0) / 1024)} KB</small>
                    </label>
                    <button
                      type="button"
                      className="quiet activity-document-delete"
                      aria-label={`Delete ${f.filename}`}
                      onClick={() => deleteDocument(f)}
                    >
                      Delete
                    </button>
                  </div>
                ))
            )}
            {!loadingFiles && !files.length && (
              <p className="help">
                {draft.course_id
                  ? "No documents yet. Upload course materials to get started."
                  : "Loading course materials from your Canvas context."}
              </p>
            )}
          </div>
          <div className="activity-material-heading">
            <h3>Selected documents ({selected.length})</h3>
            {selected.length > 0 && (
              <button
                className="quiet"
                onClick={() => {
                  setSelected([]);
                  setStage(1);
                  setPublishIssue(null);
                  setError("");
                }}
              >
                Clear all
              </button>
            )}
          </div>
          {selected.length ? (
            <ul className="activity-selected-list">
              {files
                .filter((f) => selected.includes(f.document_id))
                .map((f) => (
                  <li key={f.file_id}>
                    {f.filename}
                    <button
                      className="quiet"
                      aria-label={`Remove ${f.filename}`}
                      onClick={() => {
                        setSelected((s) =>
                          s.filter((v) => v !== f.document_id),
                        );
                        setStage(1);
                        setPublishIssue(null);
                        setError("");
                      }}
                    >
                      ×
                    </button>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="help">No documents selected.</p>
          )}
        </section>
        <section className="panel" data-activity-tutorial="activity">
          <h2>Select activity</h2>
          {publishIssue?.target === "activity" && <p className="publish-inline-error">{publishIssue.message}</p>}
          <ActivityRail label="activity choices" className="activity-rail">
            {ACTIVITY_TYPES.map((key, index) => {
              const tool = TOOLS[key];
              return (
                <button
                  key={key}
                  aria-pressed={draft.tool === key}
                  style={{ "--tool-color": tool.color }}
                  className={`tool-card activity-choice ${draft.tool === key ? "is-selected" : ""}`}
                  onClick={() => chooseTool(key)}
                >
                  <span className="tool-card-topline">
                    <span className="tool-mark">
                      <ActivityIcon tool={key} />
                    </span>
                    {draft.tool === key ? (
                      <span className="activity-selected-indicator" aria-hidden="true"><span>✓</span> Selected</span>
                    ) : (
                      <span className="tool-step" aria-hidden="true">0{index + 1}</span>
                    )}
                  </span>
                  <span className="tool-mode">
                    {
                      {
                        socratic: "Guide",
                        reflections: "Reflect",
                        "self-directed-learning": "Learn",
                        debate: "Discuss",
                        aiducate: "Explore",
                      }[key]
                    }
                  </span>
                  <strong>{tool.name}</strong>
                  <span className="activity-choice-description">
                    {tool.description}
                  </span>
                </button>
              );
            })}
          </ActivityRail>
        </section>
        {draft.tool && (
          <section className="panel activity-settings" ref={settingsRef} data-activity-tutorial="settings">
            <h2>{TOOLS[draft.tool].name} settings</h2>
            {draft.tool === "socratic" ? (
              <SocraticConfig
                value={{ ...draft.config, document_ids: selected }}
                onChange={setConfig}
                courseId={draft.course_id}
                frozen={frozen}
                hideDocuments
                documents={files}
                onGenerateSetup={generateSocraticSetup}
                onGenerateOpening={generateSocraticOpening}
                publishIssue={publishIssue}
                setupError={setupError}
                generatingSetup={busy}
                canGenerateSetup={Boolean(draft.title.trim() && selected.length && selected.length <= 12 && !busy)}
                onMaterialsChange={({ files: nextFiles }) => {
                  setFiles(nextFiles);
                  const available = new Set(
                    nextFiles
                      .filter((file) => file.document_id)
                      .map((file) => file.document_id),
                  );
                  setSelected((current) =>
                    current.filter((documentId) =>
                      available.has(documentId),
                    ),
                  );
                }}
              />
            ) : draft.tool === "reflections" ? (
              <ReflectionConfig value={draft.config} onChange={setConfig} publishIssue={publishIssue} />
            ) : draft.tool === "self-directed-learning" ? (
              <>
                <label>
                  Learning focus
                  <textarea
                    rows={3}
                    value={draft.config.prompt || ""}
                    onChange={(e) =>
                      setConfig({ ...draft.config, prompt: e.target.value })
                    }
                    placeholder="What should students learn from these materials?"
                  />
                </label>
                <label>
                  Sub-questions
                  <textarea
                    aria-label="Sub-questions"
                    rows={5}
                    value={(draft.config.custom_questions || []).join("\n")}
                    onChange={(e) =>
                      setConfig({
                        ...draft.config,
                        custom_questions: e.target.value.split("\n"),
                      })
                    }
                    placeholder="Enter one question per line"
                  />
                  <span className="help">
                    These questions guide the generated lesson. Review the
                    lesson before publishing.
                  </span>
                </label>
              </>
            ) : (
              <>
                <label>
                  {draft.tool === "debate"
                    ? "Debate topic or scenario"
                    : "Activity instructions"}
                  <textarea
                    data-publish-target={draft.tool === "debate" ? "debate-scenario" : undefined}
                    aria-invalid={publishIssue?.target === "debate-scenario" || undefined}
                    rows={4}
                    value={draft.config.scenario || draft.config.prompt || ""}
                    onChange={(e) =>
                      setConfig({
                        ...draft.config,
                        [draft.tool === "debate" ? "scenario" : "prompt"]:
                          e.target.value,
                      })
                    }
                  />
                </label>
                {publishIssue?.target === "debate-scenario" && <p className="publish-inline-error">{publishIssue.message}</p>}
                <p className="help">
                  {draft.tool === "aiducate"
                    ? "AIducate has no backend yet. You can save a draft."
                    : draft.tool === "self-directed-learning"
                      ? "Select course materials above. Review activity generates the adaptive lesson for you to check before publishing."
                      : "Students discuss this scenario with the Debate chatbot."}
                </p>
              </>
            )}
          </section>
        )}
        <div className="editor-actions" data-activity-tutorial="publish">
          <button
            className="secondary"
            disabled={!ready}
            onClick={() => run(() => save(false))}
          >
            Save draft
          </button>
          <button
            className="secondary"
            disabled={
              !ready ||
              (draft.tool === "self-directed-learning" && !selected.length)
            }
            onClick={review}
          >
            {busy ? "Preparing…" : "Review activity"}
          </button>
          <button onClick={publishActivity}>Publish activity</button>
        </div>
        {!connected && (
          <p className="help">
            AIducate is available for draft testing; publishing needs its
            backend connection.
          </p>
        )}
        {draft.tool === "self-directed-learning" && !selected.length && (
          <p className="help">
            Select course materials to review or publish an SDL lesson.
          </p>
        )}
        {stage === 3 && (
          <section className="panel activity-review" ref={reviewRef}>
            <h2>Review and publish</h2>
            <dl className="activity-summary">
              <dt>Activity</dt>
              <dd>{draft.title}</dd>
              <dt>Course</dt>
              <dd>
                {course?.course_code} — {course?.title}
              </dd>
              <dt>Due date</dt>
              <dd>{draft.due ? date(draft.due) : "No due date"}</dd>
              <dt>Description</dt>
              <dd>{draft.instructions || "No description"}</dd>
              {draft.tool === "socratic" && (
                <>
                  <dt>Teaching scope</dt>
                  <dd>Entire selected assignment materials</dd>
                  <dt>Tutor guidance</dt>
                  <dd>{(draft.config.guidance_mode || (draft.config.learning_steps?.length ? "guided" : "basic")) === "guided" ? "Guided learning path" : "Basic conversation"}</dd>
                  <dt>Opening question</dt>
                  <dd>{draft.config.prompt || "Generated from course materials"}</dd>
                  {(draft.config.guidance_mode || (draft.config.learning_steps?.length ? "guided" : "basic")) === "guided" && <><dt>Learning path</dt><dd>{draft.config.learning_steps?.length ? draft.config.learning_steps.map((step, index) => `${index + 1}. ${step.title}`).join(" → ") : "No generated steps"}</dd></>}
                  <dt>Messages before completion</dt>
                  <dd>{draft.config.minimum_messages ?? 1}</dd>
                </>
              )}
              <dt>Chat</dt>
              <dd>{TOOLS[draft.tool].name}</dd>
              <dt>Materials</dt>
              <dd>{selected.length} selected documents</dd>
              <dt>Assigned to</dt>
              <dd>All currently enrolled students</dd>
            </dl>
            {draft.tool === "self-directed-learning" &&
              draft.config.learning_plan && (
                <LessonPreview plan={draft.config.learning_plan} />
              )}
            <p className="help">
              Publishing freezes the activity settings and the current student
              recipient list.
            </p>
            {!connected && (
              <Notice>
                This chat must be connected before publishing. Your draft can be
                saved now.
              </Notice>
            )}
            {draft.tool === "socratic" && !selected.length && (
              <p className="help">
                Select at least one indexed document before publishing Socratic.
              </p>
            )}
          </section>
        )}
      </fieldset>
    </>
  );
}
