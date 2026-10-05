import { useEffect, useState } from "react";
import { api } from "./api";
import { Notice } from "./ui";

export default function CanvasLinkedFiles({ assignmentId, onImported }) {
  const [files, setFiles] = useState(null);
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    const result = await api(`/platform/assignments/${assignmentId}/canvas-files`);
    setFiles(result.files);
  }

  useEffect(() => {
    let active = true;
    api(`/platform/assignments/${assignmentId}/canvas-files`)
      .then((result) => active && setFiles(result.files))
      .catch((caught) => active && setError(caught.message));
    return () => { active = false; };
  }, [assignmentId]);

  async function importSelected() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api(`/platform/assignments/${assignmentId}/canvas-files`, {
        method: "POST",
        body: { file_ids: selected },
      });
      setSelected([]);
      await load();
      if (result.imported.length) onImported?.(result.imported);
      const importedText = `${result.imported.length} file(s) added to course materials.`;
      const skippedText = result.skipped.length
        ? ` ${result.skipped.map((file) => `${file.filename}: ${file.reason}`).join(" ")}`
        : "";
      setNotice(importedText + skippedText);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel canvas-linked-files">
      <h2>Canvas files in this assignment</h2>
      <p className="help">
        Nothing is added automatically. Choose files to copy into this course's
        searchable materials. Approved students in the course may then use those
        materials in the chatbot. Check Canvas access restrictions before importing.
        Other links remain in the assignment instructions.
      </p>
      <Notice error={error}>{notice}</Notice>
      {files === null && !error && <p>Checking linked Canvas files…</p>}
      {files?.length === 0 && <p>No Canvas-hosted files were linked in these instructions.</p>}
      {files?.map((file) => {
        const available = file.importable && !file.imported;
        return (
          <label className="check" key={file.id}>
            <input
              type="checkbox"
              checked={selected.includes(file.id)}
              disabled={busy || !available}
              onChange={(event) => setSelected((current) => event.target.checked
                ? [...current, file.id]
                : current.filter((id) => id !== file.id))}
            />
            <span>
              {file.filename}
              <small>{file.imported ? "Already in course materials" : file.reason || `${Math.ceil(file.size / 1024)} KB`}</small>
            </span>
          </label>
        );
      })}
      {files?.some((file) => file.importable && !file.imported) && (
        <button type="button" className="secondary" disabled={busy || !selected.length} onClick={importSelected}>
          {busy ? "Adding selected files…" : "Add selected files to course materials"}
        </button>
      )}
    </section>
  );
}
