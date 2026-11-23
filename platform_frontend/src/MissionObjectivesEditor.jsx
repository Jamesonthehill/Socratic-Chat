import { useId } from "react";

export default function MissionObjectivesEditor({ objectives = [], onChange, disabled = false }) {
  const id = useId();
  return <div className="mission-objectives-editor">
    <div className="mission-objectives-editor-heading">
      <strong id={id}>Mission objectives</strong>
      <span>{objectives.length} / 6</span>
    </div>
    <p id={`${id}-help`} className="help">Use 2–4 clear objectives. Each row describes one thing the student should explain or apply.</p>
    <table aria-labelledby={id} aria-describedby={`${id}-help`}>
      <thead><tr><th scope="col">#</th><th scope="col">What the student should demonstrate</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
      <tbody>
        {objectives.map((objective, index) => <tr key={index}>
          <th scope="row">{String(index + 1).padStart(2, "0")}</th>
          <td><textarea aria-label={`Objective ${index + 1}`} value={objective} rows={2} maxLength={300}
            disabled={disabled} placeholder="Explain a choice, connection, or consequence in the scenario."
            onChange={(event) => onChange(objectives.map((item, position) => position === index ? event.target.value : item))} /></td>
          <td><button type="button" className="quiet compact" disabled={disabled}
            aria-label={`Remove objective ${index + 1}`}
            onClick={() => onChange(objectives.filter((_, position) => position !== index))}>Remove</button></td>
        </tr>)}
        {!objectives.length && <tr><td colSpan={3} className="help">No objectives yet. Add one to define what students should demonstrate.</td></tr>}
      </tbody>
    </table>
    <button type="button" className="quiet compact" disabled={disabled || objectives.length >= 6}
      onClick={() => onChange([...objectives, ""])}>+ Add objective</button>
  </div>;
}
