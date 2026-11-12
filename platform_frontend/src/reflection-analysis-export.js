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

export function reportHtml(title, results, model = "", { assigned, gradeLabels = [] } = {}) {
  const e = escapeHtml;
  const analyzed = results.filter(row => row.analysis);
  const statuses = ["resolved", "unresolved", "unspecified", "no_challenge"];
  const colors = ["#00836a", "#d22e49", "#a86a00", "#407596", "#714bb2", "#bd4678"];
  const topics = new Map();
  const emotions = new Map();
  for (const row of results) {
    const answer = row.answers?.find(({ question }) => /^how do you feel about the course so far\?/i.test(question.trim()));
    const choices = [...new Set((answer?.response || "").split(",").map(value => value.trim()).filter(value => value && value !== "6"))];
    for (const choice of choices) {
      const counts = emotions.get(choice) || [0, 0];
      counts[choices.length === 1 ? 0 : 1]++;
      emotions.set(choice, counts);
    }
  }

  function chartRows(rows, labels, denominator) {
    const max = Math.max(1, ...rows.map(([, counts]) => counts.reduce((sum, count) => sum + count, 0)));
    return rows.map(([name, counts]) => `<div class="chart-row"><strong>${e(name)}</strong>
      <div class="chart-track">${counts.map((count, i) => count ? `<span style="width:${100 * count / max}%;background:${colors[i % colors.length]}"></span>` : "").join("")}</div>
      <small>${counts.map((count, i) => count ? `${e(labels[i])} ${count} (${(100 * count / denominator).toFixed(1)}%)` : "").filter(Boolean).join(" · ") || "0"}</small>
    </div>`).join("");
  }

  function chartViews(title, views) {
    return `<div class="chart-views"><h3>${title}</h3><label>Chart view <select>${views.map(([label], i) =>
      `<option value="${i}">${label}</option>`).join("")}</select></label>
      ${views.map(([, chart], i) => `<div data-chart${i ? " hidden" : ""}>${chart}</div>`).join("")}</div>`;
  }
  for (const { analysis } of analyzed) {
    analysis.primary_labels_selected.forEach((label, index) => {
      const counts = topics.get(label) || [0, 0, 0, 0];
      counts[statuses.indexOf(analysis.resolution_primary_labels[index])]++;
      topics.set(label, counts);
    });
  }

  const grades = gradeLabels.flatMap(label => {
    const match = String(label ?? "").match(/^(.+):\s*(-?\d+(?:\.\d+)?)(%?)$/);
    return match ? [{ name: match[1], value: Number(match[2]), unit: match[3] }] : [];
  });
  const comparableGrades = grades.length && grades.every(
    grade => grade.name === grades[0].name && grade.unit === grades[0].unit,
  );
  const average = comparableGrades
    ? grades.reduce((sum, grade) => sum + grade.value, 0) / grades.length
    : null;
  const profiles = results.map((row, index) => `<details class="profile">
    <summary><strong>Student ${index + 1}</strong>${row.grade == null ? "" : `<span>${e(row.grade)}</span>`}</summary>
    ${row.analysis ? `<p><strong>Urgency</strong> ${e(row.analysis.urgency)}</p>
      <ul>${row.analysis.primary_labels_selected.map((topic, i) =>
        `<li>${e(readable(topic))} · ${e(readable(row.analysis.resolution_primary_labels[i]))}</li>`).join("")}</ul>`
      : `<p>${e(row.error || "Analysis unavailable for this response.")}</p>`}
    <div class="profile-grid">
      <details open><summary>Reflection responses</summary>
        ${row.answers?.length ? `<table><thead><tr><th>Question</th><th>Response</th></tr></thead><tbody>
        ${row.answers.map(({ question, response }) => `<tr><td>${e(question)}</td><td>${e(response)}</td></tr>`).join("")}</tbody></table>`
        : `<blockquote>${e(row.text)}</blockquote>`}</details>
      <div><h3>Grades</h3>${row.gradeBreakdown?.length ? `<table><thead><tr><th>Category</th><th>Current score</th></tr></thead><tbody>
        ${row.gradeBreakdown.map(({ category, score }) => `<tr><td>${e(category)}</td><td>${e(score)}</td></tr>`).join("")}</tbody></table>`
        : `<p>${e(row.grade || "No grade available.")}</p>`}
        ${row.missingAssignments?.length ? `<h3>Missing assignments</h3><ul>${row.missingAssignments.map(name => `<li>${e(name)}</li>`).join("")}</ul>` : ""}
      </div>
    </div>
  </details>`).join("");
  const notes = (field) => analyzed.map(({ analysis }, index) => {
    const studentNumber = results.indexOf(analyzed[index]) + 1;
    return `<article><h3>Student ${studentNumber}</h3><p>${e(analysis[field])}</p></article>`;
  }).join("");
  const panels = [
    ["Class Aggregates", `<h2>Summary for ${e(title)}</h2>
      <dl><div><dt>${assigned == null ? "Students in report" : "Student records in this set"}</dt><dd>${assigned ?? results.length}</dd></div>
      <div><dt>Students with responses</dt><dd>${results.length}</dd></div>
      <div><dt>Responses analyzed</dt><dd>${analyzed.length}</dd></div></dl>
      <h3>Grade data</h3>
      ${average == null ? "<p>No comparable numeric grades available.</p>" : `<p>Average ${e(grades[0].name)} <strong>${average.toFixed(2)}${e(grades[0].unit)}</strong> · ${grades.length} valid grades</p>`}
      <p class="note">This report covers one reflection set. Grade counts use the selected grade column and exclude blank grades.</p>
      ${emotions.size ? chartViews("Emotions reported by students", [
        ["All selections", chartRows([...emotions].map(([label, [single, mixed]]) => [label, [single + mixed]]), ["Selected"], assigned || results.length)],
        ["Single and mixed selections", chartRows([...emotions], ["Single", "Mixed"], assigned || results.length)],
      ]) : "<p>No responses to the course emotion question were imported.</p>"}`],
    ["Student Profiles", `<h2>Student profiles</h2>${profiles || "<p>No student responses.</p>"}`],
    ["Topic Analysis", `<h2>Topic analysis</h2>${topics.size ? chartViews("Topic distribution by resolution status", [
      ["All statuses", chartRows([...topics].map(([label, counts]) => [readable(label), counts]), statuses.map(readable), analyzed.length)],
      ...statuses.map((status, index) => [readable(status), chartRows(
        [...topics].map(([label, counts]) => [readable(label), statuses.map((_, i) => i === index ? counts[i] : 0)]),
        statuses.map(readable), analyzed.length,
      )]),
    ]) + "<p class='note'>Percentages use analyzed reflections. One reflection may mention several topics.</p>"
      : "<p>No analyzed topics available.</p>"}`],
    ["Summarization", `<h2>Reflection summaries</h2>${notes("reflection_summary") || "<p>No generated summaries available.</p>"}`],
    ["Instructor Follow-up", `<h2>Suggested follow-ups</h2>${notes("instructor_suggestions") || "<p>No generated follow-up suggestions available.</p>"}`],
  ];
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${e(title)} · Instructor report</title><style>
    *{box-sizing:border-box}body{margin:0;background:#edf3f8;color:#162b3d;font:16px/1.55 system-ui,sans-serif}main{width:min(1080px,calc(100% - 32px));margin:32px auto}
    header,section{background:white;border:1px solid #d2e2ee;border-radius:16px;padding:clamp(16px,4vw,36px)}header{border-top:5px solid #2278ad}
    h1,h2,h3{line-height:1.25;margin:0 0 14px}header p{margin:8px 0}.note{color:#486175}
    nav{display:flex;flex-wrap:wrap;gap:6px;margin:20px 0 8px}button{font:inherit;font-weight:650;color:#163952;background:#fff;border:1px solid #b7d0e0;border-radius:8px;padding:9px 14px;cursor:pointer}button[aria-pressed=true]{background:#176ba0;color:#fff}
    dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}dl div{background:#edf6fb;padding:16px;border-radius:12px}dd{margin:0;font-size:1.7rem;font-weight:750}
    article,.profile{border-top:1px solid #d2e2ee;padding:14px 0}summary{cursor:pointer}summary span{margin-inline-start:12px;color:#486175}blockquote{white-space:pre-wrap;overflow-wrap:anywhere;border-left:3px solid #2278ad;margin-inline:0;padding-left:16px}
    table{border-collapse:collapse;width:100%;text-align:left}th,td{padding:10px;border-bottom:1px solid #d2e2ee}
    .chart-row{display:grid;gap:4px;margin:14px 0}.chart-track{display:flex;height:16px;background:#edf6fb;border-radius:6px;overflow:hidden}
    .chart-views select{font:inherit;margin-left:8px}.profile-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:24px;margin-top:16px}.profile-grid td{white-space:pre-wrap;overflow-wrap:anywhere}
    @media print{nav{display:none}section[hidden]{display:block}section{margin-bottom:12px}}
  </style></head><body><main><header><h1>${e(title)}</h1><p>Instructor reflection report</p><p class="note">Student names and IDs are omitted.${model ? ` Analysis model: ${e(model)}.` : ""}</p></header>
    <nav aria-label="Report sections">${panels.map(([label], i) => `<button type="button" aria-controls="section-${i}" aria-pressed="${i === 0}">${label}</button>`).join("")}</nav>
    ${panels.map(([, content], i) => `<section id="section-${i}"${i ? " hidden" : ""}>${content}</section>`).join("")}
  </main><script>
    for (const view of document.querySelectorAll(".chart-views")) {
      const picker = view.querySelector("select");
      picker.addEventListener("change", () => {
        view.querySelectorAll("[data-chart]").forEach((chart, i) => { chart.hidden = i !== Number(picker.value); });
      });
    }
    const buttons = document.querySelectorAll("nav button");
    for (const button of buttons) button.addEventListener("click", () => {
      for (const tab of buttons) {
        tab.setAttribute("aria-pressed", String(tab === button));
        document.getElementById(tab.getAttribute("aria-controls")).hidden = tab !== button;
      }
    });
  </script></body></html>`;
}

export function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
