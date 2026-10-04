import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Notice } from "./ui";

const CANVAS_ROLE_LABELS = {
  teacher: "Teacher",
  ta: "TA",
  designer: "Designer",
};

function CanvasCourseLinkForCourse({ course, onLinked }) {
  const [canvasCourses, setCanvasCourses] = useState(null);
  const [selectedCanvasId, setSelectedCanvasId] = useState("");
  const [status, setStatus] = useState("idle");
  const [linking, setLinking] = useState(false);
  const [error, setError] = useState("");
  const [missingConnection, setMissingConnection] = useState(false);
  const requesting = useRef(false);
  const loaded = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function loadCourses() {
    if (requesting.current || loaded.current) return;
    requesting.current = true;
    setStatus("loading");
    setError("");
    setMissingConnection(false);
    try {
      const result = await api("/platform/integrations/canvas/courses", {
        method: "POST",
        body: {},
      });
      if (!mounted.current) return;
      setCanvasCourses(result);
      loaded.current = true;
      setStatus("ready");
    } catch (caught) {
      if (!mounted.current) return;
      setMissingConnection(/connect.*canvas|reconnect/i.test(caught.message));
      setError(caught.message);
      setStatus("error");
    } finally {
      requesting.current = false;
    }
  }

  async function linkCourse() {
    if (!selectedCanvasId || linking) return;
    setLinking(true);
    setError("");
    try {
      const updated = await api("/platform/integrations/canvas/link-course", {
        method: "POST",
        body: {
          platform_course_id: course.course_id,
          course_id: selectedCanvasId,
        },
      });
      if (mounted.current) onLinked(updated);
    } catch (caught) {
      if (mounted.current) setError(caught.message);
    } finally {
      if (mounted.current) setLinking(false);
    }
  }

  return (
    <details
      className="canvas-course-link"
      onToggle={(event) => {
        if (event.currentTarget.open) loadCourses();
      }}
    >
      <summary>Link Canvas course</summary>
      <div className="canvas-course-link-content">
        <p>Choose this course’s match in Canvas to use its assignments here.</p>
        {status === "loading" && <p role="status">Loading Canvas courses…</p>}
        {status === "error" && (
          <>
            {missingConnection ? (
              <p role="alert" className="canvas-course-link-help">
                Connect Canvas below first in “Add a course from Canvas,” then
                try again.
              </p>
            ) : (
              <Notice error={error} />
            )}
            <button
              type="button"
              className="secondary compact"
              onClick={loadCourses}
            >
              Try again
            </button>
          </>
        )}
        {status === "ready" && canvasCourses.length === 0 && (
          <p className="canvas-course-link-help">
            No active Canvas courses where you are a teacher, TA, or designer
            were found.
          </p>
        )}
        {status === "ready" && canvasCourses.length > 0 && (
          <div className="canvas-course-link-controls">
            <label>
              Canvas course
              <select
                value={selectedCanvasId}
                disabled={linking}
                onChange={(event) => setSelectedCanvasId(event.target.value)}
              >
                <option value="">Select a Canvas course</option>
                {canvasCourses.map((canvasCourse) => (
                  <option key={canvasCourse.id} value={canvasCourse.id}>
                    {canvasCourse.course_code
                      ? `${canvasCourse.course_code} — ${canvasCourse.name}`
                      : canvasCourse.name}
                    {CANVAS_ROLE_LABELS[canvasCourse.enrollment_role]
                      ? ` (${CANVAS_ROLE_LABELS[canvasCourse.enrollment_role]})`
                      : ""}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={!selectedCanvasId || linking}
              onClick={linkCourse}
            >
              {linking ? "Linking…" : "Link selected Canvas course"}
            </button>
          </div>
        )}
        {status === "ready" && error && <Notice error={error} />}
      </div>
    </details>
  );
}

export default function CanvasCourseLink({ course, onLinked }) {
  if (!course || course.canvas_course_id) return null;
  return (
    <CanvasCourseLinkForCourse
      key={course.course_id}
      course={course}
      onLinked={onLinked}
    />
  );
}
