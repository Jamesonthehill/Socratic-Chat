import {useState} from "react";
import {Notice} from "./ui";

const groups=[["not_started","New"],["in_progress","In progress"],["completed","Completed"],["","All assignments"]];
export default function StudentAssignmentBrowser({items,error,reload,renderItems}) {
  const [view,setView]=useState(()=>localStorage.getItem("platform_student_assignment_view")==="list" ? "list" : "cards");
  return <>
    <div className="page-heading"><div><p className="context">Your learning workspace</p><h1>Your assignments</h1></div></div>
    <div className="student-view-toolbar">
      <div className="assignment-view-switch" role="group" aria-label="Assignment display">
        {[["list","List view"],["cards","Grid view"]].map(([key,title])=><button type="button" key={key} aria-label={title} title={title} aria-pressed={view===key} className={view===key ? "active" : ""} onClick={()=>{setView(key);localStorage.setItem("platform_student_assignment_view",key);}}>{key==="cards" ? <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 3h5v5H3zM12 3h5v5h-5zM3 12h5v5H3zM12 12h5v5h-5z"/></svg> : <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 4h14M3 10h14M3 16h14"/></svg>}</button>)}
      </div>
    </div>
    <Notice error={error}/>
    {!items ? !error && <p role="status">Loading assignments…</p> : groups.map(([key,title])=>{
      const rows=items.filter(item=>!key || (item.progress || "not_started")===key);
      return <section className="student-assignment-group" key={key} aria-labelledby={`assignment-group-${key || "all"}`}>
        <h2 id={`assignment-group-${key || "all"}`}>{title}<span className="student-assignment-count">{rows.length}</span></h2>
        {rows.length ? renderItems(rows,view) : <p className="student-group-empty">{key==="not_started" ? "No new assignments." : key==="in_progress" ? "No assignments in progress." : key==="completed" ? "Your completed assignments will appear here." : "Your instructor’s published activities will appear here when assigned to you."}</p>}
      </section>;
    })}
    {error && <button className="secondary compact" onClick={reload}>Try again</button>}
  </>;
}
