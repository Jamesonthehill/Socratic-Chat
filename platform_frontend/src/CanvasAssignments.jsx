import { useEffect, useRef, useState } from "react";
import { api, date, TOOLS } from "./api";
import { Notice } from "./ui";

function CanvasAssignmentsForCourse({ course, tool, onImported }) {
  const [assignments, setAssignments] = useState(null);
  const [status, setStatus] = useState("idle");
  const [search, setSearch] = useState("");
  const [importingId, setImportingId] = useState(null);
  const [imported, setImported] = useState(() => new Set());
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const requesting = useRef(false);
  const loaded = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function loadAssignments() {
    if (requesting.current || loaded.current) return;
    requesting.current = true;
    setStatus("loading");
    setError("");
    try {
      const result = await api("/platform/integrations/canvas/assignments", {
        method: "POST",
        body: { course_id: course.canvas_course_id },
      });
      if (!mounted.current) return;
      setAssignments(result);
      loaded.current = true;
      setStatus("ready");
    } catch (caught) {
      if (!mounted.current) return;
      setError(caught.message);
      setStatus("error");
    } finally {
      requesting.current = false;
    }
  }

  async function importAssignment(assignment) {
    const importKey = `${assignment.id}:${tool}`;
    if (importingId !== null || imported.has(importKey)) return;
    setImportingId(assignment.id);
    setError("");
    setSuccess("");
    try {
      const draft = await api("/platform/integrations/canvas/import", {
        method: "POST",
        body: {
          course_id: course.canvas_course_id,
          assignment_id: assignment.id,
          platform_course_id: course.course_id,
          tool,
        },
      });
      if (!mounted.current) return;
      setImported((current) => new Set(current).add(importKey));
      setSuccess(
        `Draft created for ${assignment.name}. Review it before publishing.`,
      );
      onImported(draft);
    } catch (caught) {
      if (mounted.current) setError(caught.message);
    } finally {
      if (mounted.current) setImportingId(null);
    }
  }

  const visibleAssignments = (assignments || []).filter((assignment) =>
    assignment.name
      .toLocaleLowerCase()
      .includes(search.trim().toLocaleLowerCase()),
  );

  return (
    <details
      className="canvas-assignments"
      onToggle={(event) => {
        if (event.currentTarget.open) loadAssignments();
      }}
    >
      <summary>
        <span>Choose a Canvas assignment</span>
        {assignments && <small>{assignments.length} available</small>}
      </summary>
      <div className="canvas-assignments-content">
        <p className="canvas-assignments-intro">
          Select a Canvas assignment to create a prefilled {TOOLS[tool].name}{" "}
          draft. Links to Canvas files stay clickable; students need their own
          Canvas access to open them. File contents are not copied into the
          chatbot's course materials.
        </p>
        {status === "loading" && (
          <p role="status">Loading Canvas assignments…</p>
        )}
        {status === "error" && (
          <button
            type="button"
            className="secondary compact"
            onClick={loadAssignments}
          >
            Try again
          </button>
        )}
        <Notice error={error}>{success}</Notice>
        {status === "ready" && assignments.length === 0 && (
          <p className="canvas-assignments-empty">
            There are no assignments in this Canvas course yet.
          </p>
        )}
        {status === "ready" && assignments.length > 0 && (
          <>
            <div className="canvas-assignments-controls">
              <label>
                Find an assignment
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search by name"
                />
              </label>
            </div>
            <p className="canvas-assignments-count" role="status">
              Showing {visibleAssignments.length} of {assignments.length} Canvas
              assignments
            </p>
            {visibleAssignments.length === 0 ? (
              <p className="canvas-assignments-empty">
                No assignments match your search.
              </p>
            ) : (
              <ul className="canvas-assignments-list">
                {visibleAssignments.map((assignment) => {
                  const alreadyImported = imported.has(
                    `${assignment.id}:${tool}`,
                  );
                  return (
                    <li key={assignment.id} className="canvas-assignment-row">
                      <div className="canvas-assignment-details">
                        <strong>{assignment.name}</strong>
                        <small>
                          {assignment.due_at
                            ? `Due ${date(assignment.due_at)}`
                            : "No due date"}
                        </small>
                        {assignment.description && (
                          <p>{assignment.description}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        className="secondary compact"
                        disabled={importingId !== null || alreadyImported}
                        onClick={() => importAssignment(assignment)}
                        aria-label={`Create ${TOOLS[tool].name} draft for ${assignment.name}`}
                      >
                        {alreadyImported
                          ? "Draft created"
                          : importingId === assignment.id
                            ? "Creating…"
                            : "Create draft"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
      </div>
    </details>
  );
}

export default function CanvasAssignments({ course, tool, onImported }) {
  if (!course?.canvas_course_id) return null;
  if (!TOOLS[tool]) return null;
  return (
    <CanvasAssignmentsForCourse
      key={`${course.course_id}:${course.canvas_course_id}`}
      course={course}
      tool={tool}
      onImported={onImported}
    />
  );
}
