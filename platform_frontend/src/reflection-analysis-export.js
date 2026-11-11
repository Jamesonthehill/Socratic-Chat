export const readable = (value) => value.replaceAll("_", " ");
const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );

export function csvExport(rows) {
  const cell = (value) => {
    const text = String(value ?? "");
    // Spreadsheet applications must treat uploaded responses as text.
    return `"${(/^[\s]*[=+@-]/.test(text) ? "'" : "") + text.replaceAll('"', '""')}"`;
  };
  return rows.map((row) => row.map(cell).join(",")).join("\r\n");
}

export function resultCsv(results) {
  return csvExport([
    [
      "Student_ID",
      "Name",
      "Reflection",
      "Grade",
      "Topic",
      "Resolution",
      "Urgency",
      "Summary",
      "Instructor suggestions",
      "Error",
    ],
    ...results.flatMap((row) =>
      row.analysis
        ? row.analysis.primary_labels_selected.map((topic, index) => [
            row.student_id,
            row.name,
            row.text,
            row.grade,
            topic,
            row.analysis.resolution_primary_labels[index],
            row.analysis.urgency,
            row.analysis.reflection_summary,
            row.analysis.instructor_suggestions,
            "",
          ])
        : [
            [
              row.student_id,
              row.name,
              row.text,
              row.grade,
              "",
              "",
              "",
              "",
              "",
              row.error,
            ],
          ],
    ),
  ]);
}

export function reportHtml(title, results, model = "", { responseReport = false } = {}) {
  const e = escapeHtml;
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${e(title)}</title><style>body{font:16px/1.6 system-ui;max-width:900px;margin:40px auto;padding:0 24px;color:#192338}article{border-top:1px solid #ccd3de;padding:20px 0}h1,h2{line-height:1.2}blockquote{white-space:pre-wrap;border-left:3px solid #677ce0;padding-left:18px}small{color:#536076}@media print{article{break-inside:avoid}}</style><h1>${e(title)}</h1><p>Reflection analysis · ${e(new Date().toLocaleString())}</p><p>${responseReport ? "Instructor report with original responses." : "AI-generated annotations for instructor review."} ${results.length} reflection(s).${model ? ` Model: ${e(model)}.` : ""}</p>${results.map((row) => `<article><h2>${e(row.name || row.student_id)}</h2><small>${e(row.student_id)}${row.grade == null ? "" : ` · Grade: ${e(row.grade)}${responseReport ? "" : "%"}`}</small>${row.analysis ? `<p>Urgency: ${e(row.analysis.urgency)}</p><ul>${row.analysis.primary_labels_selected.map((topic, i) => `<li>${e(readable(topic))}: ${e(row.analysis.resolution_primary_labels[i])}</li>`).join("")}</ul><h3>Student summary</h3><p>${e(row.analysis.reflection_summary)}</p><h3>Instructor suggestions</h3><p>${e(row.analysis.instructor_suggestions)}</p>` : `<p>${e(row.error || (responseReport ? "" : "Not analyzed"))}</p>`}<details><summary>Original reflection</summary><blockquote>${e(row.text)}</blockquote></details></article>`).join("")}</html>`;
}

export function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
