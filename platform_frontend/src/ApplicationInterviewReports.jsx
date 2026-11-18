import {useState} from 'react';
import {api} from './api';

export default function ApplicationInterviewReports({assignmentId}) {
  const [reports,setReports] = useState(null);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  async function load() {
    setBusy(true); setError(''); setReports(null);
    try { setReports(await api(`/platform/assignments/${assignmentId}/application-interviews`)); }
    catch(e) {setError(e.message);}
    finally {setBusy(false);}
  }
  return <section className="panel" aria-label="Application interview evidence">
    <h2>Application understanding interviews</h2>
    <p>Formative AI observations for instructor review. These results are separate from assignment grades and are not published to Canvas.</p>
    <button disabled={busy} onClick={load}>{busy ? 'Loading interviews…' : 'Load interview evidence'}</button>
    {error && <p role="alert">{error}</p>}
    {reports?.length === 0 && <p>No assigned students.</p>}
    {reports?.map(row=><details key={row.student_id}><summary>{row.display_name} — {row.interview?.status || 'Not started'}</summary>
      {row.interview && <>
        <p>Started: {row.interview.started_at} · Ended: {row.interview.ended_at || 'In progress'}</p>
        <p>Observation: {row.interview.outcome}. No grade publication.</p>
        <h3>Instructor criterion</h3><p>{row.interview.criterion.description}</p>
        <h3>Evidence targets</h3><ul>{row.interview.targets.map(t=><li key={t.id}>{t.id}: {t.description}</li>)}</ul>
        {row.interview.answers.map(a=><article key={a.turn_id}>
          <h3>{row.interview.questions.find(q=>q.id === a.question_id)?.text}</h3>
          <p style={{whiteSpace:'pre-wrap'}}>{a.response}</p>
          <p>Received: {a.received_at} · Assessed: {a.assessed_at}</p>
          <p>{a.assessment.feedback}</p>
          <ul>{a.assessment.evidence.map(e=><li key={e.target_id}>{e.target_id}: {e.status} — {e.feedback}{e.quote && <blockquote>{e.quote}</blockquote>}</li>)}</ul>
        </article>)}
        {row.interview.failures.length > 0 && <p>{row.interview.failures.length} request(s) could not be assessed; no credit decision was made for those requests.</p>}
      </>}
    </details>)}
  </section>;
}
