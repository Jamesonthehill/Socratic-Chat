import { useState } from "react";
import { readable } from "./reflection-analysis-export";

export default function AiducateStudentProfiles({ analysis }) {
  const [query, setQuery] = useState("");
  const [submission, setSubmission] = useState("submitted");
  const [topic, setTopic] = useState("");
  const [expanded, setExpanded] = useState(null);

  const findings = new Map((analysis.findings || []).map(record => [record.student_id, record.analysis]));
  const profiles = analysis.students.map(student => {
    const finding = findings.get(student.student_id);
    return { student, finding, topics: finding?.primary_labels_selected || [] };
  });
  const topics = [...new Set(profiles.flatMap(profile => profile.topics))].sort();
  const search = query.trim().toLocaleLowerCase();
  const filtered = profiles.filter(({ student, topics }) =>
    (!submission || (submission === "submitted") === Boolean(student.responses.length))
    && (!topic || topics.includes(topic))
    && [student.name, student.student_id, ...topics.map(readable), ...student.responses]
      .join(" ").toLocaleLowerCase().includes(search),
  );
  const submitted = profiles.filter(({ student }) => student.responses.length).length;
  const activeFilters = Number(Boolean(submission)) + Number(Boolean(topic)) + Number(Boolean(search));

  return <section className="aid-section aid-profiles" aria-labelledby="aid-profiles-title">
    <header className="aid-profiles-header">
      <h2 id="aid-profiles-title">Student Profiles</h2>
      <p>Browse students and read their responses for this reflection.</p>
    </header>
    <div className="aid-profiles-body">
      <div className="aid-profile-filter">
        <details>
          <summary><strong>Filter students</strong> <small>{activeFilters} active</small></summary>
          <div className="aid-profile-fields">
            <label>Responses<select value={submission} onChange={event => setSubmission(event.target.value)}>
              <option value="">All students</option>
              <option value="submitted">With responses</option>
              <option value="empty">Without responses</option>
            </select></label>
            {topics.length > 0 && <label>Topic<select value={topic} onChange={event => setTopic(event.target.value)}>
              <option value="">All topics</option>
              {topics.map(value => <option key={value} value={value}>{readable(value)}</option>)}
            </select></label>}
          </div>
        </details>
        <button type="button" className="aid-link" onClick={() => { setQuery(""); setSubmission(""); setTopic(""); }}>Clear all filters</button>
      </div>
      <input className="aid-profile-search" aria-label="Search names, IDs, topics, or reflections"
        placeholder="Search names, IDs, topics, or reflections" type="search" value={query} onChange={event => setQuery(event.target.value)} />
      <p className="aid-profile-count" role="status">Showing {filtered.length} of {profiles.length} students · {submitted} with responses</p>
      {filtered.length ? <div className="aid-profile-table-wrap" role="region" aria-label="Student profiles table" tabIndex={0}>
        <table className="aid-profile-table">
          <thead><tr><th scope="col">Student / ID</th><th scope="col">Topics identified</th><th scope="col">Student tags</th><th scope="col">Reflection</th></tr></thead>
          {filtered.map(({ student, topics, finding }) => {
            const { student_id: id, name, responses, gradeLabel } = student;
            const isOpen = expanded === id;
            return <tbody key={id}>
              <tr>
                <th scope="row"><strong>{name}</strong><small>ID: {id}</small></th>
                <td>{topics.length ? <div className="aid-profile-tags">{topics.map(value => <span className="aid-profile-tag topic" key={value}>{readable(value)}</span>)}</div> : <small>—</small>}</td>
                <td><div className="aid-profile-tags">
                  {gradeLabel && <span className="aid-profile-tag grade">{gradeLabel}</span>}
                  <span className={responses.length ? "aid-profile-tag submitted" : "aid-profile-tag"}>{responses.length ? "Submitted" : "No response"}</span>
                </div>
                {finding && <details className="aid-extra-tags"><summary>View all tags</summary><div className="aid-profile-tags">
                  {finding.urgency && <span className="aid-profile-tag">Urgency: {finding.urgency}</span>}
                  {[...new Set(finding.resolution_primary_labels || [])].map(value => <span className="aid-profile-tag" key={value}>{readable(value)}</span>)}
                </div></details>}</td>
                <td>{responses.length > 0 && <button type="button" className="aid-link" aria-expanded={isOpen}
                  aria-label={`${isOpen ? "Hide" : "View"} reflections for ${name}`}
                  onClick={() => setExpanded(isOpen ? null : id)}>{isOpen ? "Hide ↑" : "View →"}</button>}</td>
              </tr>
              {isOpen && <tr className="aid-profile-responses"><td colSpan={4}>
                <strong>Reflection responses</strong>
                <ol>{responses.map((response, index) => <li key={index}>{response}</li>)}</ol>
              </td></tr>}
            </tbody>;
          })}
        </table>
      </div> : <p className="aid-no-results">{submitted ? "No students match these filters." : "This reflection has no saved responses."}</p>}
    </div>
  </section>;
}
