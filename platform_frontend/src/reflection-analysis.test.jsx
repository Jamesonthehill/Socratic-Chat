import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "./main";
import ReflectionAnalysis from "./ReflectionAnalysis";
import { api, SESSION_KEY } from "./api";
import { csvExport, reportHtml } from "./reflection-analysis-export";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal()),
  api: vi.fn(),
}));
const record = {
  student_id: "001",
  name: "Alex",
  text: "I cannot understand loops",
  grade: 80,
};
const annotation = {
  primary_labels_selected: ["python_and_coding"],
  resolution_primary_labels: ["unresolved"],
  urgency: "high",
  reflection_summary: "Alex needs help with loops.",
  instructor_suggestions: "Offer a walkthrough.",
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem(SESSION_KEY, JSON.stringify({ access_token: "test" }));
  api.mockImplementation(async (path) => {
    if (path === "/platform/reflection-analysis/config")
      return {
        labels: { python_and_coding: "Programming challenges" },
        model_configured: true,
      };
    if (path === "/platform/assignments")
      return [
        {
          id: "assignment",
          title: "Week 1",
          course_code: "CS101",
          tool: "reflections",
          can_manage: true,
        },
      ];
    if (path.endsWith("/reflection-analysis"))
      return {
        assignment: { title: "Week 1" },
        summary: { assigned: 2 },
        students: [
          { student_id: "001", name: "Alex", responses: [record.text] },
        ],
      };
    if (path.endsWith("/analyze"))
      return {
        results: [{ ...record, index: 0, analysis: annotation }],
        summary: { failed: 0 },
        model: "test-model",
      };
    throw Error(`Unexpected request: ${path}`);
  });
});

test("professor loads assignment, analyzes responses, and filters student summaries", async () => {
  const user = userEvent.setup();
  render(<ReflectionAnalysis />);
  await screen.findByRole("option", { name: /CS101 — Week 1/ });
  await user.selectOptions(
    screen.getByLabelText("CourseLab assignment"),
    "assignment",
  );
  await user.click(screen.getByRole("button", { name: "Load assignment" }));
  await screen.findByText("1 reflections loaded. 0 analyzed.");
  await user.click(
    screen.getByRole("button", { name: "Continue to analysis" }),
  );
  await user.click(screen.getByRole("button", { name: "Run topic analysis" }));
  await screen.findByText(
    "1 analyzed · 1 with unresolved challenges · 1 high urgency",
  );
  await user.click(
    screen.getByRole("button", { name: "Explore student summaries" }),
  );
  expect(screen.getByText("Alex")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Urgency"), "low");
  expect(
    screen.getByText("No reflections match these filters."),
  ).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Urgency"), "high");
  await user.click(screen.getByText("Alex"));
  expect(screen.getByText("Offer a walkthrough.")).toBeInTheDocument();
  expect(screen.getByText(record.text)).toBeInTheDocument();
});

test("CSV import requires explicit response selection and displays cleaning warnings", async () => {
  const user = userEvent.setup();
  const original = api.getMockImplementation();
  api.mockImplementation(async (path, options) => {
    if (path.endsWith("/import"))
      return options.body.id_column
        ? {
            records: [record],
            warnings: ["Row 3: skipped an empty student ID or reflection."],
          }
        : {
            columns: ["Student_ID", "Name", "Q1"],
            preview: [{ Student_ID: "001", Name: "Alex", Q1: record.text }],
            row_count: 2,
          };
    return original(path, options);
  });
  render(<ReflectionAnalysis />);
  const file = new File(
    ["Student_ID,Name,Q1\n001,Alex,Loops"],
    "reflections.csv",
    { type: "text/csv" },
  );
  file.text = async () => "Student_ID,Name,Q1\n001,Alex,Loops";
  fireEvent.change(screen.getByLabelText("Reflection CSV or TSV"), {
    target: { files: [file] },
  });
  await screen.findByText("Map columns · reflections.csv");
  expect(
    screen.getByRole("button", { name: "Import reflections" }),
  ).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: "Q1" }));
  await user.click(screen.getByRole("button", { name: "Import reflections" }));
  await screen.findByText("1 reflections loaded. 0 analyzed.");
  await user.click(screen.getByRole("tab", { name: "Data cleaning" }));
  expect(
    screen.getByText("Row 3: skipped an empty student ID or reflection."),
  ).toBeInTheDocument();
  expect(screen.getByText("001")).toBeInTheDocument();
});

test("new navigation tab is adjacent to professor dashboard and hidden from students", async () => {
  const original = api.getMockImplementation();
  api.mockImplementation(async (path, options) =>
    path === "/auth/me"
      ? {
          user: {
            authority_level: 1,
            onboarding_complete: true,
            username: "Professor",
          },
        }
      : original(path, options),
  );
  const professor = render(
    <MemoryRouter initialEntries={["/professor/reflection-analysis"]}>
      <App />
    </MemoryRouter>,
  );
  const navigation = await screen.findByRole("navigation", {
    name: "Main navigation",
  });
  expect(
    within(navigation)
      .getAllByRole("link")
      .map((link) => link.textContent),
  ).toEqual(["Professor dashboard", "Reflection analysis", "AIducate"]);
  expect(
    screen.getByRole("link", { name: "Reflection analysis" }),
  ).toHaveAttribute("aria-current", "page");
  professor.unmount();
  api.mockImplementation(async (path) => {
    if (path === "/auth/me")
      return {
        user: {
          authority_level: 2,
          onboarding_complete: true,
          username: "Student",
        },
      };
    if (path === "/courses") return { courses: [] };
    if (path === "/platform/assignments") return [];
    return {};
  });
  render(
    <MemoryRouter initialEntries={["/professor/reflection-analysis"]}>
      <App />
    </MemoryRouter>,
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("heading", { name: "Reflection analysis" }),
    ).not.toBeInTheDocument(),
  );
  expect(
    await screen.findByRole("navigation", { name: "Main navigation" }),
  ).not.toHaveTextContent("Reflection analysis");
});

test("exports escape untrusted HTML and spreadsheet formulas", () => {
  const html = reportHtml("<script>alert(1)</script>", [
    {
      ...record,
      text: '<img src=x onerror="alert(1)">',
      name: '<svg onload="alert(1)">',
      analysis: annotation,
    },
  ]);
  expect(html).not.toContain("<script>");
  expect(html).not.toContain("<img");
  expect(html).toContain("&lt;img");
  expect(csvExport([["=HYPERLINK(1)", 'a"b', "safe"]])).toBe(
    '"\'=HYPERLINK(1)","a""b","safe"',
  );
});

test("loaded reflections survive navigating to the dashboard and back", async () => {
  const user = userEvent.setup();
  const original = api.getMockImplementation();
  api.mockImplementation(async (path, options) => {
    if (path === "/auth/me")
      return {
        user: {
          authority_level: 1,
          onboarding_complete: true,
          username: "Professor",
        },
      };
    if (path === "/courses") return { courses: [] };
    return original(path, options);
  });
  render(
    <MemoryRouter initialEntries={["/professor/reflection-analysis"]}>
      <App />
    </MemoryRouter>,
  );
  await screen.findByRole("option", { name: /CS101 — Week 1/ });
  await user.selectOptions(
    screen.getByLabelText("CourseLab assignment"),
    "assignment",
  );
  await user.click(screen.getByRole("button", { name: "Load assignment" }));
  await screen.findByText("1 reflections loaded. 0 analyzed.");
  await user.click(screen.getByRole("link", { name: "Professor dashboard" }));
  expect(
    screen.queryByRole("heading", { name: "Reflection analysis" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Reflection analysis" }));
  expect(screen.getByText("1 reflections loaded. 0 analyzed.")).toBeVisible();
});
