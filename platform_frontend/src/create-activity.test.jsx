import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import {
  act,
  render,
  screen,
  waitFor,
  fireEvent,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
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
let courseFiles;
beforeEach(() => {
  resetCourseContext();
  courseFiles = [
    {
      file_id: "f1",
      document_id: "d1",
      filename: "Requirements.pdf",
      file_size: 2048,
    },
  ];
  api.mockReset();
  api.mockImplementation(async (path, options) => {
    if (path.startsWith("/platform/context")) return course;
    if (path === "/platform/courses/course-1/documents")
      return { files: courseFiles };
    if (
      path === "/platform/courses/course-1/documents/upload" &&
      options?.method === "POST"
    ) {
      courseFiles = [
        ...courseFiles,
        {
          file_id: "f2",
          document_id: "d2",
          filename: "New lesson.pdf",
          file_size: 1024,
        },
      ];
      return { files: [{ file_id: "f2", document_id: "d2" }] };
    }
    if (path === "/courses/course-1/documents")
      return { files: courseFiles };
    if (path === "/courses/course-1/learning-objectives")
      return { objectives: [] };
    if (path === "/courses/course-1/documents/f1/keyword-suggestions")
      return { keywords: ["design patterns"], message: "Generated." };
    if (path === "/courses/course-1/documents/f2/keyword-suggestions")
      return { keywords: ["new lesson topic"], message: "Generated." };
    if (path === "/courses/course-1/socratic-setup/generate")
      return {
        keywords: ["design choices"],
        prompt: "Imagine a team choosing a design. Which choice would you test first?",
        minimum_messages: 4,
        instructions: "Discuss design choices, then submit your design through Canvas.",
        source_files: ["Requirements.pdf"],
        source_chunk_ids: ["chunk-1"],
        learning_steps: [
          { title: "Understand the design", goal: "Explain the design requirements.", scenario: "A team begins by reviewing its design requirements.", question: "Which requirement should the team examine first?", evidence_quote: "Review the design requirements.", source_chunk_id: "chunk-1", source_file: "Requirements.pdf" },
          { title: "Submit your design", goal: "Describe the design you will submit.", scenario: "The same team finishes its design and prepares to submit it.", question: "What should the team include in its submission?", evidence_quote: "Submit the design through Canvas.", source_chunk_id: "chunk-1", source_file: "Requirements.pdf" },
        ],
      };
    if (path === "/courses/course-1/socratic-opening/generate")
      return {
        prompt: "A team must choose a design. What would you examine first?",
        source_files: ["Requirements.pdf"],
      };
    if (
      path.startsWith("/courses/course-1/documents/") &&
      options?.method === "DELETE"
    ) {
      const fileId = path.split("/").at(-1);
      courseFiles = courseFiles.filter((file) => file.file_id !== fileId);
      return { deleted: true };
    }
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

test("assignment material picker offers Python, Word and PowerPoint files", async () => {
  await open();
  const picker = document.querySelector('input[type="file"]');
  for (const extension of [".py", ".doc", ".docx", ".ppt", ".pptx"]) {
    expect(picker.getAttribute("accept").split(",")).toContain(extension);
  }
});
test("activity details offer an optional field-by-field tutorial", async () => {
  const user = await open();
  expect(screen.queryByRole("dialog", { name: "Assignment tutorial" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Open assignment tutorial" }));
  const tutorial = screen.getByRole("dialog", { name: "Assignment tutorial" });
  expect(tutorial).toHaveTextContent("Step 1 of 6");
  expect(screen.getByLabelText("Assignment title").closest("label")).toHaveClass("activity-tutorial-highlight");
  await user.click(within(tutorial).getByRole("button", { name: "Next" }));
  expect(tutorial).toHaveTextContent("Due date");
  expect(screen.getByLabelText("Due date").closest("label")).toHaveClass("activity-tutorial-highlight");
  expect(screen.getByLabelText("Assignment title").closest("label")).not.toHaveClass("activity-tutorial-highlight");
  await user.click(within(tutorial).getByRole("button", { name: "Next" }));
  expect(screen.getByLabelText("Description").closest("label")).toHaveClass("activity-tutorial-highlight");
  await user.click(within(tutorial).getByRole("button", { name: "Close tutorial" }));
  expect(screen.queryByRole("dialog", { name: "Assignment tutorial" })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Description").closest("label")).not.toHaveClass("activity-tutorial-highlight");
  await waitFor(() => expect(screen.getByRole("button", { name: "Open assignment tutorial" })).toHaveFocus());
});
test("tutorial explains the selected activity settings and closes with Escape", async () => {
  const user = await open();
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.click(screen.getByRole("button", { name: "Open assignment tutorial" }));
  const tutorial = screen.getByRole("dialog", { name: "Assignment tutorial" });
  expect(tutorial).toHaveTextContent("Step 1 of 7");
  for (let step = 0; step < 5; step += 1) {
    await user.click(within(tutorial).getByRole("button", { name: "Next" }));
  }
  expect(tutorial).toHaveTextContent("Step 6 of 7");
  expect(tutorial).toHaveTextContent("Choose a basic conversation or a guided path");
  expect(document.querySelector('[data-activity-tutorial="settings"]')).toHaveClass("activity-tutorial-highlight");
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog", { name: "Assignment tutorial" })).not.toBeInTheDocument();
});
test("the selected activity shows a checkmark and only one choice stays selected", async () => {
  const user = await open();
  const socratic = screen.getByRole("button", { name: /Socratic Chat/ });
  const debate = screen.getByRole("button", { name: /Debate/ });
  await user.click(socratic);
  expect(socratic).toHaveAttribute("aria-pressed", "true");
  expect(socratic.querySelector(".activity-selected-indicator")).toHaveTextContent("✓ Selected");
  expect(debate.querySelector(".activity-selected-indicator")).toBeNull();
  await user.click(debate);
  expect(socratic).toHaveAttribute("aria-pressed", "false");
  expect(socratic.querySelector(".activity-selected-indicator")).toBeNull();
  expect(debate.querySelector(".activity-selected-indicator")).toHaveTextContent("✓ Selected");
});
test("clicking outside the activity cards keeps the selected activity and its settings", async () => {
  const user = await open();
  const socratic = screen.getByRole("button", { name: /Socratic Chat/ });
  await user.click(socratic);
  await user.click(screen.getByRole("heading", { name: "Assignment Configuration" }));
  expect(socratic).toHaveAttribute("aria-pressed", "true");
  expect(socratic.querySelector(".activity-selected-indicator")).toHaveTextContent("✓ Selected");
  expect(screen.getByRole("heading", { name: "Socratic Chat settings" })).toBeInTheDocument();
  await user.click(screen.getByRole("heading", { name: "Course materials" }));
  expect(socratic).toHaveAttribute("aria-pressed", "true");
});
test("publishing opens the new assignment with its student preview requested", async () => {
  const original = api.getMockImplementation();
  api.mockImplementation((path, options) =>
    path === "/platform/assignments/a1/publish" && options?.method === "POST"
      ? Promise.resolve({ status: "published" })
      : original(path, options),
  );
  function PublishedRoute() {
    const location = useLocation();
    return <p>{location.state?.showStudentPreview ? "Student preview requested" : "Preview missing"}</p>;
  }
  render(<MemoryRouter initialEntries={["/professor/activities/new"]}><Routes>
    <Route path="/professor/activities/new" element={<CreateActivity />} />
    <Route path="/professor/activities/:id" element={<PublishedRoute />} />
  </Routes></MemoryRouter>);
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Assignment title"), "Compare design choices");
  await user.click(await screen.findByRole("checkbox", { name: /Requirements.pdf/ }));
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await screen.findByRole("heading", { name: "Review and publish" });
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  expect(await screen.findByText("Student preview requested")).toBeInTheDocument();
});
test("new Socratic activities use selected assignment materials without requiring keywords", async () => {
  const user = await open();
  await user.click(await screen.findByRole("checkbox", { name: /Requirements.pdf/ }));
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  expect(screen.getByText(/Teaching scope:/).closest("p")).toHaveTextContent("Selected assignment materials");
  expect(screen.queryByRole("region", { name: "Approved keywords" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await screen.findByRole("heading", { name: "Review and publish" });
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/platform/assignments",
      expect.objectContaining({
        body: expect.objectContaining({
          config: expect.objectContaining({ scope_mode: "assignment", document_ids: ["d1"] }),
        }),
      }),
    ),
  );
});
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
  expect(screen.getByText(/Teaching scope:/).closest("p")).toHaveTextContent("Selected assignment materials");
  expect(
    screen.getByRole("heading", { name: "Socratic Chat settings" }),
  ).toBeInTheDocument();
  expect(
    screen.getByLabelText("Opening question or prompt"),
  ).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /Basic conversation/ })).toBeChecked();
  expect(screen.queryByRole("button", { name: "Generate setup from selected sources" })).not.toBeInTheDocument();
  expect(
    screen.getByLabelText("Messages required before completion"),
  ).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Optional keywords" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Course documents" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Review activity" }));
  expect(
    screen.getByRole("button", { name: "Publish activity" }),
  ).toBeEnabled();
  await user.type(screen.getByLabelText("Student instructions and submission"), "Updated instructions");
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

test("a PDF upload appears in the course library and is selected", async () => {
  const user = await open();
  await user.upload(
    document.querySelector('input[type="file"]'),
    new File(["%PDF-1.4"], "New lesson.pdf", { type: "application/pdf" }),
  );
  expect(await screen.findByRole("checkbox", { name: /New lesson.pdf/ })).toBeChecked();
  expect(screen.getByText("Documents uploaded and ready to select.")).toBeInTheDocument();
});

test("an embedding failure is shown next to the upload control", async () => {
  const user = await open();
  await screen.findByRole("checkbox", { name: /Requirements.pdf/ });
  api.mockImplementationOnce(async () => {
    throw new Error("Document search has no configured embedding provider.");
  });
  await user.upload(
    document.querySelector('input[type="file"]'),
    new File(["%PDF-1.4"], "New lesson.pdf", { type: "application/pdf" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("embedding provider");
});

test("a completed request is not reported as success when the PDF is absent from the refreshed library", async () => {
  const user = await open();
  await screen.findByRole("checkbox", { name: /Requirements.pdf/ });
  const originalApi = api.getMockImplementation();
  api.mockImplementation((path, options) =>
    path === "/platform/courses/course-1/documents/upload" && options?.method === "POST"
      ? Promise.resolve({ files: [{ file_id: "missing", document_id: "d2" }] })
      : originalApi(path, options),
  );
  await user.upload(
    document.querySelector('input[type="file"]'),
    new File(["%PDF-1.4"], "New lesson.pdf", { type: "application/pdf" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("not in this course's library");
  expect(screen.queryByText("Documents uploaded and ready to select.")).not.toBeInTheDocument();
});

test("instructors can delete uploaded documents from course materials", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const user = await open();
  await user.click(
    await screen.findByRole("checkbox", { name: /Requirements.pdf/ }),
  );
  await user.click(
    screen.getByRole("button", { name: "Delete Requirements.pdf" }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("checkbox", { name: /Requirements.pdf/ }),
    ).not.toBeInTheDocument(),
  );
  expect(
    screen.getByRole("heading", { name: "Selected documents (0)" }),
  ).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith(
    "/courses/course-1/documents/f1",
    { method: "DELETE" },
  );
});

test.skip("legacy keyword preparation is no longer part of Socratic setup", async () => {
  const user = await open();
  await user.click(
    await screen.findByRole("checkbox", { name: /Requirements.pdf/ }),
  );
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.selectOptions(screen.getByLabelText("Teaching scope"), "keywords");
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

test.skip("legacy keyword suggestions are no longer part of Socratic setup", async () => {
  const user = await open();
  await user.click(
    await screen.findByRole("checkbox", { name: /Requirements.pdf/ }),
  );
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.selectOptions(screen.getByLabelText("Teaching scope"), "keywords");
  await user.click(
    await screen.findByRole("button", { name: "Suggest keywords only" }),
  );
  expect(
    await screen.findByRole("button", {
      name: "Approve keyword design patterns",
    }),
  ).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith(
    "/courses/course-1/documents/f1/keyword-suggestions",
    { method: "POST" },
  );
});

test("source generation drafts editable opening, submission and completion settings", async () => {
  const user = await open();
  await user.click(await screen.findByRole("checkbox", { name: /Requirements.pdf/ }));
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.click(screen.getByRole("radio", { name: /Guided learning path/ }));
  await user.click(screen.getByRole("button", { name: "Generate setup from selected sources" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith(
    "/courses/course-1/socratic-setup/generate",
    expect.objectContaining({ method: "POST", body: expect.objectContaining({ document_ids: ["d1"] }) }),
  ));
  expect(screen.queryByRole("region", { name: "Approved keywords" })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Opening question or prompt")).toHaveValue(
    "Imagine a team choosing a design. Which choice would you test first?",
  );
  expect(screen.getByLabelText("Messages required before completion")).toHaveValue(4);
  expect(screen.getByLabelText("Student instructions and submission")).toHaveValue(
    "Discuss design choices, then submit your design through Canvas.",
  );
  expect(screen.getByRole("region", { name: "Learning steps" })).toHaveTextContent("Understand the design");
  const steps = screen.getByRole("region", { name: "Learning steps" });
  expect(within(steps).getAllByText("Requirements.pdf")).toHaveLength(2);
  expect(within(steps).getAllByLabelText("Step title")).toHaveLength(1);
  const secondStep = within(steps).getByRole("button", { name: /Step 2.*Submit your design.*What should the team include/ });
  expect(secondStep).toHaveAttribute("aria-expanded", "false");
  await user.click(secondStep);
  expect(secondStep).toHaveAttribute("aria-expanded", "true");
  expect(within(steps).getByLabelText("Step title")).toHaveValue("Submit your design");
  expect(within(steps).getByLabelText("How the assignment scenario continues")).toHaveValue("The same team finishes its design and prepares to submit it.");
  expect(within(steps).getByLabelText("Question for this step")).toHaveValue("What should the team include in its submission?");
  expect(within(steps).getAllByLabelText("Step title")).toHaveLength(1);
  await user.clear(screen.getByLabelText("Opening question or prompt"));
  await user.type(screen.getByLabelText("Opening question or prompt"), "What would you try next?");
  expect(screen.getByLabelText("Opening question or prompt")).toHaveValue("What would you try next?");
  await user.click(screen.getByRole("button", { name: "Move step 2 up" }));
  expect(within(steps).getAllByText("Submit your design")[0]).toBeInTheDocument();
  expect(within(steps).getByLabelText("Step title")).toHaveValue("Submit your design");
  expect(screen.getByRole("button", { name: "Publish activity" })).toBeEnabled();
});

test("generated steps can be dragged, moved with buttons, and removed", async () => {
  const user = await open();
  await user.click(await screen.findByRole("checkbox", { name: /Requirements.pdf/ }));
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.click(screen.getByRole("radio", { name: /Guided learning path/ }));
  await user.click(screen.getByRole("button", { name: "Generate setup from selected sources" }));
  const steps = await screen.findByRole("region", { name: "Learning steps" });
  const cards = () => [...steps.querySelectorAll(".socratic-learning-step")];
  const names = () => [...steps.querySelectorAll(".socratic-step-name")].map((node) => node.textContent);
  await waitFor(() => expect(cards()).toHaveLength(2));
  expect(names()).toEqual(["Understand the design", "Submit your design"]);
  expect(within(steps).getAllByLabelText("Step title")).toHaveLength(1);
  const firstCard = cards()[0];
  const secondCard = cards()[1];
  const transfer = { effectAllowed: "", dropEffect: "", setData: vi.fn() };
  expect(firstCard).toHaveAttribute("draggable", "true");
  expect(fireEvent.dragStart(within(firstCard).getByLabelText("Step title"), { dataTransfer: transfer })).toBe(false);
  expect(transfer.setData).not.toHaveBeenCalled();
  fireEvent.dragStart(firstCard.querySelector(".socratic-step-summary"), { dataTransfer: transfer });
  fireEvent.dragOver(secondCard, { dataTransfer: transfer });
  expect(secondCard).toHaveClass("is-drag-over-after");
  fireEvent.drop(secondCard, { dataTransfer: transfer });
  expect(names()).toEqual(["Submit your design", "Understand the design"]);
  expect(within(steps).getByLabelText("Step title")).toHaveValue("Understand the design");
  expect(transfer.setData).toHaveBeenCalledWith("text/plain", "0");

  expect(screen.getByRole("button", { name: "Move step 1 down" })).toHaveClass("socratic-step-move");
  await user.click(screen.getByRole("button", { name: "Move step 1 down" }));
  expect(names()).toEqual(["Understand the design", "Submit your design"]);
  const remove = screen.getByRole("button", { name: "Remove step 2" });
  expect(remove).toHaveClass("socratic-step-remove");
  await user.click(remove);
  expect(cards()).toHaveLength(1);
});

test("guided mode cannot publish an empty path and basic mode keeps the professor's question", async () => {
  const user = await open();
  await user.click(await screen.findByRole("checkbox", { name: /Requirements.pdf/ }));
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.type(screen.getByLabelText("Opening question or prompt"), "What would you test first?");
  await user.click(screen.getByRole("radio", { name: /Guided learning path/ }));
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/Generate a learning path before publishing/);
  await waitFor(() => expect(screen.getByRole("button", { name: "Generate setup from selected sources" })).toHaveFocus());
  expect(api).not.toHaveBeenCalledWith("/platform/assignments", expect.objectContaining({ method: "POST" }));
  await user.click(screen.getByRole("radio", { name: /Basic conversation/ }));
  expect(screen.getByLabelText("Opening question or prompt")).toHaveValue("What would you test first?");
  expect(screen.queryByRole("region", { name: "Learning steps" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await screen.findByText("Review the activity below, then select Publish activity to confirm.");
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/platform/assignments", expect.objectContaining({
    body: expect.objectContaining({ config: expect.objectContaining({ guidance_mode: "basic", learning_steps: [] }) }),
  })));
});

test("basic conversation generates only the opening question", async () => {
  const user = await open();
  await user.click(await screen.findByRole("checkbox", { name: /Requirements.pdf/ }));
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  const opening = screen.getByLabelText("Opening question or prompt");
  await user.type(opening, "An instructor's original question?");
  const generate = screen.getByRole("button", { name: "Generate opening question" });
  expect(generate).toBeEnabled();
  await user.click(generate);
  await waitFor(() => expect(opening).toHaveValue("A team must choose a design. What would you examine first?"));
  expect(api).toHaveBeenCalledWith(
    "/courses/course-1/socratic-opening/generate",
    expect.objectContaining({ method: "POST", body: expect.objectContaining({ document_ids: ["d1"] }) }),
  );
  expect(api).not.toHaveBeenCalledWith("/courses/course-1/socratic-setup/generate", expect.anything());
  expect(screen.getByLabelText("Messages required before completion")).toHaveValue(1);
  expect(screen.queryByRole("region", { name: "Learning steps" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("radio", { name: /Guided learning path/ }));
  expect(screen.queryByRole("button", { name: "Generate opening question" })).not.toBeInTheDocument();
});

test("source generation shows animated progress until the model finishes", async () => {
  const user = await open();
  await user.click(await screen.findByRole("checkbox", { name: /Requirements.pdf/ }));
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.click(screen.getByRole("radio", { name: /Guided learning path/ }));
  const original = api.getMockImplementation();
  let finishGeneration;
  api.mockImplementation((path, options) =>
    path === "/courses/course-1/socratic-setup/generate"
      ? new Promise((resolve) => { finishGeneration = resolve; })
      : original(path, options),
  );
  await user.click(screen.getByRole("button", { name: "Generate setup from selected sources" }));
  const progress = screen.getByRole("status", { name: "BrainTutor: Generating setup from selected documents" });
  expect(progress).toHaveClass("generation-overlay");
  expect(progress.querySelector(".generation-status-fullscreen")).toBeInTheDocument();
  expect(progress.querySelector(".thinking-orbit-particles")).toBeInTheDocument();
  await act(async () => finishGeneration({
    keywords: ["design choices"], prompt: "What would you try?", minimum_messages: 3,
    instructions: "Discuss design choices.", source_files: ["Requirements.pdf"],
  }));
  await waitFor(() => expect(screen.queryByRole("status", { name: "BrainTutor: Generating setup from selected documents" })).not.toBeInTheDocument());
});

test("uploading an indexed document activates source-based setup generation", async () => {
  courseFiles = [];
  const user = await open();
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.click(screen.getByRole("radio", { name: /Guided learning path/ }));
  const generate = await screen.findByRole("button", {
    name: "Generate setup from selected sources",
  });
  expect(generate).toHaveClass("socratic-generate-setup");
  expect(generate).toBeDisabled();
  fireEvent.change(document.querySelector('input[type="file"][multiple]'), {
    target: {
      files: [
        new File(["lesson"], "New lesson.pdf", {
          type: "application/pdf",
        }),
      ],
    },
  });
  await waitFor(() => expect(generate).toBeEnabled());
  await user.click(generate);
  expect(await screen.findByLabelText("Opening question or prompt")).toHaveValue(
    "Imagine a team choosing a design. Which choice would you test first?",
  );
  expect(api).toHaveBeenCalledWith(
    "/courses/course-1/socratic-setup/generate",
    expect.objectContaining({ method: "POST", body: expect.objectContaining({ document_ids: ["d2"] }) }),
  );
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

test("clicking blank space keeps the selection and entered chat settings", async () => {
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
    screen.getByRole("heading", { name: "Debate settings" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Debate/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("Assignment title")).toHaveValue(
    "Compare design choices",
  );
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
  await waitFor(() => expect(screen.getByRole("checkbox", { name: /Requirements.pdf/ })).toHaveFocus());
  expect(screen.getByText("Select at least one indexed course document or upload course materials.", { selector: ".publish-inline-error" })).toBeInTheDocument();
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
  await waitFor(() => expect(screen.getByRole("button", { name: /Socratic Chat/ })).toHaveFocus());
});

test("Publish moves to the first missing field, then to the next requirement", async () => {
  const user = await open();
  const title = screen.getByLabelText("Assignment title");
  await user.clear(title);
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await waitFor(() => expect(title).toHaveFocus());
  expect(title.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
  expect(screen.getByText("Enter an activity title.", { selector: ".publish-inline-error" })).toBeInTheDocument();
  await user.type(title, "A new activity");
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await waitFor(() => expect(screen.getByRole("button", { name: /Socratic Chat/ })).toHaveFocus());
});

test("Publish focuses the missing reflection sub-topic and debate scenario", async () => {
  const user = await open();
  await user.click(screen.getByRole("button", { name: /Reflections/ }));
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await waitFor(() => expect(screen.getByLabelText(/Sub-topics to explore/)).toHaveFocus());
  await user.click(screen.getByRole("button", { name: /Debate/ }));
  await user.clear(screen.getByLabelText("Assignment title"));
  await user.type(screen.getByLabelText("Assignment title"), "Debate");
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await waitFor(() => expect(screen.getByLabelText(/Debate topic or scenario/)).toHaveFocus());
});

test("Publish moves through missing milestone reflection fields", async () => {
  const user = await open();
  await user.click(screen.getByRole("button", { name: /Reflections/ }));
  await user.selectOptions(screen.getByLabelText("Reflection type"), "milestone_based");
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await waitFor(() => expect(screen.getByLabelText("Milestone prompt")).toHaveFocus());
  expect(screen.getByLabelText("Milestone prompt")).toHaveAttribute("aria-invalid", "true");
  await user.type(screen.getByLabelText("Milestone prompt"), "What did you try this week?");
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await waitFor(() => expect(screen.getByLabelText("Historical responses (CSV)")).toHaveFocus());
});

test("a server-side publishing requirement moves back to the affected materials", async () => {
  const original = api.getMockImplementation();
  api.mockImplementation((path, options) =>
    path === "/platform/assignments/a1/publish" && options?.method === "POST"
      ? Promise.reject(new Error("Some course materials have no indexed content. Re-upload them before publishing."))
      : original(path, options),
  );
  const user = await open();
  await user.click(screen.getByRole("checkbox", { name: /Requirements.pdf/ }));
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  await screen.findByRole("heading", { name: "Review and publish" });
  await user.click(screen.getByRole("button", { name: "Publish activity" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("no indexed content");
  await waitFor(() => expect(screen.getByRole("checkbox", { name: /Requirements.pdf/ })).toHaveFocus());
});
