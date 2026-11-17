import { useState } from "react";
import { session } from "./api";

export default function AiducateProfile() {
  const account = session() || {};
  const storageKey = "aiducate-profile:" + (account.user_id || account.username);
  const [fields, setFields] = useState(() => {
    const initial = { name: account.display_name || "", email: account.email || "", institution: "", department: "" };
    try { return { ...initial, ...JSON.parse(localStorage.getItem(storageKey)) }; }
    catch { return initial; }
  });
  const [message, setMessage] = useState("");
  const [demoKey, setDemoKey] = useState("");
  const [visible, setVisible] = useState(false);
  const [checked, setChecked] = useState(false);
  return <div><div className="aid-heading"><div><small>Account</small><h1>Instructor Profile</h1><p>Manage your AIDucate profile and preview connection settings.</p></div></div>
    <div className="aid-profile-grid"><form className="aid-section" onSubmit={event => {
      event.preventDefault();
      try { localStorage.setItem(storageKey, JSON.stringify(fields)); setMessage("Profile saved in this browser."); }
      catch { setMessage("Browser storage is unavailable."); }
    }}><h2>Account information</h2>
      {Object.entries({ name: "Full name", email: "Email address", institution: "Institution", department: "Department" }).map(([key, label]) =>
        <label key={key}>{label}<input type={key === "email" ? "email" : "text"} value={fields[key]} onChange={event => { setFields({ ...fields, [key]: event.target.value }); setMessage(""); }}/></label>)}
      <label>Role<input readOnly value="Instructor"/></label>
      <button>Save profile</button><p role="status">{message || "Profile changes apply in this browser."}</p>
    </form><section className="aid-section"><h2>OpenAI API Key</h2><p>Preview the connection controls with a sample key.</p>
      <p role="status">{checked ? "Demo check complete · No live connection" : "Demo · Disconnected"}</p>
      <label>Sample key<input type={visible ? "text" : "password"} value={demoKey} readOnly placeholder="Load a sample key"/></label>
      <div className="editor-actions"><button onClick={() => { setDemoKey("sk-demo-instructor"); setChecked(false); }}>Load sample</button>
      <button disabled={!demoKey} onClick={() => setVisible(!visible)}>{visible ? "Hide" : "Show"}</button>
      <button disabled={!demoKey} onClick={() => setChecked(true)}>Check connection (demo)</button>
      <button disabled={!demoKey} onClick={() => { setDemoKey(""); setChecked(false); setVisible(false); }}>Clear</button></div>
    </section></div></div>;
}
