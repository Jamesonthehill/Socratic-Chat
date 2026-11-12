import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, logout, session } from "./api";
import { Notice } from "./ui";
import "./aiducate.css";
import aiducateLogo from "./aiducate-logo.png";
import { download, reportHtml } from "./reflection-analysis-export";
import AiducateProfile from "./AiducateProfile";
import AiducateStudentProfiles from "./AiducateStudentProfiles";
import CanvasSurveyImport from "./CanvasSurveyImport";


function Metric({ label, value, hint }) {
  return <div className="aid-metric"><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>;
}

function ReflectionImportPage({ course, title, onClose, onAdd, error }) {
  return <section className="aid-import-page" aria-labelledby="aid-import-title">
    <header><h2 id="aid-import-title">{title ? "Replace reflection data" : "Add reflection"}</h2>
      <button type="button" className="secondary" onClick={onClose}>Cancel</button>
    </header>
    <div className="aid-import-page-body">
      <p>Upload survey responses for <strong>{course.course_code || course.title}</strong>.</p>
      <div className="aid-canvas-instructions">
        <strong>Get the CSV from Canvas</strong>
        <ol>
          <li>Open the survey and select <strong>Survey Statistics</strong>.</li>
          <li>Choose <strong>Student Analysis</strong> to download the response CSV.</li>
          <li>Use <strong>Upload reflection CSV</strong> below. A grading CSV is optional.</li>
        </ol>
        <p>Direct Canvas import is not available yet.</p>
      </div>
      {error && <Notice error={error} />}
      <CanvasSurveyImport onUse={onAdd} initialName={title} useLabel={title ? "Replace reflection data" : "Add reflection"} />
    </div>
  </section>;
}

function CreateCourseDialog({ onClose, onSubmit, saving, error }) {
  const dialog = useRef(null);
  useEffect(() => {
    dialog.current.showModal();
  }, []);

  return <dialog ref={dialog} className="aid-create-dialog" aria-labelledby="aid-create-course-title"
    onClose={onClose} onCancel={event => { if (saving) event.preventDefault(); }}>
    <form onSubmit={onSubmit}>
      <header><h2 id="aid-create-course-title">Create a course</h2></header>
      <div className="aid-create-fields">
        <p>Courses group reflection uploads and their analyses.</p>
        {error && <Notice error={error} />}
        <label>Course code<input name="course_code" placeholder="e.g., CSC 141" required minLength={2} maxLength={40} autoFocus /></label>
        <label>Course name<input name="title" placeholder="e.g., Introduction to Java" required minLength={2} maxLength={160} /></label>
        <label>Term<input name="term" placeholder="e.g., Fall 2026" maxLength={80} /></label>
      </div>
      <footer>
        <button type="button" className="secondary" disabled={saving} onClick={() => dialog.current.close()}>Cancel</button>
        <button type="submit" disabled={saving}>{saving ? "Creating…" : "Create course"}</button>
      </footer>
    </form>
  </dialog>;
}

async function buildInstructorReport(selected, analysis) {
  const title = selected.title;
  const findings = new Map((analysis.findings || []).map(record => [record.student_id, record]));
  if (selected.overview) {
    const students = analysis.students.map(student => {
      const pairs = student.answers || student.responses.map(response => {
        const separator = response.indexOf(" — ");
        return separator < 0 ? { question: "Reflection", response } : {
          question: response.slice(0, separator), response: response.slice(separator + 3),
        };
      });
      const grades = student.reportGrades || Object.fromEntries(
        (student.gradeBreakdown || []).filter(({ score }) => /^-?\d+(?:\.\d+)?%?$/.test(score))
          .map(({ category, score }) => [category, Number(score.replace(/%$/, ""))]),
      );
      return {
        answers: Object.fromEntries(pairs.map(({ question, response }) => [question, response])),
        grades,
        missing_assignments: student.missingAssignments || [],
        analysis: findings.get(student.student_id)?.analysis,
      };
    });
    const { html } = await api("/platform/reflection-analysis/report", { method: "POST", body: { students } });
    return html;
  }
  const records = analysis.students.filter(student => student.responses.length).map(student => ({
    ...findings.get(student.student_id),
    text: student.responses.join("\n\n"),
    grade: student.gradeLabel,
    answers: student.answers,
    gradeBreakdown: student.gradeBreakdown,
    missingAssignments: student.missingAssignments,
  }));
  return reportHtml(title, records, analysis.model, {
    assigned: analysis.summary.assigned,
    gradeLabels: analysis.students.map(student => student.gradeLabel),
  });
}

export default function AiducateWorkspace() {
  const [profileOpen, setProfileOpen] = useState(false);
  const account = session();
  const accountId = account?.user_id || account?.username;
  const storageKey = accountId ? `aiducate-reflections:${accountId}` : null;
  const [imports, setImports] = useState(() => {
    try {
      const saved = storageKey && JSON.parse(localStorage.getItem(storageKey));
      return Array.isArray(saved) ? saved : [];
    } catch {
      return [];
    }
  });
  const [importError, setImportError] = useState("");
  const resultsKey = storageKey ? `${storageKey}:results` : null;
  const [ready, setReady] = useState(() => {
    try {
      return (resultsKey && JSON.parse(localStorage.getItem(resultsKey))) || {};
    } catch {
      return {};
    }
  });
  const savedResults = useRef(ready);

  function saveResult(id, result) {
    const next = { ...savedResults.current };
    if (result) next[id] = result;
    else delete next[id];
    savedResults.current = next;
    setReady(next);
    try {
      if (!resultsKey) throw new Error("Instructor account unavailable");
      localStorage.setItem(resultsKey, JSON.stringify(next));
    } catch {
      setError("Results are available for this visit, but could not be saved in this browser.");
    }
  }
  const [replaceId, setReplaceId] = useState("");
  function beginImport(id = "") {
    setProfileOpen(false);
    setReplaceId(id);
    setImportError("");
    setImportOpen(true);
  }
  function acceptImport(filename, overview) {
    const id = crypto.randomUUID();
    const item = { id, course_id: courseId, title: filename, completed_count: overview.summary.completed, overview };
    const nextImports = [...imports.filter(reflection => reflection.id !== id), item];
    try {
      if (!storageKey) throw new Error("Instructor account unavailable");
      localStorage.setItem(storageKey, JSON.stringify(nextImports));
    } catch {
      setImportError("Could not save this reflection in your browser. Check available storage or try a smaller CSV.");
      return;
    }
    setImports(nextImports);
    if (replaceId) saveResult(replaceId, null);
    setImportOpen(false);
    analysisTarget.current = String(id);
    setAssignmentId(String(id));
    setSearchParams({ course: courseId, reflection: id }, { replace: true });
    setAnalysis(null);
  }
  const [importOpen, setImportOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const [courses, setCourses] = useState([]);
  const [enrollmentCount, setEnrollmentCount] = useState(null);
  const [creatingCourse, setCreatingCourse] = useState(false);
  const [savingCourse, setSavingCourse] = useState(false);
  const [courseError, setCourseError] = useState("");
  const termsKey = accountId ? `aiducate-course-terms:${accountId}` : null;
  const [courseTerms, setCourseTerms] = useState(() => {
    try {
      return (termsKey && JSON.parse(localStorage.getItem(termsKey))) || {};
    } catch {
      return {};
    }
  });
  const [assignments, setAssignments] = useState([]);
  const [courseId, setCourseId] = useState(() => searchParams.get("course") || "");
  const [assignmentId, setAssignmentId] = useState(() => searchParams.get("reflection") || "");
  const analysisTarget = useRef(assignmentId);
  const [analysis, setAnalysis] = useState(() => restoreAnalysis(assignmentId));
  const [surveyAnalysis, setSurveyAnalysis] = useState(() => ready[assignmentId]?.surveys || null);
  const [tab, setTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [reportPreview, setReportPreview] = useState(null);
  const reportCache = useRef(new WeakMap());
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([api("/courses"), api("/platform/assignments")]).then(([courseData, assignmentData]) => {
      if (!active) return;
      setCourses((courseData.courses || []).filter(course => course.membership_role === "instructor" && course.membership_status === "approved"));
      setAssignments(assignmentData.filter(item => (item.tool === "reflections" || (item.tool === "socratic" && Object.values(item.config?.step_surveys || {}).some(record=>record.published))) && item.status === "published" && item.can_manage !== false));
    }).catch(e => active && setError(e.message)).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setEnrollmentCount(null);
    Promise.all(courses.map(course => api(
      `/instructor/enrolled-students?course_id=${encodeURIComponent(course.course_id)}`,
    ))).then(rosters => {
      if (active) setEnrollmentCount(rosters.reduce(
        (sum, roster) => sum + new Set(roster.map(student => student.user_id)).size, 0,
      ));
    }).catch(() => {});
    return () => { active = false; };
  }, [courses]);

  async function createCourse(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setCourseError("");
    setSavingCourse(true);
    try {
      const item = await api("/courses", { method: "POST", body: {
        course_code: form.get("course_code").trim(),
        title: form.get("title").trim(),
      } });
      const term = form.get("term").trim();
      if (term) {
        const nextTerms = { ...courseTerms, [item.course_id]: term };
        setCourseTerms(nextTerms);
        try {
          if (termsKey) localStorage.setItem(termsKey, JSON.stringify(nextTerms));
        } catch {
          setError("Course created. The term could only be kept for this visit.");
        }
      }
      setCourses(current => [...current, item]);
      setCreatingCourse(false);
      openCourse(item.course_id);
    } catch (error) {
      setCourseError(error.message);
    } finally {
      setSavingCourse(false);
    }
  }

  const reflectionSets = [...assignments, ...imports].filter(item =>
    item.tool !== "socratic" && courses.some(course => String(course.course_id) === String(item.course_id)),
  );
  const hasCompletedAnalysis = item => {
    const result = ready[item.id];
    return item.overview
      ? Boolean(item.completed_count && result?.findings?.filter(record => record.analysis).length === item.completed_count)
      : Boolean(result?.overview && item.completed_count);
  };
  const completedAnalyses = reflectionSets.filter(hasCompletedAnalysis).length;
  const awaitingAnalysis = reflectionSets.length - completedAnalyses;

  const course = courses.find(item => String(item.course_id) === String(courseId));
  const courseAssignments = [...assignments, ...imports].filter(item => String(item.course_id) === String(courseId));
  const selected = courseAssignments.find(item => String(item.id) === String(assignmentId));

  function restoreAnalysis(id) {
    const result = ready[id];
    const imported = imports.find(item => item.id === id);
    if (imported && result?.findings) return { ...imported.overview, ...result };
    return result?.overview || null;
  }

  async function runAnalysis() {
    const id = assignmentId;
    if (!id) return;
    setError(""); setAnalyzing(true);
    try {
      if (selected?.overview) {
        const students = selected.overview.students.filter(student => student.responses.length);
        if (!students.length) throw new Error("This reflection set has no written responses to analyze.");
        const previous = ready[id]?.findings || [];
        const completed = new Map(previous.filter(record => record.analysis).map(record => [record.student_id, record]));
        const records = students.filter(student => !completed.has(student.student_id)).map(student => ({
          student_id: student.student_id,
          name: student.name,
          text: student.responses.join("\n\n"),
        }));
        const findings = new Map(previous.map(record => [record.student_id, record]));
        let model = ready[id]?.model || "";
        try {
          let batch = [];
          let characters = 0;
          async function sendBatch() {
            if (!batch.length) return;
            const result = await api("/platform/reflection-analysis/analyze", {
              method: "POST", body: { records: batch, context: course.title || "" },
            });
            for (const { student_id, analysis, error } of result.results) {
              findings.set(student_id, { student_id, analysis, error });
            }
            model = result.model;
            batch = [];
            characters = 0;
          }
          for (const record of records) {
            if (record.text.length > 16000) {
              findings.set(record.student_id, { student_id: record.student_id, error: "Response exceeds the 16,000 character analysis limit." });
              continue;
            }
            if (batch.length === 50 || characters + record.text.length > 120000) await sendBatch();
            batch.push(record);
            characters += record.text.length;
          }
          await sendBatch();
        } finally {
          const result = students.map(student => findings.get(student.student_id)).filter(Boolean);
          if (result.length) {
            const overview = { ...selected.overview, findings: result, model };
            if (analysisTarget.current === id) {
              setAnalysis(overview);
              setTab("overview");
            }
            saveResult(id, { findings: result, model });
          }
        }
        return;
      }
      const [overview,surveys] = await Promise.all([api(`/platform/assignments/${id}/reflection-analysis`),api(`/platform/assignments/${id}/step-survey-analysis`)]);
      if (analysisTarget.current === id) {
        setAnalysis(overview); setSurveyAnalysis(surveys); setTab("overview");
      }
      saveResult(id, { overview, surveys });
    }
    catch (e) { setError(e.message); }
    finally { setAnalyzing(false); }
  }
  function getInstructorReport(reflection, result) {
    const cached = reportCache.current.get(result);
    if (cached) return cached;
    const report = buildInstructorReport(reflection, result).catch(error => {
      reportCache.current.delete(result);
      throw error;
    });
    reportCache.current.set(result, report);
    return report;
  }

  useEffect(() => {
    if (tab !== "details" || !selected || !analysis) return;
    let active = true;
    setReportPreview(null);
    getInstructorReport(selected, analysis).then(
      html => { if (active) setReportPreview({ analysis, html }); },
      error => { if (active) setReportPreview({ analysis, error: error.message }); },
    );
    return () => { active = false; };
  }, [tab, selected, analysis]);

  async function downloadInstructorReport() {
    const filename = (selected.title.replace(/\.csv$/i, "").replace(/[^a-z0-9_-]+/gi, "-") || "reflection") + "-instructor-report.html";
    setError("");
    setExporting(true);
    try {
      download(filename, await getInstructorReport(selected, analysis), "text/html;charset=utf-8");
    } catch (error) {
      setError(error.message);
    } finally {
      setExporting(false);
    }
  }

  function openCourse(id) {
    analysisTarget.current = "";
    setCourseId(String(id)); setAssignmentId(""); setAnalysis(null); setSurveyAnalysis(null);
    setSearchParams(id ? { course: String(id) } : {}, { replace: true });
  }
  function openAssignment(id) {
    analysisTarget.current = String(id);
    setAssignmentId(String(id)); setAnalysis(restoreAnalysis(id)); setSurveyAnalysis(ready[id]?.surveys || null);
    setTab("overview");
    setSearchParams({ course: courseId, reflection: String(id) }, { replace: true });
  }

  const header = (eyebrow, title, description, action) => <div className="aid-heading aid-hero"><div><span className="aid-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div>;

  function openProfile() {
    setImportOpen(false);
    setProfileOpen(true);
  }

  const profileInitial = (account?.display_name?.trim() || account?.username?.trim() || "Instructor")[0].toUpperCase();

  function navigateCourse(id) {
    setImportOpen(false);
    setProfileOpen(false);
    openCourse(id);
  }
  return <div className="aid-workspace aid-shell">
    <aside className="aid-rail">
      <div className="aid-identity"><img src={aiducateLogo} alt="" /><div><strong>AIDucate</strong><small>Reflection analysis</small></div></div>
      <Link className="aid-back-to-braintutor" to="/professor">← Back to BrainTutor</Link>
      <nav aria-label="AIDucate workspace">
        <h2>Workspace</h2>
        <button aria-current={!profileOpen && !course ? "page" : undefined} onClick={() => navigateCourse("")}>Dashboard</button>
        {courses.length > 0 && <><h2>Your courses</h2>{courses.map(item =>
          <button key={item.course_id} aria-current={!profileOpen && courseId === String(item.course_id) ? "page" : undefined}
            onClick={() => navigateCourse(item.course_id)}>{item.course_code || item.title}</button>
        )}</>}
        <h2>Account</h2>
        <button aria-current={profileOpen ? "page" : undefined} onClick={openProfile}>Instructor Profile</button>
        <button type="button" onClick={logout}>Log out</button>
      </nav>
    </aside>
    <div className="aid-content">
    <header className="aid-topbar"><span>Workspace / <b>{profileOpen ? "Instructor Profile" : importOpen ? (replaceId ? "Replace reflection data" : "Add reflection") : selected?.title || course?.course_code || "Dashboard"}</b></span><div className="aid-topbar-profile">
      <small>Instructor workspace</small>
      <button type="button" className="aid-profile-shortcut" onClick={openProfile}
        aria-label="Open Instructor Profile" title="Instructor Profile" aria-current={profileOpen ? "page" : undefined}>
        {profileInitial}
      </button>
    </div></header>
    {profileOpen && <AiducateProfile />}
    {importOpen && course && <ReflectionImportPage course={course} title={replaceId ? selected?.title : ""} onAdd={acceptImport} error={importError} onClose={() => setImportOpen(false)} />}
    <div hidden={profileOpen || importOpen}>
    <nav className="aid-breadcrumb" aria-label="AIducate location">
      <button type="button" onClick={() => openCourse("")}>AIducate</button>
      {course && <><span>›</span><button type="button" onClick={() => openCourse(courseId)}>{course.course_code || course.title}</button></>}
      {selected && <><span aria-hidden="true">›</span><span aria-current="page">{selected.title}</span></>}
    </nav>
    {error && <Notice error={error}/>}
    {loading ? <p role="status">Opening AIducate workspace…</p> : !course ? <>
      <div className="aid-dashboard">
        <header className="aid-dashboard-heading">
          <div><h1>Dashboard</h1><p>Choose a course to manage reflections, run analyses, and explore results.</p></div>
          <button type="button" aria-haspopup="dialog" onClick={() => {
            setCourseError("");
            setCreatingCourse(true);
          }}>+ Create course</button>
        </header>
        {creatingCourse && <CreateCourseDialog onClose={() => setCreatingCourse(false)}
          onSubmit={createCourse} saving={savingCourse} error={courseError} />}
        <div className="aid-metrics">
          <Metric label="Total courses" value={courses.length} hint="Courses in your workspace" />
          <Metric label="Student enrollments" value={enrollmentCount ?? "—"} hint="Students enrolled in more than one course are counted in each course" />
          <Metric label="Reflection sets" value={reflectionSets.length} hint="Imported sets and published Reflection assignments" />
          <Metric label="Completed analyses" value={completedAnalyses} hint="Reflection sets with saved results" />
        </div>
        {awaitingAnalysis > 0 && <div className="aid-dashboard-pending">
          <p><strong>{awaitingAnalysis} reflection {awaitingAnalysis === 1 ? "set is" : "sets are"} awaiting analysis.</strong> Open a course to run an analysis.</p>
          <a href="#aid-courses-title">View courses ↓</a>
        </div>}
        <section className="aid-dashboard-courses" aria-labelledby="aid-courses-title">
          <h2 id="aid-courses-title">Your courses</h2>
          {courses.length ? <div className="aid-course-grid">{courses.map(item => {
            const sets = reflectionSets.filter(reflection => String(reflection.course_id) === String(item.course_id));
            const completed = sets.filter(hasCompletedAnalysis).length;
            return <button type="button" className="aid-course-card" key={item.course_id} onClick={() => navigateCourse(item.course_id)}>
              {courseTerms[item.course_id] && <span className="aid-course-term">{courseTerms[item.course_id]}</span>}
              <strong>{item.course_code || item.title}</strong>
              {item.course_code && item.title && <span className="aid-dashboard-course-name">{item.title}</span>}
              <small>{sets.length} reflection {sets.length === 1 ? "set" : "sets"} · {completed} analyzed · {sets.length - completed} awaiting analysis</small>
              <span className="aid-text-action">Open course →</span>
            </button>;
          })}</div> : <div className="aid-empty"><h3>No courses yet</h3><p>Create a course or open a Canvas course you teach to get started.</p></div>}
        </section>
      </div>
    </> : !selected ? <>
      {header(`Course workspace · ${course.course_code || "Course"}`, course.title || course.course_code, "Collect Reflection responses, open an assignment, and explore what students shared.")}
      <section className="aid-section" aria-labelledby="aid-assignments-title"><div className="aid-section-heading"><div><h2 id="aid-assignments-title">{courseAssignments.some(item=>item.tool === "socratic") ? "Reflection assignments & step surveys" : "Reflection assignments"}</h2><p>{courseAssignments.length} reflection sets in this course. Imported CSVs are saved in this browser.</p></div><button onClick={() => beginImport()}>+ Add reflection</button></div>
        {courseAssignments.length ? <div className="aid-assignment-list">{courseAssignments.map(item => <button className="aid-assignment-row" type="button" key={item.id} onClick={() => openAssignment(item.id)}><span><strong>{item.title}</strong><small>{item.tool === "socratic" ? "Socratic step surveys" : "BrainTutor Reflection"} · {item.completed_count || 0} completed</small></span><span className="aid-text-action">{ready[item.id] ? "Explore results →" : "Set up analysis →"}</span></button>)}</div> : <div className="aid-empty aid-reflection-empty">
          <span className="aid-empty-icon" aria-hidden="true">✦</span>
          <h3>No reflection sets yet</h3>
          <p>Use <strong>Add reflection</strong> to import a reflection CSV for this course.</p>
        </div>}
      </section>
    </> : <>
      {header(
        "Reflection workspace",
        selected.title,
        `${course.course_code || course.title} · ${selected.completed_count || 0} submissions`,
        selected.overview && <button type="button" className="aid-replace-data" disabled={analyzing} onClick={() => beginImport(selected.id)}>Replace data</button>,
      )}
      {!analysis ? <div className="aid-empty aid-ready"><span className="aid-empty-icon">◌</span><h2>Ready for analysis</h2><p>Open the saved responses and participation counts for this assignment.</p><div className="aid-progress-steps"><span className="done">✓ Reflection selected</span><span>Review responses</span><span>Explore results</span></div><button type="button" onClick={() => runAnalysis()} disabled={analyzing}>{analyzing ? "Opening analysis…" : "Run analysis"}</button></div> : <>
        <div className="aid-result-banner"><div className="aid-result-status"><strong>Results ready</strong><span>Review the responses or download an HTML report.</span></div><button type="button" onClick={downloadInstructorReport} disabled={exporting || analyzing}>{exporting ? "Building report…" : "Download Instructor Report"}</button></div>
        <div className="aid-tabs" role="tablist" aria-label="Analysis views">{[["overview", "Overview"], ["students", "Students"], ["surveys", "Step surveys"], ["details", "Reflection details"]].map(([id, label]) => <button type="button" role="tab" aria-selected={tab === id} key={id} onClick={() => setTab(id)}>{label}</button>)}</div>
        {analysis.findings && tab === "overview" && <section className="aid-section">
          <h2>Topic analysis</h2>
          <p>{analysis.findings.filter(record => record.analysis).length} of {analysis.summary.completed} reflections analyzed. Open Reflection details for topics, resolution status, urgency, summaries, and suggested actions.</p>
        </section>}
        {tab === "overview" && <>
          <section className="aid-start"><span className="aid-eyebrow">Start here · Reflection results</span><h2>Start with the basics</h2><p>See how many students responded, then open their reflections when you need more detail.</p></section>
          <div className="aid-metrics"><Metric label="Assigned students" value={analysis.summary.assigned} hint="Students assigned this activity"/><Metric label="Started" value={analysis.summary.started} hint="Students who opened it"/><Metric label="Completed" value={analysis.summary.completed} hint="Finished assignments"/><Metric label="Student responses" value={analysis.summary.responses} hint="Saved messages from students"/></div>
          <div className="aid-overview-grid"><section className="aid-section"><span className="aid-eyebrow">01 · Notice participation</span><h2>Assignment progress</h2><p>{analysis.summary.completed} of {analysis.summary.assigned} assigned students completed this Reflection.</p><div className="aid-progress-track"><div style={{width: `${analysis.summary.assigned ? Math.round(analysis.summary.completed / analysis.summary.assigned * 100) : 0}%`}}/></div><button className="aid-link" type="button" onClick={() => setTab("students")}>Review student responses →</button></section><section className="aid-section"><span className="aid-eyebrow">02 · Understand the data</span><h2>What this view shows</h2><p>Participation counts and original student messages from this Reflection assignment.</p><button className="aid-link" type="button" onClick={() => setTab("details")}>See reflection details →</button></section></div>
        </>}
        {tab === "students" && <AiducateStudentProfiles key={selected.id} analysis={analysis} />}
        {tab === "surveys" && <section className="aid-section"><span className="aid-eyebrow">Ungraded · Student self-reports</span><h2>Step survey responses</h2><p>Responses are grouped by learning step and survey version. Confidence is self-reported and does not establish mastery.</p><Link className="button compact" to={`/professor/activities/${selected.id}/settings`}>Edit step surveys</Link>
          {surveyAnalysis?.groups?.length ? surveyAnalysis.groups.map(group=><section className="survey-analysis-group" key={`${group.step_index}:${group.survey.version}`}><h3>Step {group.step_index+1}: {group.step_title}</h3><p><strong>{group.survey.title}</strong> · {group.responses.length} submissions · Published {new Date(group.survey.published_at).toLocaleDateString()}</p>{group.responses.map(response=><details key={response.student_id}><summary>{response.name} · View responses</summary><time>{new Date(response.submitted_at).toLocaleString()}</time>{group.survey.questions.map(question=><blockquote key={question.id}><strong>{question.prompt}</strong><p>{question.kind === "confidence" ? `${response.answers[question.id]} / 5 (self-reported)` : response.answers[question.id]}</p></blockquote>)}</details>)}</section>) : <p>No step survey responses yet. Publish a survey in assignment settings and invite students to respond.</p>}
        </section>}
        {tab === "details" && <section className="aid-section">
          <h2>Reflection details</h2>
          {reportPreview?.analysis !== analysis ? <p role="status">Building instructor report…</p>
            : reportPreview.error ? <Notice error={reportPreview.error} />
            : <iframe className="aid-reflection-report" title="Instructor reflection report" sandbox="allow-scripts" srcDoc={reportPreview.html} />}
        </section>}
      </>}
    </>}
    </div></div>
  </div>;
}
