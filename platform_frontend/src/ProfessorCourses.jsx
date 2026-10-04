import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, label, TOOLS } from "./api";
import CanvasAssignments from "./CanvasAssignments";
import CanvasCourseLink from "./CanvasCourseLink";
import CanvasImport from "./CanvasImport";
import { Notice } from "./ui";

export default function ProfessorCourses({ assignments, assignmentsError }) {
  const navigate = useNavigate();
  const [courses, setCourses] = useState(null);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [error, setError] = useState("");
  const managementRef = useRef(null);
  const courseButtons = useRef({});

  useEffect(() => {
    let active = true;
    api("/courses")
      .then(({ courses: visibleCourses }) => {
        if (active) {
          setCourses(
            visibleCourses.filter(
              (course) => course.membership_role === "instructor",
            ),
          );
        }
      })
      .catch((caught) => active && setError(caught.message));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (selectedCourseId) {
      managementRef.current?.scrollIntoView?.({
        behavior: "auto",
        block: "nearest",
      });
    }
  }, [selectedCourseId]);

  const selectedCourse = courses?.find(
    (course) => course.course_id === selectedCourseId,
  );
  const courseAssignments = (assignments || []).filter(
    (assignment) => assignment.course_id === selectedCourseId,
  );

  function addCourse(created) {
    setCourses((current) => {
      const visible = current || [];
      return visible.some((course) => course.course_id === created.course_id)
        ? visible.map((course) =>
            course.course_id === created.course_id ? created : course,
          )
        : [...visible, created];
    });
    setSelectedCourseId(created.course_id);
  }

  function linkCourse(updated) {
    setCourses((current) =>
      current.map((course) =>
        course.course_id === updated.course_id ? updated : course,
      ),
    );
  }

  return (
    <section
      id="courses"
      className="section professor-course-section"
      aria-labelledby="professor-courses-title"
    >
      <div className="section-heading">
        <div>
          <h2 id="professor-courses-title">Your courses</h2>
          <p>Choose a course to manage its chatbot assignments.</p>
        </div>
      </div>
      <Notice error={error} />
      {courses === null && !error && <p role="status">Loading courses…</p>}
      {courses?.length === 0 && (
        <p className="empty">No courses yet. Add one from Canvas below.</p>
      )}
      {courses?.length > 0 && (
        <div className="professor-course-grid">
          {courses.map((course) => (
            <button
              type="button"
              key={course.course_id}
              ref={(node) => {
                courseButtons.current[course.course_id] = node;
              }}
              className="professor-course-card"
              aria-expanded={selectedCourseId === course.course_id}
              aria-controls={
                selectedCourseId === course.course_id
                  ? "professor-course-management"
                  : undefined
              }
              onClick={() =>
                setSelectedCourseId((current) =>
                  current === course.course_id ? "" : course.course_id,
                )
              }
            >
              <span className="eyebrow">{course.course_code}</span>
              <strong>{course.title}</strong>
              <span className="professor-course-card-action">
                {selectedCourseId === course.course_id
                  ? "Close management"
                  : "Manage course"}
                <span aria-hidden="true">
                  {selectedCourseId === course.course_id ? "−" : "→"}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
      {selectedCourse && (
        <div
          id="professor-course-management"
          ref={managementRef}
          className="professor-course-management"
          role="region"
          aria-label={`${selectedCourse.title} management`}
        >
          <div className="section-heading">
            <div>
              <span className="eyebrow">{selectedCourse.course_code}</span>
              <h3>{selectedCourse.title}</h3>
            </div>
            <button
              type="button"
              className="quiet"
              onClick={() => {
                setSelectedCourseId("");
                courseButtons.current[selectedCourse.course_id]?.focus();
              }}
              aria-label="Close course management"
            >
              Close
            </button>
          </div>
          <h4>Create a chatbot assignment</h4>
          <div className="professor-course-actions">
            {Object.entries(TOOLS).map(([toolId, tool]) => (
              <Link
                key={toolId}
                className="button secondary"
                to={`/professor/tools/${toolId}/assignments/new?course=${selectedCourse.course_id}`}
              >
                {tool.name}
              </Link>
            ))}
          </div>
          <h4>CourseLab assignments</h4>
          {assignmentsError ? (
            <Notice error={assignmentsError} />
          ) : assignments === null ? (
            <p role="status">Loading assignments…</p>
          ) : courseAssignments.length ? (
            <ul className="professor-course-assignment-list">
              {courseAssignments.map((assignment) => (
                <li key={assignment.id}>
                  <Link
                    to={`/professor/tools/${assignment.tool}/assignments/${assignment.id}`}
                  >
                    {assignment.title}
                  </Link>
                  <span>
                    {TOOLS[assignment.tool]?.name || assignment.tool} ·{" "}
                    {label(assignment.status)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="help">No CourseLab assignments in this course yet.</p>
          )}
          {selectedCourse.canvas_course_id ? (
            <CanvasAssignments
              key={selectedCourse.course_id}
              course={selectedCourse}
              onImported={(draft) =>
                navigate(
                  `/professor/tools/${draft.tool}/assignments/${draft.id}`,
                )
              }
            />
          ) : (
            <CanvasCourseLink course={selectedCourse} onLinked={linkCourse} />
          )}
        </div>
      )}
      <details
        className="professor-course-import"
        onToggle={(event) => setImportOpen(event.currentTarget.open)}
      >
        <summary>Add a course from Canvas</summary>
        {importOpen && <CanvasImport onCourseCreated={addCourse} />}
      </details>
    </section>
  );
}
