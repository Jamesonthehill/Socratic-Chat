import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Notice } from "./ui";
import {
  csvExport,
  download,
  readable,
  reportHtml,
  resultCsv,
} from "./reflection-analysis-export";
import "./reflection-analysis.css";

const views = ["Workflow", "Analysis", "Summarization", "Data cleaning"];
const labelFor = (value) => readable(value);

export default function ReflectionAnalysis() {
  const [tab, setTab] = useState("Workflow");
  const [config, setConfig] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [assignmentId, setAssignmentId] = useState("");
  const [records, setRecords] = useState([]);
  const [title, setTitle] = useState("Imported reflections");
  const [source, setSource] = useState(null);
  const [mapping, setMapping] = useState({
    id_column: "",
    name_column: "",
    grade_column: "",
    response_columns: [],
  });
  const [warnings, setWarnings] = useState([]);
  const [results, setResults] = useState([]);
  const [model, setModel] = useState("");
  const [context, setContext] = useState("");
  const [batchSize, setBatchSize] = useState(10);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState("");
  const [urgency, setUrgency] = useState("");
  const [unresolvedOnly, setUnresolvedOnly] = useState(false);
  const [minGrade, setMinGrade] = useState("");
  const [maxGrade, setMaxGrade] = useState("");
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    Promise.allSettled([
      api("/platform/reflection-analysis/config"),
      api("/platform/assignments"),
    ])
      .then(([configuration, items]) => {
        if (!alive.current) return;
        if (configuration.status === "fulfilled")
          setConfig(configuration.value);
        if (items.status === "fulfilled") {
          setAssignments(
            items.value.filter(
              (item) =>
                item.tool === "reflections" && item.can_manage !== false,
            ),
          );
        }
        const failed = [configuration, items].find(
          (result) => result.status === "rejected",
        );
        if (failed) setError(failed.reason.message);
      })
      .catch((e) => alive.current && setError(e.message));
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    if (!records.length) return;
    const warn = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [records.length]);

  async function perform(message, work) {
    setBusy(message);
    setError("");
    try {
      await work();
    } catch (e) {
      if (alive.current) setError(e.message);
    } finally {
      if (alive.current) setBusy("");
    }
  }
  function loadRecords(items, name, notes = []) {
    setRecords(items);
    setTitle(name);
    setWarnings(notes);
    setResults([]);
    setModel("");
    setQuery("");
    setTopic("");
    setUrgency("");
    setUnresolvedOnly(false);
    setMinGrade("");
    setMaxGrade("");
  }
  async function inspect(file) {
    if (!file) return;
    await perform("Reading CSV…", async () => {
      if (file.size > 2_000_000) throw Error("Choose a CSV smaller than 2 MB.");
      const content = await file.text();
      const preview = await api("/platform/reflection-analysis/import", {
        method: "POST",
        body: { content },
      });
      if (!alive.current) return;
      setSource({ ...preview, content, name: file.name });
      const guess = (names) =>
        preview.columns.find((column) =>
          names.includes(column.toLowerCase()),
        ) || "";
      setMapping({
        id_column: guess([
          "student_id",
          "id",
          "student id",
          "email",
          "sis login id",
        ]),
        name_column: guess(["name", "student"]),
        grade_column: guess(["grade", "current score", "score"]),
        response_columns: [],
      });
    });
  }
  const pending = records
    .map((record, index) => ({ ...record, index }))
    .filter(
      (record) =>
        !results.some((row) => row.index === record.index && row.analysis),
    );
  async function analyze() {
    await perform("Analyzing reflections…", async () => {
      const batch = pending.slice(0, batchSize);
      const data = await api("/platform/reflection-analysis/analyze", {
        method: "POST",
        body: { records: batch.map(({ index, ...record }) => record), context },
      });
      if (!alive.current) return;
      const updated = data.results.map((row, index) => ({
        ...row,
        index: batch[index].index,
      }));
      setResults((previous) =>
        [
          ...previous.filter(
            (row) => !updated.some((next) => next.index === row.index),
          ),
          ...updated,
        ].sort((a, b) => a.index - b.index),
      );
      setModel(data.model);
      if (data.summary.failed)
        setError(
          `${data.summary.failed} reflection(s) could not be analyzed. Successful results are available; run the next batch to retry failed reflections.`,
        );
    });
  }
  const successful = results.filter((row) => row.analysis);
  const topicCounts = {};
  successful.forEach((row) =>
    row.analysis.primary_labels_selected.forEach((name, index) => {
      topicCounts[name] ||= { count: 0, unresolved: 0 };
      topicCounts[name].count++;
      if (row.analysis.resolution_primary_labels[index] === "unresolved")
        topicCounts[name].unresolved++;
    }),
  );
  const visible = successful.filter(
    (row) =>
      (!query ||
        `${row.name} ${row.student_id} ${row.text} ${row.analysis.reflection_summary}`
          .toLowerCase()
          .includes(query.toLowerCase())) &&
      (!topic || row.analysis.primary_labels_selected.includes(topic)) &&
      (!urgency || row.analysis.urgency === urgency) &&
      (!unresolvedOnly ||
        row.analysis.resolution_primary_labels.includes("unresolved")) &&
      (minGrade === "" ||
        (row.grade != null && row.grade >= Number(minGrade))) &&
      (maxGrade === "" || (row.grade != null && row.grade <= Number(maxGrade))),
  );
  const unresolved = successful.filter((row) =>
    row.analysis.resolution_primary_labels.includes("unresolved"),
  ).length;
  const high = successful.filter(
    (row) => row.analysis.urgency === "high",
  ).length;
  const grades = successful
    .filter((row) => row.grade != null)
    .map((row) => row.grade);
  const exportReport = (rows) =>
    download(
      "reflection-report.html",
      reportHtml(title, rows, model),
      "text/html;charset=utf-8",
    );

  return (
    <div className="reflection-analysis">
      <div className="page-heading">
        <div>
          <h1>Reflection analysis</h1>
          <p>
            Understand student challenges and plan your next classroom
            conversation.
          </p>
        </div>
        {results.length > 0 && (
          <button className="secondary" onClick={() => exportReport(results)}>
            Download report
          </button>
        )}
      </div>
      <Notice error={error} />
      <div
        className="ra-tabs"
        role="tablist"
        aria-label="Reflection analysis tools"
      >
        {views.map((view) => (
          <button
            id={`ra-tab-${view.replaceAll(" ", "-")}`}
            aria-controls="ra-panel"
            type="button"
            role="tab"
            aria-selected={tab === view}
            key={view}
            onClick={() => setTab(view)}
          >
            {view}
          </button>
        ))}
      </div>
      <div
        id="ra-panel"
        role="tabpanel"
        aria-labelledby={`ra-tab-${tab.replaceAll(" ", "-")}`}
      >
        {tab === "Workflow" && (
          <>
            <section className="panel">
              <h2>Choose your reflections</h2>
              <p>
                Open a Reflection assignment you manage, or import a CSV from
                your course.
              </p>
              <div className="ra-source-grid">
                <div>
                  <label>
                    CourseLab assignment
                    <select
                      value={assignmentId}
                      disabled={!!busy}
                      onChange={(event) => setAssignmentId(event.target.value)}
                    >
                      <option value="">Select an assignment</option>
                      {assignments.map((item) => (
                        <option value={item.id} key={item.id}>
                          {item.course_code || item.course_title} — {item.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    disabled={!assignmentId || !!busy}
                    onClick={() =>
                      perform("Loading responses…", async () => {
                        const data = await api(
                          `/platform/assignments/${assignmentId}/reflection-analysis`,
                        );
                        if (!alive.current) return;
                        const items = data.students
                          .filter((student) => student.responses.length)
                          .map((student) => ({
                            student_id: String(student.student_id),
                            name: student.name,
                            text: student.responses.join("\n\n"),
                            grade: null,
                          }));
                        loadRecords(items, data.assignment.title, [
                          `${data.summary.assigned - items.length} assigned student(s) have no saved responses. Saved responses include work in progress.`,
                        ]);
                      })
                    }
                  >
                    Load assignment
                  </button>
                  {config && !assignments.length && (
                    <p className="help">
                      No Reflection assignments you manage are available.
                    </p>
                  )}
                </div>
                <div>
                  <label>
                    Reflection CSV or TSV
                    <input
                      type="file"
                      accept=".csv,.tsv,text/csv,text/tab-separated-values"
                      disabled={!!busy}
                      onChange={(event) => {
                        inspect(event.target.files?.[0]);
                        event.target.value = "";
                      }}
                    />
                  </label>
                  <p className="help">
                    Up to 2 MB and 5,000 rows. Map student IDs and response
                    columns before importing.
                  </p>
                  <button
                    className="quiet"
                    onClick={() =>
                      download(
                        "reflection-template.csv",
                        csvExport([
                          [
                            "Student_ID",
                            "Name",
                            "Grade",
                            "Q1: What was challenging?",
                            "Q2: How did you address it?",
                          ],
                          ["example-001", "Example student", "", "", ""],
                        ]),
                        "text/csv",
                      )
                    }
                  >
                    Download CSV template
                  </button>
                </div>
              </div>
            </section>
            {source && (
              <section className="panel">
                <h2>Map columns · {source.name}</h2>
                <p>
                  {source.row_count} nonempty rows. Only selected response
                  columns are sent for analysis.
                </p>
                <div className="ra-mapping">
                  {[
                    ["id_column", "Student ID"],
                    ["name_column", "Student name (optional)"],
                    ["grade_column", "Grade 0–100 (optional)"],
                  ].map(([key, name]) => (
                    <label key={key}>
                      {name}
                      <select
                        value={mapping[key]}
                        disabled={!!busy}
                        onChange={(event) =>
                          setMapping((previous) => ({
                            ...previous,
                            [key]: event.target.value,
                          }))
                        }
                      >
                        <option value="">Select a column</option>
                        {source.columns.map((column) => (
                          <option key={column}>{column}</option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
                <fieldset disabled={!!busy}>
                  <legend>Reflection response columns</legend>
                  <div className="ra-checkboxes">
                    {source.columns.map((column) => (
                      <label key={column}>
                        <input
                          type="checkbox"
                          checked={mapping.response_columns.includes(column)}
                          onChange={(event) =>
                            setMapping((previous) => ({
                              ...previous,
                              response_columns: event.target.checked
                                ? [...previous.response_columns, column]
                                : previous.response_columns.filter(
                                    (value) => value !== column,
                                  ),
                            }))
                          }
                        />
                        {column}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <details>
                  <summary>Preview first five rows</summary>
                  <div className="ra-table-scroll">
                    <table>
                      <thead>
                        <tr>
                          {source.columns.map((column) => (
                            <th key={column}>{column}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {source.preview.map((row, index) => (
                          <tr key={index}>
                            {source.columns.map((column) => (
                              <td key={column}>{row[column]}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
                <button
                  disabled={
                    !!busy ||
                    !mapping.id_column ||
                    !mapping.response_columns.length
                  }
                  onClick={() =>
                    perform("Importing reflections…", async () => {
                      const data = await api(
                        "/platform/reflection-analysis/import",
                        {
                          method: "POST",
                          body: { content: source.content, ...mapping },
                        },
                      );
                      if (alive.current)
                        loadRecords(
                          data.records,
                          source.name.replace(/\.(csv|tsv)$/i, ""),
                          data.warnings,
                        );
                    })
                  }
                >
                  Import reflections
                </button>
              </section>
            )}
            <section className="panel">
              <h2>{records.length ? title : "Your reflection workspace"}</h2>
              <p>
                {records.length
                  ? `${records.length} reflections loaded. ${successful.length} analyzed.`
                  : "Select an assignment or import a CSV to begin."}
              </p>
              <p className="help">
                This workspace lasts while this page is open. Download your data
                and results before leaving.
              </p>
              {records.length > 0 && (
                <button onClick={() => setTab("Analysis")}>
                  Continue to analysis
                </button>
              )}
            </section>
          </>
        )}
        {tab === "Analysis" && (
          <>
            <section className="panel">
              <h2>Analyze student challenges</h2>
              <p>
                Classify topics, urgency, and whether each challenge is
                resolved. Review AI annotations alongside the original
                reflections.
              </p>
              <label>
                Course context (optional)
                <textarea
                  maxLength={3000}
                  rows={3}
                  disabled={!!busy || successful.length > 0}
                  value={context}
                  onChange={(event) => setContext(event.target.value)}
                  placeholder="Course subject, activities, and concepts students are reflecting on"
                />
              </label>
              {successful.length > 0 && (
                <p className="help">
                  Course context is fixed for this analysis. Reload the dataset
                  to start again with different context.
                </p>
              )}
              <div className="ra-actions">
                <label>
                  Reflections in next batch
                  <select
                    value={batchSize}
                    disabled={!!busy}
                    onChange={(event) =>
                      setBatchSize(Number(event.target.value))
                    }
                  >
                    {[1, 5, 10, 20, 50].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  disabled={
                    !!busy || !pending.length || !config?.model_configured
                  }
                  onClick={analyze}
                >
                  {successful.length
                    ? "Analyze next batch / retry failures"
                    : "Run topic analysis"}
                </button>
              </div>
              <p className="help">
                {pending.length} reflections remaining. Analysis uses the
                configured AI model. Larger batches can take several minutes.
              </p>
              {config && !config.model_configured && (
                <Notice>
                  A generation model must be configured before running topic
                  analysis. CSV preparation and exports are available.
                </Notice>
              )}
              <details>
                <summary>
                  Challenge labels from the original analysis tool
                </summary>
                <dl>
                  {Object.entries(config?.labels || {}).map(
                    ([name, definition]) => (
                      <div key={name}>
                        <dt>{labelFor(name)}</dt>
                        <dd>{definition}</dd>
                      </div>
                    ),
                  )}
                </dl>
              </details>
            </section>
            {successful.length > 0 && (
              <section className="panel">
                <h2>Topics across reflections</h2>
                <p>
                  {successful.length} analyzed · {unresolved} with unresolved
                  challenges · {high} high urgency
                </p>
                {Object.entries(topicCounts)
                  .sort((a, b) => b[1].count - a[1].count)
                  .map(([name, counts]) => (
                    <div className="ra-topic" key={name}>
                      <span>{labelFor(name)}</span>
                      <meter
                        aria-label={`${labelFor(name)} reflections`}
                        min={0}
                        max={successful.length}
                        value={counts.count}
                      />
                      <strong>{counts.count}</strong>
                      <small>{counts.unresolved} unresolved</small>
                    </div>
                  ))}
                <div className="ra-actions">
                  <button
                    className="secondary"
                    onClick={() =>
                      download(
                        "reflection-analysis.csv",
                        resultCsv(results),
                        "text/csv;charset=utf-8",
                      )
                    }
                  >
                    Download analysis CSV
                  </button>
                  <button onClick={() => setTab("Summarization")}>
                    Explore student summaries
                  </button>
                </div>
              </section>
            )}
            {!!results.filter((row) => row.error).length && (
              <section className="panel">
                <h2>Reflections to retry</h2>
                {results
                  .filter((row) => row.error)
                  .map((row) => (
                    <p key={row.index}>
                      {row.name || row.student_id}: {row.error}
                    </p>
                  ))}
              </section>
            )}
          </>
        )}
        {tab === "Summarization" && (
          <>
            <section className="panel">
              <h2>Class summary</h2>
              {successful.length ? (
                <>
                  <p>
                    Of {successful.length} analyzed reflections, {unresolved}{" "}
                    include an unresolved challenge and {high} have high
                    urgency.
                  </p>
                  <p>
                    {grades.length
                      ? `Average supplied grade: ${(grades.reduce((sum, grade) => sum + grade, 0) / grades.length).toFixed(1)}% across ${grades.length} graded reflections.`
                      : "No grades supplied. Grades are never inferred from reflections."}
                  </p>
                  <h3>Topic summaries</h3>
                  {Object.entries(topicCounts).map(([name, counts]) => (
                    <p key={name}>
                      <strong>{labelFor(name)}</strong>: {counts.count}{" "}
                      reflection(s), {counts.unresolved} unresolved.
                    </p>
                  ))}
                  <p className="help">
                    Counts summarize successful AI annotations only. Topic
                    counts can overlap because a reflection may mention multiple
                    challenges.
                  </p>
                </>
              ) : (
                <p>
                  Run topic analysis to generate class, topic, and student
                  summaries.
                </p>
              )}
            </section>
            {successful.length > 0 && (
              <section className="panel">
                <h2>Student summaries</h2>
                <div className="ra-filters">
                  <label>
                    Search students and reflections
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                    />
                  </label>
                  <label>
                    Topic
                    <select
                      value={topic}
                      onChange={(event) => setTopic(event.target.value)}
                    >
                      <option value="">All topics</option>
                      {Object.keys(topicCounts).map((name) => (
                        <option value={name} key={name}>
                          {labelFor(name)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Urgency
                    <select
                      value={urgency}
                      onChange={(event) => setUrgency(event.target.value)}
                    >
                      <option value="">All urgency levels</option>
                      {["none", "low", "medium", "high"].map((name) => (
                        <option key={name}>{name}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Minimum grade
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={minGrade}
                      onChange={(event) => setMinGrade(event.target.value)}
                    />
                  </label>
                  <label>
                    Maximum grade
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={maxGrade}
                      onChange={(event) => setMaxGrade(event.target.value)}
                    />
                  </label>
                </div>
                <label className="ra-check">
                  <input
                    type="checkbox"
                    checked={unresolvedOnly}
                    onChange={(event) =>
                      setUnresolvedOnly(event.target.checked)
                    }
                  />
                  Unresolved challenges only
                </label>
                <div className="ra-actions">
                  <p>{visible.length} matching reflections</p>
                  <button
                    className="secondary"
                    disabled={!visible.length}
                    onClick={() => exportReport(visible)}
                  >
                    Download filtered report
                  </button>
                </div>
                {!visible.length && <p>No reflections match these filters.</p>}
                {visible.map((row) => (
                  <details key={row.index} className="ra-student">
                    <summary>
                      <strong>{row.name || row.student_id}</strong>
                      <span>
                        {row.analysis.urgency} urgency
                        {row.grade == null ? "" : ` · ${row.grade}%`}
                      </span>
                    </summary>
                    <ul>
                      {row.analysis.primary_labels_selected.map(
                        (name, index) => (
                          <li key={name}>
                            {labelFor(name)}:{" "}
                            {row.analysis.resolution_primary_labels[index]}
                          </li>
                        ),
                      )}
                    </ul>
                    <p>{row.analysis.reflection_summary}</p>
                    <h3>Instructor suggestions</h3>
                    <p>{row.analysis.instructor_suggestions}</p>
                    <h3>Original reflection</h3>
                    <blockquote>{row.text}</blockquote>
                    <button
                      className="quiet"
                      onClick={() => exportReport([row])}
                    >
                      Download student report
                    </button>
                  </details>
                ))}
              </section>
            )}
          </>
        )}
        {tab === "Data cleaning" && (
          <section className="panel">
            <h2>Review and export prepared data</h2>
            <p>
              CSV and TSV imports trim whitespace, preserve student IDs
              (including leading zeros), skip empty IDs or responses, and flag
              repeated IDs. Repeated IDs remain separate reflections.
            </p>
            {warnings.length > 0 && (
              <details open>
                <summary>{warnings.length} import note(s)</summary>
                <ul>
                  {warnings.slice(0, 100).map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
                {warnings.length > 100 && <p>Showing the first 100 notes.</p>}
              </details>
            )}
            {records.length ? (
              <>
                <div className="ra-actions">
                  <button
                    className="secondary"
                    onClick={() =>
                      download(
                        "prepared-reflections.csv",
                        csvExport([
                          ["Student_ID", "Name", "Reflection", "Grade"],
                          ...records.map((row) => [
                            row.student_id,
                            row.name,
                            row.text,
                            row.grade,
                          ]),
                        ]),
                        "text/csv;charset=utf-8",
                      )
                    }
                  >
                    Download prepared CSV
                  </button>
                </div>
                <div className="ra-table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Grade</th>
                        <th>Reflection</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.slice(0, 100).map((row, index) => (
                        <tr key={index}>
                          <td>{row.student_id}</td>
                          <td>{row.name}</td>
                          <td>{row.grade ?? "Not supplied"}</td>
                          <td>{row.text}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="help">
                  Showing the first {Math.min(records.length, 100)} of{" "}
                  {records.length} reflections. The download includes all
                  prepared rows.
                </p>
              </>
            ) : (
              <p>Load reflections in Workflow to review the prepared data.</p>
            )}
          </section>
        )}
      </div>
      {busy && (
        <p className="ra-busy" role="status">
          {busy}
        </p>
      )}
    </div>
  );
}
