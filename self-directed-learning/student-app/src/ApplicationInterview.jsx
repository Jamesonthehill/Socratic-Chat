import {useEffect, useRef, useState} from 'react';
import {api} from './api';

export default function ApplicationInterview({assignmentId, initial}) {
  const [interview, setInterview] = useState(initial);
  const [answer, setAnswer] = useState(initial?.retry_response || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const started = useRef(false);
  const pending = useRef(null);
  const inFlight = useRef(false);
  async function send(action) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError('');
    const body = pending.current?.action === action ? pending.current : {
      action, turn_id: crypto.randomUUID(), question_id: interview?.question?.id || null,
      content: action === 'answer' ? answer.trim() : '',
    };
    pending.current = body;
    try {
      const result = await api(`/student/assignments/${assignmentId}/application-interview`, {
        method:'POST', body:JSON.stringify(body),
      });
      setInterview(result);
      pending.current = null;
      if (!result.error) setAnswer('');
    } catch (e) {
      setError(e.message || 'Your interview could not be saved. Retry the same action.');
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!started.current) {
      started.current = true;
      if (!initial) send('start');
    }
  }, []);
  const ended = ['complete','stopped'].includes(interview?.status);
  return <section className="diagnostic-card" aria-label="Application understanding interview">
    <h3>Application understanding interview</h3>
    <p>Let’s explore the reasoning behind your response. This optional conversation does not change your score. Answer the final research-use question below to view your completion card.</p>
    {interview?.turns?.map((turn,index)=><div key={index}>
      <InterviewBubble role="assistant" text={turn.question}/>
      <InterviewBubble role="student" text={turn.response}/>
      <InterviewBubble role="assistant" text={turn.feedback}/>
    </div>)}
    {!ended && interview?.question && <InterviewBubble role="assistant" text={interview.question.text}/>}
    {busy && pending.current?.action === 'answer' && <InterviewBubble role="student" text={pending.current.content}/>}
    {busy && <p role="status">Thinking…</p>}
    {(error || interview?.error) && <p role="alert">{error || interview.error}</p>}
    {!ended && <form onSubmit={e=>{e.preventDefault(); if(interview?.status === 'active' && answer.trim()) send('answer');}}>
      {interview?.status === 'active' && <>
        <label htmlFor="interview-answer">Explain your reasoning</label>
        <textarea id="interview-answer" value={answer} maxLength={8000} disabled={busy || Boolean(pending.current)}
          onChange={e=>setAnswer(e.target.value)} />
      </>}
      <div className="learning-choices">
        {interview?.status === 'active'
          ? <button type="submit" className="primary" disabled={busy || !answer.trim()}>Send interview response</button>
          : !busy && <button type="button" className="primary" onClick={()=>send('start')}>Retry interview question</button>}
        <button type="button" className="secondary" disabled={busy} onClick={()=>send('stop')}>Stop interview and keep my result</button>
      </div>
    </form>}
    {ended && <p role="status">{interview.status === 'stopped' ? 'Interview stopped. Your application result is unchanged.' : interview.outcome === 'evidence_demonstrated' ? 'You provided evidence for the concept we explored. Your application result is unchanged.' : 'Interview finished. Some reasoning needs further review; your application result is unchanged.'}</p>}
  </section>;
}

function InterviewBubble({role,text}) {
  return <div className={`sdl-message-group ${role}`}>
    <span className="sdl-speaker">{role === 'student' ? 'You' : 'Tutor'}</span>
    <article className={`message sdl-bubble ${role}`}><p style={{whiteSpace:'pre-wrap'}}>{text}</p></article>
  </div>;
}
