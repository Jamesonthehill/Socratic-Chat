import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { GenerationStatus, Notice } from "./ui";
import "./step-surveys.css";

const blankQuestion = (kind = "text") => ({ id: crypto.randomUUID(), kind, prompt: "" });
const emptyDraft = title => ({ title: `${title} reflection`.slice(0,150), questions: [
  { ...blankQuestion("confidence"), prompt: `How confident do you feel about ${title}?`.slice(0,500) },
  { ...blankQuestion(), prompt: "Which part of this step was confusing?" },
  { ...blankQuestion(), prompt: "Explain one thing you learned from this step." },
] });

export function StepSurveyEditor({ assignment }) {
  const [steps, setSteps] = useState([]), [index, setIndex] = useState(0), [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [generating, setGenerating] = useState(false);
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    api(`/platform/assignments/${assignment.id}/step-surveys`).then(data => {
      if (!active) return;
      const list = data.steps || []; setSteps(list); setIndex(0);
      setDraft(list[0] ? list[0].draft || emptyDraft(list[0].title) : null);
    }).catch(e => active && setError(e.message)).finally(() => active && setLoading(false));
    return () => {active = false;};
  }, [assignment.id]);
  function select(next) {
    setIndex(next); setDraft(steps[next].draft || emptyDraft(steps[next].title)); setError("");setNotice("");
  }
  function edit(patch) {
    const next = {...draft,...patch};
    setDraft(next);
    setSteps(rows => rows.map((row,i) => i === index ? {...row,draft:next} : row));
    setNotice("");
  }
  async function generate() {
    setError("");setNotice("");setBusy(true);setGenerating(true);
    try { edit(await api(`/platform/assignments/${assignment.id}/step-surveys/${index}/generate`,{method:"POST",body:{}})); }
    catch(e){setError(e.message);} finally{setBusy(false);setGenerating(false);}
  }
  async function save(publish) {
    setError("");setNotice("");setBusy(true);
    try {
      const record = await api(`/platform/assignments/${assignment.id}/step-surveys/${index}`, {method:"PUT",body:{title:draft.title,questions:draft.questions,publish}});
      setSteps(rows => rows.map((row,i) => i === index ? {...row,...record} : row));
      setNotice(publish ? "Survey published. Students can answer it from this step." : "Survey draft saved. Students still see the last published version.");
    } catch(e){setError(e.message);} finally{setBusy(false);}
  }
  const valid = draft?.title.trim().length >= 3 && draft.questions.length > 0 && draft.questions.every(q => q.prompt.trim().length >= 5);
  return <section className="panel step-survey-editor" aria-label="Step survey settings">
    <div className="survey-heading"><div><h2>Step surveys</h2><p>Collect ungraded confidence, confusion, and learning reflections. Surveys do not unlock or block learning steps.</p></div><span className="survey-tag">Ungraded</span></div>
    <Notice error={error}/>{notice && <p role="status" className="survey-success">{notice}</p>}
    {loading ? <p role="status">Loading surveys…</p> : !steps.length ? <p>Add learning steps or Reflection sub-topics first.</p> : <>
      <label>Survey learning step<select disabled={busy} value={index} onChange={e => select(Number(e.target.value))}>{steps.map((step,i) => <option value={i} key={i}>{i+1}. {step.title}</option>)}</select></label>
      <p className="help"><strong>Learning goal:</strong> {steps[index].goal}</p>
      <div className="survey-toolbar"><button type="button" disabled={busy} onClick={generate}>Generate step survey</button><span>{steps[index].published ? "A published version is available to students." : "Not published yet."}</span></div>
      <label>Survey title<input maxLength={150} value={draft.title} disabled={busy} onChange={e => edit({title:e.target.value})}/></label>
      {draft.questions.map((question,i) => <div className="survey-edit-question" key={question.id}>
        <label>Question {i+1}<textarea rows={2} maxLength={500} value={question.prompt} disabled={busy} onChange={e => edit({questions:draft.questions.map((q,n)=>n===i?{...q,prompt:e.target.value}:q)})}/></label>
        <div className="survey-toolbar"><label>Response type<select disabled={busy} value={question.kind} onChange={e => edit({questions:draft.questions.map((q,n)=>n===i?{...q,kind:e.target.value}:q)})}><option value="confidence">Confidence · 1–5</option><option value="text">Written reflection</option></select></label><button className="survey-remove" type="button" disabled={busy || draft.questions.length===1} onClick={()=>edit({questions:draft.questions.filter((_,n)=>n!==i)})}>Remove question</button></div>
      </div>)}
      <div className="survey-toolbar"><button className="quiet" type="button" disabled={busy || draft.questions.length>=6} onClick={()=>edit({questions:[...draft.questions,blankQuestion()]})}>＋ Add question</button><button type="button" disabled={busy || !valid} onClick={()=>save(false)}>Save survey draft</button><button className="survey-publish" type="button" disabled={busy || !valid} onClick={()=>save(true)}>Publish survey</button></div>
      <p className="help">Review AI-generated questions before publishing. New publications get a new version; earlier student responses remain attached to the questions they answered.</p>
    </>}
    {generating && <GenerationStatus fullScreen atomLogo title="Step survey" message="Drafting questions from this learning goal and its course material"/>}
  </section>;
}

export function StudentStepSurvey({ assignmentId, stepIndex, reflection = false }) {
  const [open,setOpen] = useState(false), [steps,setSteps] = useState([]), [selected,setSelected] = useState(stepIndex || 0);
  const [answers,setAnswers] = useState({}), [loading,setLoading] = useState(false), [busy,setBusy] = useState(false), [error,setError] = useState("");
  const close = useRef(null), trigger = useRef(null);
  async function show() {
    setOpen(true);setLoading(true);setError("");setAnswers({});
    try {
      const data = await api(`/platform/assignments/${assignmentId}/step-surveys`);
      setSteps(data.steps);setSelected(data.steps.find(step=>step.index===stepIndex)?.index ?? data.steps[0]?.index ?? 0);
    } catch(e){setError(e.message);} finally{setLoading(false);}
  }
  function dismiss(){setOpen(false);trigger.current?.focus();}
  useEffect(()=>{if(open)close.current?.focus();},[open]);
  const step = steps.find(step=>step.index===selected), survey=step?.published;
  async function submit(event) {
    event.preventDefault();setBusy(true);setError("");
    try {
      await api(`/platform/assignments/${assignmentId}/step-surveys/${selected}/submit`,{method:"POST",body:{version:survey.version,answers}});
      setSteps(rows=>rows.map(row=>row.index===selected?{...row,submitted:true}:row));
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  const complete = survey?.questions.every(q => q.kind === "confidence" ? Number.isInteger(answers[q.id]) : typeof answers[q.id]==="string" && answers[q.id].trim());
  return <>
    <button ref={trigger} type="button" className="step-survey-trigger compact" onClick={show}>Quiz / Survey</button>
    {open && <div className="survey-overlay"><section className="survey-modal" role="dialog" aria-modal="true" aria-labelledby="student-survey-title" onKeyDown={event=>{
      if(event.key==="Escape" && !busy)dismiss();
      if(event.key==="Tab"){
        const nodes=[...event.currentTarget.querySelectorAll('button:not(:disabled),select,textarea,input')];
        if(event.shiftKey && document.activeElement===nodes[0]){event.preventDefault();nodes.at(-1)?.focus();}
        else if(!event.shiftKey && document.activeElement===nodes.at(-1)){event.preventDefault();nodes[0]?.focus();}
      }
    }}>
      <div className="survey-heading"><div><span className="survey-tag">Ungraded reflection</span><h2 id="student-survey-title">{survey?.title || "Step survey"}</h2></div><button ref={close} type="button" className="survey-remove" disabled={busy} onClick={dismiss}>Close</button></div>
      <p>Your answers help your instructor understand what was clear or confusing. This survey does not affect your grade or learning progress.</p><Notice error={error}/>
      {loading ? <p role="status">Opening your survey…</p> : !steps.length ? <p>Your instructor has not published a survey for {reflection ? "this assignment" : "the steps you have reached"} yet.</p> : <>
        <label>Learning step<select disabled={busy} value={selected} onChange={e=>{setSelected(Number(e.target.value));setAnswers({});setError("");}}>{steps.map(row=><option key={row.index} value={row.index}>{row.index+1}. {row.title}</option>)}</select></label>
        {step?.submitted ? <p className="survey-success" role="status">✓ Survey submitted. Thank you for sharing your reflection.</p> : <form onSubmit={submit}>
          {survey?.questions.map((question,i)=><fieldset disabled={busy} key={question.id}><legend>{i+1}. {question.prompt}</legend>{question.kind==="confidence" ? <div className="survey-confidence" role="radiogroup" aria-label={question.prompt}>{[1,2,3,4,5].map(value=><label key={value}><input type="radio" name={question.id} value={value} required checked={answers[question.id]===value} onChange={()=>setAnswers(current=>({...current,[question.id]:value}))}/><span>{value}</span></label>)}<small>1 · Not confident &nbsp; 5 · Very confident</small></div> : <textarea rows={3} maxLength={2000} required value={answers[question.id] || ""} onChange={e=>setAnswers(current=>({...current,[question.id]:e.target.value}))}/>}</fieldset>)}
          <button type="submit" disabled={busy || !complete}>{busy?"Submitting…":"Submit survey"}</button>
        </form>}
      </>}
    </section></div>}
  </>;
}
