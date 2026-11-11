import { useRef, useState } from "react";

export function parseSurveyCsv(text) {
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
  if (headers.some(h => /^(current score|final score|homework current score)$/i.test(h)) || rows.some(r => /^\s*points possible\s*$/i.test(r[0]))) throw Error("This looks like a gradebook export. Choose a quiz or survey response CSV instead.");
  return { headers, rows };
}

const metadata = /^(id|student|student id|name|section|sis.*|.*email.*|.*submitted.*|attempt|.*score.*|.*points.*|.*time.*)$/i;

export default function CanvasSurveyImport() {
  const input = useRef(null);
  const [data, setData] = useState(null), [selected, setSelected] = useState([]), [error, setError] = useState("");
  const [busy, setBusy] = useState(false), [review, setReview] = useState(false);
  async function upload(file) {
    setData(null); setReview(false); setError("");
    if (!file) return;
    if (!/\.csv$/i.test(file.name) || file.size > 2 * 1024 * 1024) { setError("Choose a CSV file up to 2 MB."); return; }
    setBusy(true);
    try { const parsed = parseSurveyCsv(await file.text()); setData({ ...parsed, filename: file.name }); setSelected(parsed.headers.map((h, i) => metadata.test(h) ? -1 : i).filter(i => i >= 0)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  }
  const responded = data?.rows.filter(r => selected.some(i => r[i].trim())) || [];
  return <section className="aid-section" aria-label="Canvas survey CSV import">
    <span className="aid-eyebrow">Canvas responses</span><h2>Import Canvas survey CSV</h2>
    <p>Export responses from Canvas Quizzes, then choose the questions you want to review.</p>
    <p className="help">This preview stays in this browser tab until you leave or clear it. It is not saved to the platform or sent to an AI service.</p>
    <input ref={input} type="file" accept=".csv,text/csv" aria-label="Canvas survey CSV file" hidden onChange={e => upload(e.target.files?.[0])}/>
    <button type="button" disabled={busy} onClick={() => input.current.click()}>{busy ? "Reading CSV…" : "Choose CSV file"}</button>
    {error && <p role="alert">{error}</p>}
    {data && <>
      <p><strong>{data.filename}</strong> · {data.rows.length} records</p>
      <fieldset><legend>Select reflection question columns</legend>{data.headers.map((h, i) => <label key={i} style={{display:"flex",gap:"0.6rem",alignItems:"center",marginBlock:"0.5rem"}}><input style={{width:"auto"}} type="checkbox" checked={selected.includes(i)} onChange={e => { setReview(false); setSelected(e.target.checked ? [...selected, i].sort((a,b)=>a-b) : selected.filter(n => n !== i)); }}/>{h}</label>)}</fieldset>
      <div className="editor-actions"><button type="button" disabled={!selected.length} onClick={() => setReview(true)}>Review imported responses</button><button type="button" className="secondary" onClick={() => {setData(null);setReview(false);}}>Clear imported data</button></div>
      {review && <div aria-live="polite"><h3>Response overview</h3><p><strong>{responded.length}</strong> records contain responses to the selected questions; <strong>{data.rows.length - responded.length}</strong> have no selected responses. These counts do not establish learning or mastery.</p>
        {selected.map(i => <details key={i}><summary><strong>{data.headers[i]}</strong> · {data.rows.filter(r=>r[i].trim()).length} responses</summary><ol>{data.rows.map((r,n)=>r[i].trim() ? <li key={n}><strong>Record {n+1}</strong><p style={{whiteSpace:"pre-wrap"}}>{r[i]}</p></li> : null)}</ol></details>)}
      </div>}
    </>}
  </section>;
}
