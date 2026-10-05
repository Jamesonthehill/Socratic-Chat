import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { api, SOCRATIC_URL, TOOLS, date, label } from "./api";
import { Notice, Badge } from "./ui";
import CanvasLinkedFiles from "./CanvasLinkedFiles";
import {
  SocraticConfig,
  ReflectionConfig,
  TutorConfig,
  defaults,
} from "./ToolConfig";

function localDate(value) {
  if (!value) return "";
  const d = new Date(value);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

function AssignmentSettings({ optional, children }) {
  if (!optional) return children;
  return (
    <details className="canvas-optional-settings">
      <summary>Customize details (optional)</summary>
      {children}
    </details>
  );
}

export default function AssignmentEditor() {
  const { tool, id } = useParams(),
    [query] = useSearchParams(),
    navigate = useNavigate();
  const [item, setItem] = useState(null),
    [students, setStudents] = useState([]);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [materialsRevision, setMaterialsRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setItem(null);
    setError("");
    const load =
      id === "new"
        ? Promise.resolve({
            course_id: query.get("course") || "",
            tool,
            title: "",
            instructions: "",
            due_at: null,
            audience: "course",
            recipient_ids: [],
            config: structuredClone(defaults[tool] || {}),
            status: "draft",
          })
        : api(`/platform/assignments/${id}`);
    load
      .then(async (data) => {
        if (data.tool !== tool)
          throw new Error(
            "This assignment belongs to a different tool. Return to the dashboard.",
          );
        if (active) setItem(data);
        if (data.course_id) {
          const enrolled = await api(
            `/instructor/enrolled-students?course_id=${data.course_id}`,
          );
          if (active) setStudents(enrolled);
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [id, tool]);
  const change = (key, value) => setItem((prev) => ({ ...prev, [key]: value }));
  const config = (value) => change("config", value);
  const perform = async (fn) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  async function save(publish = false) {
    const payload = Object.fromEntries(
      [
        "course_id",
        "tool",
        "title",
        "instructions",
        "due_at",
        "audience",
        "recipient_ids",
        "config",
      ].map((k) => [k, item[k] ?? (k === "recipient_ids" ? [] : null)]),
    );
    const saved = await api(
      `/platform/assignments${id === "new" ? "" : `/${id}`}`,
      { method: id === "new" ? "POST" : "PUT", body: payload },
    );
    setItem({ ...item, ...saved });
    try {
      if (publish) {
        await api(`/platform/assignments/${saved.id}/publish`, {
          method: "POST",
        });
        setItem(await api(`/platform/assignments/${saved.id}`));
        setNotice(
          item.audience === "course"
            ? "Published. Enrolled students can open this assignment, including students who enroll later."
            : item.recipient_ids?.length
              ? "Published. Selected students can now open this assignment."
              : "Published with no students selected. This assignment is not visible to students.",
        );
      } else setNotice("Draft saved.");
    } finally {
      // Preserve the saved draft on publish failure, without racing the detail fetch.
      if (id === "new")
        navigate(`/professor/tools/${tool}/assignments/${saved.id}`, {
          replace: true,
        });
    }
  }
  if (!TOOLS[tool]) return <Notice error="Unknown tool." />;
  if (!item)
    return (
      <>
        <Link to={`/professor/tools/${tool}`}>Back to dashboard</Link>
        <Notice error={error} />
        {!error && <p>Loading assignment…</p>}
      </>
    );
  const frozen = item.status !== "draft";
  const importedFromCanvas = query.get("from") === "canvas";
  const Config = {
    socratic: SocraticConfig,
    reflections: ReflectionConfig,
    "student-agent": TutorConfig,
  }[tool];
  return (
    <>
      <Link className="back" to={`/professor/tools/${tool}`}>
        ← {TOOLS[tool].name} dashboard
      </Link>
      <div className="page-heading">
        <div>
          <p className="context">{TOOLS[tool].name} configuration</p>
          <h1>{id === "new" ? "A new learning assignment" : item.title}</h1>
          <p>
            {frozen
              ? "Published settings are frozen. Duplicate this assignment to use different settings."
              : importedFromCanvas
                ? "Canvas filled in this assignment. You can publish it as-is or optionally adjust the settings below."
                : "Set the learning experience, choose your students, then publish."}
          </p>
        </div>
        <Badge value={item.status} />
      </div>
      <Notice error={error} />
      <Notice>{notice}</Notice>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          perform(() => save(false));
        }}
      >
        {importedFromCanvas && !frozen && (
          <section className="panel canvas-import-review">
            <h2>Ready to publish from Canvas</h2>
            <p>
              The title, instructions, due date, and chatbot settings are
              prefilled. You can publish without editing them.
            </p>
            <div className="canvas-import-instructions">
              <Markdown components={{ a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>
                {item.instructions || "No instructions were provided in Canvas."}
              </Markdown>
            </div>
          </section>
        )}
        {!frozen && id !== "new" && tool === "socratic" && item.config?.canvas_context && (
          <CanvasLinkedFiles
            assignmentId={id}
            onImported={() => setMaterialsRevision((revision) => revision + 1)}
          />
        )}
        <AssignmentSettings optional={importedFromCanvas && !frozen}>
          <fieldset disabled={busy || frozen} className="editor-fieldset">
            <div className="editor-grid">
              <section className="panel">
                <h2>Assignment details</h2>
                <label>
                  Title
                  <input
                    required
                    maxLength={200}
                    value={item.title}
                    onChange={(e) => change("title", e.target.value)}
                    placeholder="e.g. Week 3: Requirements in practice"
                  />
                </label>
                <label>
                  Assigned chatbot
                  <input value={TOOLS[item.tool].name} readOnly />
                </label>
                <label>
                  Instructions
                  <textarea
                    rows={4}
                    value={item.instructions}
                    onChange={(e) => change("instructions", e.target.value)}
                    placeholder="What should students focus on?"
                  />
                </label>
                <label>
                  Due date (your local time)
                  <input
                    type="datetime-local"
                    value={localDate(item.due_at)}
                    onChange={(e) =>
                      change(
                        "due_at",
                        e.target.value
                          ? new Date(e.target.value).toISOString()
                          : null,
                      )
                    }
                  />
                </label>
                <p className="help">
                  Due dates are shown as guidance; students may continue after
                  the due date.
                </p>
              </section>
              <section className="panel">
                <h2>Who receives this?</h2>
                <label>
                  Assign to
                  <select
                    value={item.audience}
                    onChange={(e) => change("audience", e.target.value)}
                  >
                    <option value="course">All enrolled students</option>
                    <option value="selected">Selected students</option>
                  </select>
                </label>
                <p className="help">
                  You can publish before students enroll. All enrolled students,
                  including those who join later, can access a course-wide
                  assignment. For selected students, only those chosen before
                  publishing can access it.
                </p>
                {item.audience === "selected" && (
                  <div className="student-options">
                    {students.map((s) => (
                      <label className="check" key={s.user_id}>
                        <input
                          type="checkbox"
                          checked={
                            item.recipient_ids?.includes(s.user_id) || false
                          }
                          onChange={(e) =>
                            change(
                              "recipient_ids",
                              e.target.checked
                                ? [...(item.recipient_ids || []), s.user_id]
                                : item.recipient_ids.filter(
                                    (x) => x !== s.user_id,
                                  ),
                            )
                          }
                        />
                        <span>
                          {s.display_name || s.email}
                          <small>{s.email}</small>
                        </span>
                      </label>
                    ))}
                    {!students.length && (
                      <p>No enrolled students yet. To make this available when
                        students enroll, choose “All enrolled students” before
                        publishing.</p>
                    )}
                  </div>
                )}
                <a href={`${SOCRATIC_URL}?manage=1`}>
                  Manage course enrollment
                </a>
              </section>
            </div>
            <section className="panel tool-config">
              <h2>{TOOLS[tool].name} settings</h2>
              <Config
                value={item.config}
                onChange={config}
                courseId={item.course_id}
                materialsRevision={materialsRevision}
                frozen={frozen}
              />
            </section>
          </fieldset>
        </AssignmentSettings>
        <div className="editor-actions">
          {!frozen ? (
            <>
              <button className="secondary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save draft"}
              </button>
              <button
                type="button"
                disabled={busy || !item.title.trim() || !item.course_id}
                onClick={() => perform(() => save(true))}
              >
                Publish assignment
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  perform(async () => {
                    const copy = await api(
                      `/platform/assignments/${id}/duplicate`,
                      { method: "POST" },
                    );
                    navigate(`/professor/tools/${tool}/assignments/${copy.id}`);
                  })
                }
              >
                Duplicate as draft
              </button>
              {item.status !== "archived" && (
                <button
                  className="secondary"
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    perform(async () => {
                      await api(`/platform/assignments/${id}/archive`, {
                        method: "POST",
                      });
                      change("status", "archived");
                      setNotice(
                        "Archived. Students can no longer open this assignment.",
                      );
                    })
                  }
                >
                  Archive assignment
                </button>
              )}
            </>
          )}
        </div>
      </form>
      {frozen && (
        <section className="section">
          <h2>Student progress</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Progress</th>
                  <th>Completed</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {(item.students || []).map((s) => (
                  <tr key={s.student_id}>
                    <td>{s.display_name || s.username}</td>
                    <td>
                      <Badge value={s.progress} />
                    </td>
                    <td>{s.completed_at ? date(s.completed_at) : "—"}</td>
                    <td>
                      {s.result ? (
                        <details>
                          <summary>View result</summary>
                          <pre>{JSON.stringify(s.result, null, 2)}</pre>
                        </details>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
