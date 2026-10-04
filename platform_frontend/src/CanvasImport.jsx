import { useEffect, useState } from "react";
import { api } from "./api";
import { Notice } from "./ui";

const CANVAS_ROLE_LABELS = {
  teacher: "Teacher",
  ta: "TA",
  designer: "Designer",
};

export default function CanvasImport({ onCourseCreated }) {
  const [accessToken, setAccessToken] = useState("");
  const [canvasCourses, setCanvasCourses] = useState([]);
  const [canvasCourseId, setCanvasCourseId] = useState("");
  const [connection, setConnection] = useState(null);
  const [coursesLoaded, setCoursesLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let active = true;
    api("/platform/integrations/canvas/connection")
      .then(async (status) => {
        if (!active) return;
        setConnection(status);
        if (status.connected) {
          const courses = await api("/platform/integrations/canvas/courses", {
            method: "POST",
            body: {},
          });
          if (active) {
            setCanvasCourses(courses);
            setCoursesLoaded(true);
          }
        }
      })
      .catch((caught) => active && setError(caught.message));
    return () => {
      active = false;
    };
  }, []);

  async function perform(action) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await action();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  function connectCanvas() {
    return perform(async () => {
      const result = await api("/platform/integrations/canvas/connection", {
        method: "POST",
        body: { access_token: accessToken },
      });
      setConnection(result);
      setCanvasCourses(result.courses || []);
      setCoursesLoaded(true);
      setAccessToken("");
      setCanvasCourseId("");
    });
  }

  function loadCourses() {
    return perform(async () => {
      setCoursesLoaded(false);
      const courses = await api("/platform/integrations/canvas/courses", {
        method: "POST",
        body: {},
      });
      setCanvasCourses(courses);
      setCoursesLoaded(true);
      setCanvasCourseId("");
    });
  }

  function disconnectCanvas() {
    return perform(async () => {
      const result = await api("/platform/integrations/canvas/connection", {
        method: "DELETE",
      });
      setConnection(result);
      setCanvasCourses([]);
      setCoursesLoaded(false);
      setCanvasCourseId("");
    });
  }

  function createPlatformCourse() {
    return perform(async () => {
      if (!canvasCourseId) throw new Error("Select a Canvas course first.");
      const created = await api("/platform/integrations/canvas/course", {
        method: "POST",
        body: { course_id: canvasCourseId },
      });
      onCourseCreated(created);
      setCanvasCourseId("");
      setSuccess(`${created.title} was added to CourseLab.`);
    });
  }

  return (
    <section className="panel canvas-import">
      <h2>Add courses from UNC Charlotte Canvas</h2>
      <p>
        Connect Canvas to see active courses where you are a teacher, TA, or
        designer. Choose a course to add it to CourseLab. Your token is
        encrypted on the server, is never returned to your browser, and can be
        disconnected whenever you choose.
      </p>
      <Notice error={error}>{success}</Notice>
      <div className="canvas-import-grid">
        {connection?.connected ? (
          <>
            <div className="canvas-connection-status" role="status">
              <strong>Canvas connected</strong>
              <span>
                Your saved connection will be reused for future sign-ins.
              </span>
            </div>
            <div className="canvas-connection-actions">
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={loadCourses}
              >
                Refresh Canvas courses
              </button>
              <button
                type="button"
                className="quiet"
                disabled={busy}
                onClick={disconnectCanvas}
              >
                Disconnect Canvas
              </button>
            </div>
          </>
        ) : (
          <>
            <label>
              Canvas access token
              <input
                type="password"
                autoComplete="off"
                value={accessToken}
                onChange={(event) => setAccessToken(event.target.value)}
                placeholder="Paste a current Canvas token once"
              />
            </label>
            <button
              type="button"
              className="secondary"
              disabled={
                busy ||
                !connection?.encryption_configured ||
                accessToken.length < 10
              }
              onClick={connectCanvas}
            >
              Connect Canvas
            </button>
            {connection && !connection.encryption_configured && (
              <p className="help">
                Secure Canvas connections are not configured on this server yet.
              </p>
            )}
            {connection?.reconnect_required && (
              <p className="help">
                Your saved Canvas connection must be reconnected.
              </p>
            )}
          </>
        )}
        {canvasCourses.length > 0 && (
          <>
            <label>
              Canvas course
              <select
                value={canvasCourseId}
                onChange={(event) => setCanvasCourseId(event.target.value)}
              >
                <option value="">Select a Canvas course</option>
                {canvasCourses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.course_code
                      ? `${course.course_code} — ${course.name}`
                      : course.name}
                    {CANVAS_ROLE_LABELS[course.enrollment_role]
                      ? ` (${CANVAS_ROLE_LABELS[course.enrollment_role]})`
                      : ""}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="secondary"
              disabled={busy || !canvasCourseId}
              onClick={createPlatformCourse}
            >
              Add course to CourseLab
            </button>
          </>
        )}
        {connection?.connected &&
          coursesLoaded &&
          canvasCourses.length === 0 && (
            <p className="help">
              No active Canvas courses where you are a teacher, TA, or designer
              were found.
            </p>
          )}
      </div>
    </section>
  );
}
