import { useRef, useState } from "react";

export function parseSurveyCsv(text, { grading = false } = {}) {
  if (text.length > 2 * 1024 * 1024) throw Error("Choose a CSV smaller than 2 MB.");
  const rows = []; let row = [], value = "", quoted = false;
  text = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { value += '"'; i++; }
      else if (quoted || !value) quoted = !quoted;
      else throw Error("Invalid CSV quotation marks.");
    } else if (!quoted && (c === "," || c === "\n" || c === "\r")) {
      row.push(value); value = "";
      if (c !== ",") { if (row.some(v => v.trim())) rows.push(row); row = []; if (c === "\r" && text[i + 1] === "\n") i++; }
    } else value += c;
  }
  if (quoted) throw Error("The CSV has an unfinished quoted response.");
  row.push(value); if (row.some(v => v.trim())) rows.push(row);
  if (rows.length < 2) throw Error("The CSV needs question headers and at least one response row.");
  const headers = rows.shift().map(h => h.trim());
  if (headers.length > 150 || rows.length > 5000) throw Error("Use at most 150 columns and 5,000 rows.");
  if (headers.some(h => !h) || new Set(headers).size !== headers.length) throw Error("Each column needs a distinct, nonempty header.");
  if (rows.some(r => r.length !== headers.length)) throw Error("Some rows do not match the number of column headers.");
  const gradebook = headers.some(h => /^(current score|final score|homework current score)$/i.test(h)) || rows.some(r => /^\s*points possible\s*$/i.test(r[0]));
  if (gradebook && !grading) throw Error("This looks like a gradebook export. Use the Grading CSV upload instead.");
  if (grading) {
    const pointsRow = rows.find(r => /^\s*points possible\s*$/i.test(r[0]));
    const records = rows.filter(r => !/^\s*points possible\s*$/i.test(r[0]) && !r.some(v => /^\s*(manual|automatic) posting\s*$/i.test(v)));
    if (!records.length) throw Error("The grading CSV has no student records.");
    return { headers, rows: records, points: pointsRow || null, excludedRows: rows.length - records.length };
  }
  return { headers, rows };
}

const metadata = /^(id|student|student id|name|section|sis.*|.*email.*|.*submitted.*|attempt|.*score.*|.*points.*|.*time.*)$/i;
export const normalizeStudentId = value => String(value || "").trim().toLowerCase().split("@")[0];
export function matchStudentGrades(reflection, grading, reflectionKey, gradeKey) {
  const index = new Map();
  for (const row of grading.rows) {
    const id = normalizeStudentId(row[gradeKey]);
    if (id) index.set(id, [...(index.get(id) || []), row]);
  }
  return reflection.rows.map(row => {
    const id = normalizeStudentId(row[reflectionKey]);
    const matches = id ? index.get(id) || [] : [];
    return { status: !id ? "Missing ID" : matches.length > 1 ? "Duplicate grading ID" : matches.length === 1 ? "Matched" : "No grade match", grade: matches.length === 1 ? matches[0] : null };
  });
}
const findColumn = (headers, names) => {
  for (const name of names) { const i = headers.findIndex(h => h.toLowerCase() === name); if (i >= 0) return i; }
  return -1;
};

export default function CanvasSurveyImport({ onUse }) {
  const input = useRef(null);
  const [data, setData] = useState(null), [selected, setSelected] = useState([]), [error, setError] = useState("");
  const [busy, setBusy] = useState(false), [review, setReview] = useState(false);
  const gradeInput = useRef(null);
  const [grades, setGrades] = useState(null), [gradeError, setGradeError] = useState("");
  const [reflectionKey, setReflectionKey] = useState(-1), [gradeKey, setGradeKey] = useState(-1), [gradeColumn, setGradeColumn] = useState(-1);
  async function upload(file) {
    setData(null); setReview(false); setError("");
    if (!file) return;
    if (!/\.csv$/i.test(file.name) || file.size > 2 * 1024 * 1024) { setError("Choose a CSV file up to 2 MB."); return; }
    setBusy(true);
    try { const parsed = parseSurveyCsv(await file.text()); setData({ ...parsed, filename: file.name }); setSelected(parsed.headers.map((h, i) => metadata.test(h) ? -1 : i).filter(i => i >= 0)); setReflectionKey(findColumn(parsed.headers, ["sis user id", "sis login id", "email", "id", "student id"])); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  }
  async function uploadGrades(file) {
    if (!file) return;
    setGrades(null); setGradeError(""); setReview(false);
    if (!/\.csv$/i.test(file.name) || file.size > 2 * 1024 * 1024) { setGradeError("Choose a grading CSV file up to 2 MB."); return; }
    setBusy(true);
    try {
      const parsed = parseSurveyCsv(await file.text(), { grading: true });
      setGrades({ ...parsed, filename: file.name });
      setGradeKey(findColumn(parsed.headers, ["sis login id", "sis user id", "email", "id", "student id"]));
      setGradeColumn(findColumn(parsed.headers, ["current score", "current grade"]));
    } catch (e) { setGradeError(e.message); }
    finally { setBusy(false); if (gradeInput.current) gradeInput.current.value = ""; }
  }
  const responded = data?.rows.filter(r => selected.some(i => r[i].trim())) || [];
  const matches = data && grades && reflectionKey >= 0 && gradeKey >= 0 ? matchStudentGrades(data, grades, reflectionKey, gradeKey) : null;
  const scoreColumns = grades?.headers.map((h, i) => i).filter(i => !metadata.test(grades.headers[i]) || /score/i.test(grades.headers[i])) || [];
  return <section className="aid-section" aria-label="Canvas survey CSV import">
    <span className="aid-eyebrow">Canvas responses & grades</span><h2>Import Canvas survey CSV</h2>
    <p>Upload reflection responses and, optionally, a grading CSV. Match students by a shared ID, then review grades beside their responses.</p>
    <p className="help">This preview stays in this browser tab until you leave or clear it. It is not saved to the platform or sent to an AI service.</p>
    <input ref={input} type="file" accept=".csv,text/csv" aria-label="Canvas survey CSV file" hidden onChange={e => upload(e.target.files?.[0])}/>
    <div className="editor-actions"><button type="button" disabled={busy} onClick={() => input.current.click()}>{busy ? "Reading CSV…" : "Upload reflection CSV"}</button>
    <input ref={gradeInput} type="file" accept=".csv,text/csv" aria-label="Grading CSV file" hidden onChange={e => uploadGrades(e.target.files?.[0])}/>
    <button type="button" disabled={busy} onClick={() => gradeInput.current.click()}>Upload grading CSV</button></div>
    {error && <p role="alert">{error}</p>}
    {gradeError && <p role="alert">{gradeError}</p>}
    {grades && <p><strong>{grades.filename}</strong> · {grades.rows.length} student grading records · {grades.excludedRows} gradebook metadata rows excluded</p>}
    {data && <>
      <p><strong>{data.filename}</strong> · {data.rows.length} records</p>
      {grades && <fieldset><legend>Match grading and reflection records</legend>
        <p className="help">Select columns containing the same student identifier. Email addresses are matched using the part before @; capitalization is ignored. Duplicate grading IDs are not joined.</p>
        <label>Reflection student ID<select value={reflectionKey} onChange={e=>{setReflectionKey(Number(e.target.value));setReview(false);}}><option value={-1}>Choose ID column</option>{data.headers.map((h,i)=><option key={i} value={i}>{h}</option>)}</select></label>
        <label>Grading student ID<select value={gradeKey} onChange={e=>{setGradeKey(Number(e.target.value));setReview(false);}}><option value={-1}>Choose ID column</option>{grades.headers.map((h,i)=><option key={i} value={i}>{h}</option>)}</select></label>
        <label>Grade to display<select value={gradeColumn} onChange={e=>{setGradeColumn(Number(e.target.value));setReview(false);}}><option value={-1}>Review without a grade</option>{scoreColumns.map(i=><option key={i} value={i}>{grades.headers[i]}</option>)}</select></label>
        {matches && <p>{matches.filter(m=>m.status === "Matched").length} matched reflection records; {matches.filter(m=>m.status !== "Matched").length} unmatched or ambiguous. {grades.rows.filter(r=>{const id=normalizeStudentId(r[gradeKey]);return id && !data.rows.some(row=>normalizeStudentId(row[reflectionKey])===id);}).length} grading records have no reflection record.</p>}
      </fieldset>}
      <fieldset><legend>Select reflection question columns</legend>{data.headers.map((h, i) => <label key={i} style={{display:"flex",gap:"0.6rem",alignItems:"center",marginBlock:"0.5rem"}}><input style={{width:"auto"}} type="checkbox" checked={selected.includes(i)} onChange={e => { setReview(false); setSelected(e.target.checked ? [...selected, i].sort((a,b)=>a-b) : selected.filter(n => n !== i)); }}/>{h}</label>)}</fieldset>
      <div className="editor-actions"><button type="button" disabled={!selected.length} onClick={() => setReview(true)}>Review imported responses</button><button type="button" className="secondary" onClick={() => {setData(null);setGrades(null);setReview(false);setError("");setGradeError("");}}>Clear imported data</button>{grades && <button type="button" className="secondary" onClick={()=>{setGrades(null);setGradeError("");setReview(false);}}>Remove grading CSV</button>}</div>
      {review && <div aria-live="polite"><h3>Response overview</h3><p><strong>{responded.length}</strong> records contain responses to the selected questions; <strong>{data.rows.length - responded.length}</strong> have no selected responses. These counts do not establish learning or mastery.</p>
        {onUse && <button type="button" onClick={() => {
          const students = data.rows.map((row, n) => {
            const responses = selected.filter(i => row[i].trim()).map(i => data.headers[i] + " — " + row[i]);
            return { student_id: String(n), name: "Record " + (n + 1), responses, response_count: responses.length, status: responses.length ? "completed" : "not_started" };
          });
          onUse(data.filename, { students, summary: { assigned: students.length, started: responded.length, completed: responded.length, responses: students.reduce((sum, s) => sum + s.response_count, 0) } });
        }}>Use these responses in this course</button>}
        {selected.map(i => <details key={i}><summary><strong>{data.headers[i]}</strong> · {data.rows.filter(r=>r[i].trim()).length} responses</summary><ol>{data.rows.map((r,n)=>r[i].trim() ? <li key={n}><strong>Record {n+1}</strong><p style={{whiteSpace:"pre-wrap"}}>{r[i]}</p></li> : null)}</ol></details>)}
        {grades && matches && gradeColumn >= 0 && <><h3>Grades alongside reflections</h3><p>Grades are shown as provided. Blank grades are missing, not zero. These records do not establish that a grade caused a particular reflection.</p><p><strong>{grades.headers[gradeColumn]}</strong>{grades.points?.[gradeColumn]?.trim() ? ` · Points possible: ${grades.points[gradeColumn]}` : ""}</p>
          <div style={{overflowX:"auto"}}><table><thead><tr><th>Record</th><th>Match status</th><th>Grade</th>{selected.map(i=><th key={i}>{data.headers[i]}</th>)}</tr></thead><tbody>{data.rows.map((row,n)=><tr key={n}><td>{n+1}</td><td>{matches[n].status}</td><td>{matches[n].grade ? matches[n].grade[gradeColumn]?.trim() || "Not provided" : "Not matched"}</td>{selected.map(i=><td key={i} style={{whiteSpace:"pre-wrap",minWidth:"12rem"}}>{row[i] || "No response"}</td>)}</tr>)}</tbody></table></div>
        </>}
      </div>}
    </>}
  </section>;
}
