import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import CreateActivity from "./CreateActivity";
import { resetCourseContext } from "./courseContext";
import { api } from "./api";
vi.mock("./api", async (original) => ({ ...(await original()), api: vi.fn() }));
const course = {
  course_id: "course-1",
  course_code: "SE101",
  title: "Software Engineering",
  membership_role: "instructor",
};
beforeEach(() => {
  resetCourseContext();
  api.mockReset();
  api.mockImplementation(async (path, options) => {
    if (path.startsWith("/platform/context")) return course;
    if (path === "/platform/courses/course-1/documents")
      return {
        files: [
          {
            file_id: "f1",
            document_id: "d1",
            filename: "Requirements.pdf",
            file_size: 2048,
          },
        ],
      };
    if (path === "/courses/course-1/documents")
      return {
        files: [
          {
            file_id: "f1",
            document_id: "d1",
            filename: "Requirements.pdf",
            file_size: 2048,
          },
        ],
      };
    if (path === "/courses/course-1/learning-objectives")
      return { objectives: [] };
    if (path === "/platform/assignments/a1/prepare-sdl")
      return { learning_plan: { title: "Prepared lesson", objectives: [] } };
    if (path === "/platform/assignments/a1/keywords/confirm")
      return {
        ready: true,
        course_id: "course-1",
        keywords: ["design"],
        document_ids: ["d1"],
        passage_count: 3,
      };
    if (path === "/platform/assignments")
      return { ...options.body, id: "a1", status: "draft" };
    throw Error(path);
  });
});
async function open() {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <CreateActivity />
    </MemoryRouter>,
  );
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      expect.stringContaining("/platform/context"),
    ),
  );
  expect(
    screen.getByRole("heading", { name: "Assignment Configuration" }),
  ).toBeInTheDocument();
  await user.type(
    await screen.findByLabelText("Assignment title"),
    "Compare design choices",
  );
  return user;
}
test("five choices replace Student Agent; settings follow Next and review invalidates after edits", async () => {
  const user = await open();
  for (const name of [
    "Socratic Chat",
    "Reflections",
    "Self Directed Learning",
    "Debate",
    "AIducate",
  ])
    expect(
      screen.getByRole("button", { name: new RegExp(name) }),
    ).toBeInTheDocument();
  expect(screen.queryByText("Student Agent Bot")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  expect(
    screen.getByRole("heading", { name: "Socratic Chat settings" }),
  ).toBeInTheDocument();
  expect(
    screen.getByLabelText("Opening question or prompt"),
  ).toBeInTheDocument();
  expect(
    screen.getByLabelText("Messages required before completion"),
  ).toHaveValue(1);
  expect(
    await screen.findByRole("region", { name: "Optional keywords" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Course documents" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Suggest keywords" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Review activity" }));
  expect(
    screen.getByRole("button", { name: "Publish activity" }),
  ).toBeEnabled();
  await user.type(screen.getByLabelText("Description"), "Updated instructions");
  expect(
    screen.queryByRole("heading", { name: "Review and publish" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("combobox", { name: "Course" }),
  ).not.toBeInTheDocument();
});
test("selected materials and description persist when a new chat is saved as a draft", async () => {
  const user = await open();
  await user.click(
    await screen.findByRole("checkbox", { name: /Requirements.pdf/ }),
  );
  await user.type(
    screen.getByLabelText("Description"),
    "Consider opposing views.",
  );
  await user.click(screen.getByRole("button", { name: /Debate/ }));
  await user.type(
    screen.getByLabelText("Debate topic or scenario"),
    "Should software teams use AI?",
  );
  await user.click(screen.getByRole("button", { name: "Save draft" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/platform/assignments",
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          instructions: "Consider opposing views.",
          tool: "debate",
          config: expect.objectContaining({
            document_ids: ["d1"],
            scenario: "Should software teams use AI?",
          }),
        }),
      }),
    ),
  );
});
test("clear all removes selected documents", async () => {
  const user = await open();
  await user.click(
    await screen.findByRole("checkbox", { name: /Requirements.pdf/ }),
  );
  expect(
    screen.getByRole("heading", { name: "Selected documents (1)" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Clear all" }));
  expect(
    screen.getByRole("heading", { name: "Selected documents (0)" }),
  ).toBeInTheDocument();
});

test("Socratic settings can approve and prepare keywords", async () => {
  const user = await open();
  await user.click(
    await screen.findByRole("checkbox", { name: /Requirements.pdf/ }),
  );
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.type(
    await screen.findByRole("textbox", { name: "New keyword" }),
    "design",
  );
  await user.click(
    screen.getByRole("button", { name: "Add optional keyword" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Approve keyword design" }),
  );
  await user.click(screen.getByRole("button", { name: "Confirm keywords" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/platform/assignments/a1/keywords/confirm",
      { method: "POST" },
    ),
  );
  expect(
    await screen.findByText(
      "Keywords confirmed. Course materials are prepared; publish when ready.",
    ),
  ).toBeInTheDocument();
});

test("SDL review prepares a lesson before showing publish", async () => {
  const user = await open();
  await user.click(
    await screen.findByRole("checkbox", { name: /Requirements.pdf/ }),
  );
  await user.click(
    screen.getByRole("button", { name: /Self Directed Learning/ }),
  );
  await user.click(screen.getByRole("button", { name: "Review activity" }));
  expect(await screen.findByText("Prepared lesson")).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith("/platform/assignments/a1/prepare-sdl", {
    method: "POST",
  });
  expect(
    screen.getByRole("button", { name: "Publish activity" }),
  ).toBeEnabled();
});
test("Debate can proceed to publish while AIducate stays a draft", async () => {
  const user = await open();
  await user.click(screen.getByRole("button", { name: /Debate/ }));
  await user.click(screen.getByRole("button", { name: "Review activity" }));
  expect(
    screen.getByRole("button", { name: "Publish activity" }),
  ).toBeEnabled();
  await user.click(screen.getByRole("button", { name: /AIducate/ }));
  await user.click(screen.getByRole("button", { name: "Review activity" }));
  expect(
    screen.getByRole("button", { name: "Publish activity" }),
  ).toBeEnabled();
});

test("SDL selection immediately exposes sub-questions without a course picker", async () => {
  const user = await open();
  await user.click(
    screen.getByRole("button", { name: /Self Directed Learning/ }),
  );
  expect(screen.getByLabelText("Sub-questions")).toBeInTheDocument();
  expect(screen.queryByLabelText("Course")).not.toBeInTheDocument();
});

test("draft chat choices remain available and preserve settings while switching", async () => {
  const user = await open();
  await user.click(screen.getByRole("button", { name: /Debate/ }));
  await user.type(
    screen.getByLabelText("Debate topic or scenario"),
    "Should teams prioritize maintainability?",
  );
  for (const name of ["Save draft", "Review activity", "Publish activity"])
    expect(
      screen.getByRole("button", { name, exact: true }),
    ).toBeInTheDocument();
  await user.click(
    screen.getByRole("button", { name: /Self Directed Learning/ }),
  );
  expect(screen.getByLabelText("Sub-questions")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Debate/ })).toBeEnabled();
  await user.click(screen.getByRole("button", { name: /Debate/ }));
  expect(screen.getByLabelText("Debate topic or scenario")).toHaveValue(
    "Should teams prioritize maintainability?",
  );
});

test("clicking blank space clears selection while preserving entered chat settings", async () => {
  const user = await open();
  await user.click(screen.getByRole("button", { name: /Debate/ }));
  await user.type(
    screen.getByLabelText("Debate topic or scenario"),
    "Should we optimize early?",
  );
  expect(
    screen.getByRole("heading", { name: "Debate settings" }),
  ).toBeInTheDocument();
  await user.click(document.body);
  expect(
    screen.queryByRole("heading", { name: "Debate settings" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Assignment title")).toHaveValue(
    "Compare design choices",
  );
  await user.click(screen.getByRole("button", { name: /Debate/ }));
  expect(screen.getByLabelText("Debate topic or scenario")).toHaveValue(
    "Should we optimize early?",
  );
});

test("native due-date input is included in the saved draft", async () => {
  const user = await open();
  fireEvent.input(screen.getByLabelText("Due date"), {
    target: { value: "2026-11-20T17:30" },
  });
  await user.click(screen.getByRole("button", { name: /Debate/ }));
  await user.click(
    screen.getByRole("button", { name: "Save draft", exact: true }),
  );
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/platform/assignments",
      expect.objectContaining({
        body: expect.objectContaining({
          due_at: new Date("2026-11-20T17:30").toISOString(),
        }),
      }),
    ),
  );
});

test("Publish stays active and explains missing course materials", async () => {
  const user = await open();
  await user.click(
    screen.getByRole("button", { name: /Self Directed Learning/ }),
  );
  const publish = screen.getByRole("button", {
    name: "Publish activity",
    exact: true,
  });
  expect(publish).toBeEnabled();
  await user.click(publish);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Select at least one indexed course document",
  );
  expect(api.mock.calls.some(([path]) => path.includes("/prepare-sdl"))).toBe(
    false,
  );
});
test("Publish explains a missing activity choice without a disabled button", async () => {
  const user = await open();
  await user.click(
    screen.getByRole("button", { name: "Publish activity", exact: true }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Select an activity type.",
  );
});
