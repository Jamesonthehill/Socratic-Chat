import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "./api";
import { Notice } from "./ui";
import "./aiducate.css";

const statusLabel = status => ({ completed: "Completed", in_progress: "In progress", not_started: "Not started" })[status] || status;

function Metric({ label, value, hint }) {
  return <div className="aid-metric"><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>;
}

export default function AiducateWorkspace() {
  const [searchParams] = useSearchParams();
  const [courses, setCourses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [courseId, setCourseId] = useState(() => searchParams.get("course") || "");
  const [assignmentId, setAssignmentId] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [tab, setTab] = useState("overview");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([api("/courses"), api("/platform/assignments")]).then(([courseData, assignmentData]) => {
      if (!active) return;
      setCourses((courseData.courses || []).filter(course => course.membership_role === "instructor" && course.membership_status === "approved"));
      setAssignments(assignmentData.filter(item => item.tool === "reflections" && item.status === "published" && item.can_manage !== false));
    }).catch(e => active && setError(e.message)).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const course = courses.find(item => String(item.course_id) === String(courseId));
  const courseAssignments = assignments.filter(item => String(item.course_id) === String(courseId));
  const selected = courseAssignments.find(item => String(item.id) === String(assignmentId));
  const visibleStudents = (analysis?.students || []).filter(student =>
    `${student.name} ${student.status} ${student.responses.join(" ")}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));

  async function runAnalysis(id = assignmentId) {
    if (!id) return;
    setError(""); setAnalyzing(true); setAnalysis(null);
    try { setAnalysis(await api(`/platform/assignments/${id}/reflection-analysis`)); setTab("overview"); }
    catch (e) { setError(e.message); }
    finally { setAnalyzing(false); }
  }
  function openCourse(id) { setCourseId(String(id)); setAssignmentId(""); setAnalysis(null); setQuery(""); }
  function openAssignment(id) { setAssignmentId(String(id)); setAnalysis(null); setQuery(""); }

  const header = (eyebrow, title, description) => <div className="aid-heading"><div><span className="aid-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div></div>;

  return <div className="aid-workspace">
    <nav className="aid-breadcrumb" aria-label="AIducate location">
      <button type="button" onClick={() => { setCourseId(""); setAssignmentId(""); setAnalysis(null); }}>AIducate</button>
      {course && <><span>›</span><button type="button" onClick={() => openCourse(courseId)}>{course.course_code || course.title}</button></>}
      {selected && <><span>›</span><span>{selected.title}</span></>}
    </nav>
    {error && <Notice error={error}/>}
    {loading ? <p role="status">Opening AIducate workspace…</p> : !course ? <>
      {header("Instructor workspace", "AIducate dashboard", "Choose a course to review its Reflection assignments and student responses.")}
      <div className="aid-metrics">
        <Metric label="Your courses" value={courses.length} hint="Courses you teach" />
        <Metric label="Reflection sets" value={assignments.length} hint="Published BrainTutor assignments" />
        <Metric label="Available assignments" value={assignments.length} hint="Open one to review saved responses" />
      </div>
      <section className="aid-section" aria-labelledby="aid-courses-title"><div className="aid-section-heading"><div><span className="aid-eyebrow">Your course content</span><h2 id="aid-courses-title">Your courses</h2></div></div>
        {courses.length ? <div className="aid-course-grid">{courses.map(item => {
          const count = assignments.filter(assignment => String(assignment.course_id) === String(item.course_id)).length;
          return <button type="button" className="aid-course-card" key={item.course_id} onClick={() => openCourse(item.course_id)}><span className="aid-eyebrow">{item.course_code || "Course"}</span><strong>{item.title || item.course_code}</strong><small>{count} Reflection assignment{count === 1 ? "" : "s"}</small><span className="aid-text-action">Open course →</span></button>;
        })}</div> : <div className="aid-empty"><span className="aid-empty-icon">◇</span><h3>No instructor courses yet</h3><p>When you have a course in BrainTutor, it will appear here.</p></div>}
      </section>
    </> : !selected ? <>
      {header(`Course workspace · ${course.course_code || "Course"}`, course.title || course.course_code, "Collect Reflection responses, open an assignment, and explore what students shared.")}
      <div className="aid-guide" aria-label="How AIducate works">
        {[["01", "Collect reflections", "Publish a Reflection assignment and let students respond."], ["02", "Analyze reflections", "Select an assignment to count participation and open saved responses."], ["03", "Explore results", "Review the class overview and individual responses."]].map(([number, title, detail]) => <div className="aid-guide-card" key={number}><span className="aid-eyebrow">{number}</span><h3>{title}</h3><p>{detail}</p></div>)}
      </div>
      <section className="aid-section" aria-labelledby="aid-assignments-title"><div className="aid-section-heading"><div><span className="aid-eyebrow">Your course content</span><h2 id="aid-assignments-title">Reflection assignments</h2><p>Published assignments in this course are ready for review.</p></div></div>
        {courseAssignments.length ? <div className="aid-assignment-list">{courseAssignments.map(item => <button className="aid-assignment-row" type="button" key={item.id} onClick={() => openAssignment(item.id)}><span><strong>{item.title}</strong><small>BrainTutor Reflection · {item.completed_count || 0} completed</small></span><span className="aid-text-action">Open analysis →</span></button>)}</div> : <div className="aid-empty"><span className="aid-empty-icon">◇</span><h3>No published Reflection assignments</h3><p>Create a Reflection activity in this course, then return here to review responses.</p><Link className="button" to="/professor/activities/new">Create Reflection activity</Link></div>}
      </section>
    </> : <>
      {header("Reflection workspace", selected.title, `${course.course_code || course.title} · BrainTutor Reflection`)}
      {!analysis ? <div className="aid-empty aid-ready"><span className="aid-empty-icon">◌</span><h2>Ready for analysis</h2><p>Open the saved responses and participation counts for this assignment.</p><div className="aid-progress-steps"><span className="done">✓ Reflection selected</span><span>Review responses</span><span>Explore results</span></div><button type="button" onClick={() => runAnalysis()} disabled={analyzing}>{analyzing ? "Opening analysis…" : "Run analysis"}</button></div> : <>
        <div className="aid-result-banner"><strong>Analysis ready</strong><span>These results come from saved BrainTutor responses. No grades, emotions, or themes have been inferred.</span><button type="button" onClick={() => runAnalysis()} disabled={analyzing}>{analyzing ? "Refreshing…" : "Refresh results"}</button></div>
        <div className="aid-tabs" role="tablist" aria-label="Analysis views">{[["overview", "Overview"], ["students", "Students"], ["details", "Analysis details"]].map(([id, label]) => <button type="button" role="tab" aria-selected={tab === id} key={id} onClick={() => setTab(id)}>{label}</button>)}</div>
        {tab === "overview" && <>
          <section className="aid-start"><span className="aid-eyebrow">Start here · Reflection results</span><h2>Start with the basics</h2><p>See how many students responded, then open their reflections when you need more detail.</p></section>
          <div className="aid-metrics"><Metric label="Assigned students" value={analysis.summary.assigned} hint="Students assigned this activity"/><Metric label="Started" value={analysis.summary.started} hint="Students who opened it"/><Metric label="Completed" value={analysis.summary.completed} hint="Finished assignments"/><Metric label="Student responses" value={analysis.summary.responses} hint="Saved messages from students"/></div>
          <div className="aid-overview-grid"><section className="aid-section"><span className="aid-eyebrow">01 · Notice participation</span><h2>Assignment progress</h2><p>{analysis.summary.completed} of {analysis.summary.assigned} assigned students completed this Reflection.</p><div className="aid-progress-track"><div style={{width: `${analysis.summary.assigned ? Math.round(analysis.summary.completed / analysis.summary.assigned * 100) : 0}%`}}/></div><button className="aid-link" type="button" onClick={() => setTab("students")}>Review student responses →</button></section><section className="aid-section"><span className="aid-eyebrow">02 · Understand the data</span><h2>What this view shows</h2><p>Participation counts and original student messages from this Reflection assignment.</p><p>Topic, emotion, and challenge analysis can be added when a verified analysis service is connected.</p><button className="aid-link" type="button" onClick={() => setTab("details")}>See analysis details →</button></section></div>
        </>}
        {tab === "students" && <section className="aid-section"><div className="aid-section-heading"><div><span className="aid-eyebrow">Explore results</span><h2>Student reflections</h2><p>Open a student to read their saved responses.</p></div><label className="aid-search">Search students or responses<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search…"/></label></div>{visibleStudents.length ? <div className="aid-assignment-list">{visibleStudents.map(student => <details key={student.student_id} className="aid-student-row"><summary><span><strong>{student.name}</strong><small>{statusLabel(student.status)} · {student.response_count} response{student.response_count === 1 ? "" : "s"}</small></span><span className="aid-text-action">View responses</span></summary>{student.responses.length ? <ol>{student.responses.map((response, index) => <li key={index}>{response}</li>)}</ol> : <p>No response saved yet.</p>}</details>)}</div> : <p className="aid-no-results">No matching students or responses.</p>}</section>}
        {tab === "details" && <section className="aid-section"><span className="aid-eyebrow">About this analysis</span><h2>Data and limits</h2><dl className="aid-details"><dt>Source</dt><dd>BrainTutor Reflection assignment responses</dd><dt>Included</dt><dd>Assigned students, activity status, and saved student messages</dd><dt>Current method</dt><dd>Counts and direct review of original responses</dd><dt>Not yet available</dt><dd>Canvas survey imports, theme classification, emotion analysis, and grade comparisons</dd></dl></section>}
      </>}
    </>}
  </div>;
}
