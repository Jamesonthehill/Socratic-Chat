import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "./main";
import { SESSION_KEY } from "./api";
import { resetCourseContext } from "./courseContext";
beforeEach(resetCourseContext);

const course = "8b71218d-71f3-436e-a4a6-1b279c4fda79";
const assignment = {
  id: "assignment-1",
  course_id: course,
  course_code: "SE101",
  tool: "socratic",
  title: "Discuss requirements",
  instructions: "Connect your ideas.",
  due_at: null,
  status: "published",
  progress: "not_started",
  student_config: { minimum_messages: 1 },
};
const attempt = {
  id: "attempt-1",
  status: "in_progress",
  engine_state: {},
  messages: [
    { role: "assistant", content: "What makes a requirement useful?" },
  ],
};

function mockApi(role = "instructor", override = {}) {
  localStorage.setItem(
    SESSION_KEY,
    JSON.stringify({
      access_token: "test-session",
      expires_at: Date.now() + 3600000,
    }),
  );
  const responses = {
    "/api/auth/me": {
      user: {
        username: "Alex",
        display_name: "Alex Rivera",
        authority_level: role === "instructor" ? 1 : 2,
        onboarding_complete: true,
      },
    },
    "/api/platform/context": {
      course_id: course,
      course_code: "SE101",
      title: "Software Engineering",
    },
    "/api/platform/assignments": [assignment],
    "/api/courses": {
      courses: [
        {
          course_id: course,
          course_code: "SE101",
          title: "Software Engineering",
          description: "Build software collaboratively.",
          instructor_name: "Professor Rivera",
          document_count: 2,
          membership_role: role === "instructor" ? "instructor" : "student",
          membership_status: "approved",
        },
      ],
    },
    [`/api/instructor/enrolled-students?course_id=${course}`]: [
      {
        user_id: "student-1",
        display_name: "Jordan",
        email: "jordan@example.test",
      },
    ],
    [`/api/courses/${course}/documents`]: { files: [] },
    [`/api/courses/${course}/learning-objectives`]: { objectives: [] },
    "/api/platform/topic-templates": [],
    "/api/platform/assignments/assignment-1": assignment,
    "/api/platform/assignments/assignment-1/materials": { materials: [] },
    "/api/platform/assignments/assignment-1/attempt": null,
    "/api/platform/assignments/assignment-1/start": attempt,
    "POST /api/platform/assignments/assignment-1/evidence-diagram": {
      steps: ["Version control preserves revision history", "revision history for a team."],
    },
    ...override,
  };
  const fetch = vi.fn(async (url, options = {}) => {
    const originalUrl = url;
    if (url.startsWith("/api/platform/context")) url = "/api/platform/context";
    if (url.startsWith("/api/platform/assignments?"))
      url = "/api/platform/assignments";
    const entry =
      responses[`${options.method || "GET"} ${url}`] ?? responses[url];
    if (entry === undefined) throw new Error("Unexpected API call: " + url);
    const data = typeof entry === "function" ? await entry(options, originalUrl) : entry;
    return {
      ok: !data?.error,
      status: data?.error ? 422 : 200,
      json: async () => (data?.error ? { detail: data.error } : data),
      blob: async () => data instanceof Blob ? data : new Blob([JSON.stringify(data)]),
    };
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
function open(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

test("user selects and persists the platform color theme", async () => {
  mockApi("student");
  open("/student");
  const user = userEvent.setup();

  expect(await screen.findByRole("link", { name: /BrainTutor/ })).toBeInTheDocument();
  const theme = await screen.findByLabelText("Choose color theme");
  expect(theme).toHaveValue("light");

  await user.selectOptions(theme, "dark");

  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  expect(localStorage.getItem("socratic_chat_theme")).toBe("dark");
});

test("professor opens activity creation from assignments rather than the teaching toolkit", async () => {
  mockApi();
  open("/professor");
  const user = userEvent.setup();
  expect(
    await screen.findByRole("heading", { level: 1, name: "All assignments" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Courses & access" })).not.toBeInTheDocument();
  expect(screen.queryByText("Your teaching toolkit")).not.toBeInTheDocument();
  await user.click(
    screen.getByRole("link", { name: "Analytics", exact: true }),
  );
  expect(
    screen.getByRole("link", { name: "Analytics", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  expect(screen.getByText("Analytics will come here.")).toBeInTheDocument();
  await user.click(
    screen.getByRole("link", { name: "Professor dashboard", exact: true }),
  );
  await user.click(screen.getByRole("link", { name: /Create New Activity/ }));
  expect(
    await screen.findByRole("heading", { name: "Activity details" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Course materials" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Select activity" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("Student Agent Bot")).not.toBeInTheDocument();
});

test("professor dashboard lists managed courses and opens each activity in its own course", async () => {
  const otherCourse = "9db10962-81ad-4fe1-bd37-701f263720e8";
  const other = {
    ...assignment,
    id: "other-activity",
    course_id: otherCourse,
    course_code: "SE202",
    course_title: "Other managed course",
    title: "Co-taught activity",
    status: "draft",
    config: {},
  };
  const fetch = mockApi("instructor", {
    "/api/platform/context": (_options, url) => {
      if (url.includes(`course_id=${otherCourse}`)) return {
        course_id: otherCourse, course_code: "SE202", title: "Other managed course",
      };
      return { error: "A Canvas course must be selected" };
    },
    "/api/platform/assignments": [assignment, other],
    "/api/platform/assignments/other-activity": other,
    [`/api/platform/courses/${otherCourse}/documents`]: { files: [] },
    [`/api/courses/${otherCourse}/learning-objectives`]: { objectives: [] },
  });
  open("/professor");
  expect(await screen.findByRole("link", { name: "Co-taught activity" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Discuss requirements" })).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url.startsWith("/api/platform/context"))).toBe(false);
  await userEvent.setup().click(screen.getByRole("link", { name: "Co-taught activity" }));
  expect(await screen.findByRole("heading", { name: "Activity details" })).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url.includes(`course_id=${otherCourse}`))).toBe(true);
});

test("student sees mixed assignments and opens the assigned tool without selecting configuration", async () => {
  mockApi("student", {
    "/api/platform/assignments": [
      assignment,
      {
        ...assignment,
        id: "reflection-1",
        tool: "reflections",
        title: "Reflect on the sprint",
        progress: "in_progress",
      },
      {
        ...assignment,
        id: "tutor-1",
        tool: "student-agent",
        title: "Practice a use case",
        progress: "completed",
      },
    ],
  });
  open("/student");
  const user = userEvent.setup();
  expect(
    await screen.findByRole("heading", { name: "Your assignments" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Courses & access" }),
  ).not.toBeInTheDocument();
  const ongoing = await screen.findByRole("region", { name: /^Left to do/ });
  expect(
    await within(ongoing).findByRole("link", { name: "Resume" }),
  ).toHaveAttribute("href", "/student/assignments/reflection-1");
  expect(
    screen.queryByRole("link", { name: "View result" }),
  ).not.toBeInTheDocument();
  await user.click(
    within(screen.getByRole("region", { name: /^Left to do/ })).getByRole("link", {
      name: "Open assignment",
    }),
  );
  await user.click(
    await screen.findByRole("button", { name: "Start assignment" }),
  );
  expect(
    await screen.findAllByText("What makes a requirement useful?"),
  ).not.toHaveLength(0);
  expect(screen.queryByLabelText("Student ID")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Reflection type")).not.toBeInTheDocument();
});

test("Socratic tutorial previews every stage without starting the real assignment", async () => {
  mockApi("student");
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  const toggle = await screen.findByRole("button", { name: "Tutorial" });
  expect(toggle).toHaveAttribute("aria-pressed", "false");
  await user.click(toggle);
  const tutorial = screen.getByRole("dialog", { name: "Tutorial" });
  expect(within(tutorial).getByText("Tutorial · 1 of 8")).toBeInTheDocument();
  expect(within(tutorial).getByRole("heading", { name: "Read the assignment" })).toBeInTheDocument();
  expect(tutorial.querySelectorAll(".socratic-spotlight-shade")).toHaveLength(4);
  await user.click(within(tutorial).getByRole("button", { name: "Next" }));
  expect(within(tutorial).getByRole("heading", { name: "Read the course materials" })).toBeInTheDocument();
  await user.click(within(tutorial).getByRole("button", { name: "Next" }));
  expect(within(tutorial).getByRole("heading", { name: "Start with the first example" })).toBeInTheDocument();
  expect(within(tutorial).getByText(/Preview only/)).toBeInTheDocument();
  await user.click(within(tutorial).getByRole("button", { name: "Start assignment" }));
  expect(within(tutorial).getByRole("heading", { name: "Discuss the example" })).toBeInTheDocument();
  await user.click(within(tutorial).getByRole("button", { name: "Send message" }));
  expect(within(tutorial).getByRole("heading", { name: "Continue when ready" })).toBeInTheDocument();
  await user.click(within(tutorial).getByRole("button", { name: "Continue to next step" }));
  expect(within(tutorial).getByRole("heading", { name: "Finish the last topic" })).toBeInTheDocument();
  await user.click(within(tutorial).getByRole("button", { name: "Finish conversation and summarize" }));
  expect(within(tutorial).getByRole("heading", { name: "Summarize and review feedback" })).toBeInTheDocument();
  await user.click(within(tutorial).getByRole("button", { name: "Get final feedback" }));
  expect(within(tutorial).getByRole("heading", { name: "Submit the assignment" })).toBeInTheDocument();
  await user.click(within(tutorial).getByRole("button", { name: "Submit assignment" }));
  expect(screen.getByRole("button", { name: "Start assignment" })).toBeInTheDocument();
  expect(screen.queryByText("What makes a requirement useful?")).not.toBeInTheDocument();
  await user.click(toggle);
  await user.click(screen.getByRole("button", { name: "Close tutorial" }));
  expect(screen.queryByRole("dialog", { name: "Tutorial" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Start assignment" }));
  expect(await screen.findByText("What makes a requirement useful?")).toBeInTheDocument();
});

test("Socratic tutorial highlights the instructor's learning path when one exists", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1": {
      ...assignment,
      student_config: {
        ...assignment.student_config,
        learning_steps: [{ title: "Inspect an example", goal: "Notice the first important condition." }],
      },
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Tutorial" }));
  expect(screen.getByRole("button", { name: "Tutorial" })).not.toHaveClass("secondary");
  expect(screen.getByText("Tutorial · 1 of 9")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByRole("heading", { name: "Review the learning path" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByRole("heading", { name: "Read the course materials" })).toBeInTheDocument();
});

test("guided Socratic chat opens with its scenario and first question", async () => {
  const scenario = "A customer reaches the sandwich machine and sees the size menu.";
  const question = "How should the program handle the customer's first choice?";
  mockApi("student", {
    "/api/platform/assignments/assignment-1/start": {
      ...attempt,
      engine_state: { socratic: { phase: "teaching", learning_step_index: 0, next_thinking_step: question } },
      messages: [{ role: "assistant", content: `Step 1: Choose size\n\n${scenario}\n\n${question}` }],
    },
  });
  open("/student/assignments/assignment-1");
  await userEvent.setup().click(await screen.findByRole("button", { name: "Start assignment" }));
  expect(await screen.findByText(scenario)).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Your next thinking step" })).getByText(question)).toBeInTheDocument();
});

test("guided Socratic opening shows a source-backed menu table without a passage button", async () => {
  const source = {
    chunk_id: "menu-1", title: "Sandwich assignment.pdf", page_number: 3,
    evidence_quote: "What would you like? (small/ medium/ large/ off/ report)",
    text: "What would you like? (small/ medium/ large/ off/ report): small Please insert coins.",
  };
  mockApi("student", {
    "/api/platform/assignments/assignment-1": {
      ...assignment, student_config: { minimum_messages: 1, guidance_mode: "guided",
        learning_steps: [{ title: "Choose a size", goal: "Read the menu", source }] },
    },
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt, engine_state: { socratic: { phase: "teaching", learning_step_index: 0 } },
      messages: [{ role: "assistant", content: "The machine shows its menu. Which option would you choose?" }],
    },
  });
  open("/student/assignments/assignment-1");
  const table = await screen.findByRole("region", { name: "Visible course source" });
  expect(within(table).getByText("Sandwich assignment.pdf · page 3")).toBeInTheDocument();
  expect(within(table).getByRole("cell", { name: "small" })).toBeInTheDocument();
  expect(within(table).getByRole("cell", { name: "report" })).toBeInTheDocument();
  expect(within(table).queryByRole("button", { name: "View passage" })).not.toBeInTheDocument();
});

test("Socratic source cards remain with the reply that produced them", async () => {
  const firstSource = {
    document_id: "doc", chunk_id: "menu-1", title: "Menu.pdf", page_number: 1,
    evidence_quote: "What would you like? (small/ medium/ off)",
    text: "What would you like? (small/ medium/ off)",
  };
  const secondSource = {
    document_id: "doc", chunk_id: "payment-1", title: "Payment.pdf", page_number: 2,
    text: "Payment must be checked before the sandwich is served.",
  };
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      engine_state: { sources: [secondSource] },
      messages: [
        { role: "assistant", content: "Which menu option would you choose?", sources: [firstSource] },
        { role: "user", content: "small" },
        { role: "assistant", content: "How should payment be checked?", sources: [secondSource] },
      ],
    },
  });
  open("/student/assignments/assignment-1");
  const tutorCards = await screen.findAllByText("Socratic tutor");
  const firstCard = tutorCards[0].closest(".socratic-message-card");
  const secondCard = tutorCards[1].closest(".socratic-message-card");
  await userEvent.setup().click(within(firstCard).getByRole("button", { name: "View supporting sources" }));
  expect(firstCard).toHaveTextContent("Menu.pdf");
  expect(firstCard).not.toHaveTextContent("Payment.pdf");
  expect(within(firstCard).getByText("Choices shown in the source")).toBeInTheDocument();
  expect(within(secondCard).queryByText("Choices shown in the source")).not.toBeInTheDocument();
  await userEvent.setup().click(within(secondCard).getByRole("button", { name: "View supporting sources" }));
  expect(secondCard).toHaveTextContent("Payment.pdf");
  expect(secondCard).not.toHaveTextContent("Menu.pdf");
});

test("Socratic reply keeps its next-thinking-step box when the explanation has no final question", async () => {
  const question = "What exact prompt should show all five choices?";
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      engine_state: { socratic: { next_thinking_step: question } },
      messages: [{
        role: "assistant",
        content: "Include small, medium, large, off, and report. For example, `print(What would you like? (small/ medium/ large/ off/ report))`.",
        next_thinking_step: question,
      }],
    },
  });
  open("/student/assignments/assignment-1");
  expect(await screen.findByRole("region", { name: "Your next thinking step" })).toHaveTextContent(question);
  expect(screen.getByText(/Include small, medium, large, off, and report/)).toBeInTheDocument();
});

test("older reply without a question keeps the prior prompt visible after reload", async () => {
  const question = "What exact prompt should show all five choices?";
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      engine_state: { socratic: { phase: "teaching", next_thinking_step: "" } },
      messages: [
        { role: "assistant", content: question },
        { role: "user", content: "Please choose the option" },
        { role: "assistant", content: "Include all five choices. For example, `print(What would you like? (small/ medium/ large/ off/ report))`." },
      ],
    },
  });
  open("/student/assignments/assignment-1");
  const cards = await screen.findAllByText("Socratic tutor");
  const latestCard = cards[1].closest(".socratic-message-card");
  expect(within(latestCard).getByRole("region", { name: "Your next thinking step" })).toHaveTextContent(question);
});

test("paused acknowledgement shows no next-thinking-step box", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      engine_state: { socratic: {
        phase: "teaching", conversation_status: "paused",
        next_thinking_step: "How would you apply this to the assignment?",
      } },
      messages: [
        { role: "assistant", content: "What are the five choices?" },
        { role: "user", content: "ok" },
        { role: "assistant", content: "Take your time. I'm here when you're ready.",
          next_thinking_step: "How would you apply this to the assignment?" },
      ],
    },
  });
  open("/student/assignments/assignment-1");
  const cards = await screen.findAllByText("Socratic tutor");
  const latestCard = cards[1].closest(".socratic-message-card");
  expect(within(latestCard).queryByRole("region", { name: "Your next thinking step" })).not.toBeInTheDocument();
  expect(latestCard).toHaveTextContent("Take your time. I'm here when you're ready.");
});

test("dashboard link shows the student's finished and remaining assignments", async () => {
  mockApi("student", {
    "/api/platform/assignments": [
      { ...assignment, progress: "in_progress" },
      { ...assignment, id: "finished-1", title: "Completed discussion", progress: "completed" },
    ],
    "/api/platform/assignments/assignment-1/attempt": attempt,
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("link", { name: "Dashboard", exact: true }));

  const left = await screen.findByRole("region", { name: /^Left to do/ });
  const finished = screen.getByRole("region", { name: /^Finished/ });
  expect(within(left).getByText("Discuss requirements")).toBeInTheDocument();
  expect(within(left).getByText("In progress")).toBeInTheDocument();
  expect(within(left).getByRole("link", { name: "Resume" })).toBeInTheDocument();
  expect(within(finished).getByText("Completed discussion")).toBeInTheDocument();
  expect(within(finished).getByText("Completed")).toBeInTheDocument();
  expect(within(finished).getByRole("link", { name: "View result" })).toBeInTheDocument();
});

test("student dashboard lists Canvas-linked activities across courses", async () => {
  const fetch = mockApi("student", {
    "/api/platform/assignments": [
      {
        ...assignment,
        id: "canvas-1",
        title: "Code review debate",
        tool: "debate",
        course_code: "ITCS 3155",
        course_title: "Software Engineering",
        canvas_linked: true,
      },
      {
        ...assignment,
        id: "canvas-2",
        title: "Logic reflection",
        tool: "reflections",
        course_code: "ITCS 3150",
        course_title: "Proposition Logic",
        canvas_linked: true,
      },
    ],
  });
  open("/student");

  expect(await screen.findByText("Code review debate")).toBeInTheDocument();
  expect(screen.getByText("Logic reflection")).toBeInTheDocument();
  expect(screen.getByText("Software Engineering (ITCS 3155) · Debate · Canvas")).toBeInTheDocument();
  expect(screen.getByText("Proposition Logic (ITCS 3150) · Reflections · Canvas")).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url === "/api/platform/assignments")).toBe(true);
  expect(fetch.mock.calls.some(([url]) => url.startsWith("/api/platform/assignments?course_id="))).toBe(false);
});

test("keyword-based Socratic assignments begin with an example and no starter choices", async () => {
  const newAttempt = {
    ...attempt,
    messages: [{ role: "assistant", content: "Let's begin with **code review**. For example, your course material describes this situation: ‘A reviewer checks a proposed change.’ What is happening here?" }],
    engine_state: {
      socratic: { objective_keywords: ["code review", "correctness"] },
    },
  };
  mockApi("student", {
    "/api/platform/assignments/assignment-1/start": newAttempt,
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Start assignment" }));
  expect(await screen.findByText(/A reviewer checks a proposed change/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Ways to begin")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Show me an example" })).not.toBeInTheDocument();
});

test("student follows a generated Socratic path one step at a time", async () => {
  const learning_steps = [
    { title: "Choose a size", goal: "Explain how you choose a sandwich size." },
    { title: "Check ingredients", goal: "Explain when the machine checks its ingredients.", scenario: "The customer chooses small, and the same machine checks its ingredients.", question: "What should it check before asking for coins?" },
  ];
  const started = { ...attempt, engine_state: { socratic: { learning_step_index: 0, step_started_at_message_count: 1, phase: "teaching" } } };
  const discussed = { ...started, messages: [...started.messages, { role: "user", content: "I choose small." }, { role: "assistant", content: "What will happen after choosing small?" }] };
  const advanced = { ...discussed, messages: [...discussed.messages, { role: "assistant", content: "Step 2: Check ingredients\n\nThe customer chooses small, and the same machine checks its ingredients.\n\nWhat should it check before asking for coins?" }], engine_state: { socratic: { learning_step_index: 1, step_started_at_message_count: 4, phase: "teaching", next_thinking_step: "What should it check before asking for coins?" } } };
  const fetch = mockApi("student", {
    "/api/platform/assignments/assignment-1": { ...assignment, student_config: { minimum_messages: 1, learning_steps } },
    "/api/platform/assignments/assignment-1/attempt": discussed,
    "POST /api/platform/assignments/assignment-1/next-step": advanced,
  });
  open("/student/assignments/assignment-1");
  expect(await screen.findByRole("heading", { name: "Your learning path" })).toBeInTheDocument();
  expect(document.querySelector(".assignment-info")).toHaveClass("socratic-assignment-info");
  expect(document.querySelector(".student-assignment-intro")).toBeInTheDocument();
  expect(document.querySelector(".student-course-materials")).toBeInTheDocument();
  expect(document.querySelector(".student-learning-path").compareDocumentPosition(document.querySelector(".student-course-materials")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText("2 steps")).toBeInTheDocument();
  expect(screen.getByText("0%")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Learning path steps" })).toHaveAttribute("tabindex", "0");
  expect(screen.getByText("Choose a size")).toBeInTheDocument();
  expect(screen.getByText("Check ingredients")).toBeInTheDocument();
  expect([...document.querySelectorAll(".student-learning-path .student-step-number")].map((badge) => badge.textContent)).toEqual(["1", "2"]);
  expect(screen.getByText("Choose a size").closest("li")).toHaveAttribute("aria-current", "step");
  expect(screen.getByText("Current step")).toBeInTheDocument();
  expect(screen.queryByRole("separator", { name: /Step 2 of 2/ })).not.toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Learning path progress" })).toHaveAttribute("aria-valuenow", "0");
  const nextStep = screen.getByRole("button", { name: "Continue to next step" });
  expect(nextStep).toHaveClass("next-learning-step");
  expect(nextStep).toBeEnabled();
  await userEvent.setup().click(nextStep);
  expect(await screen.findByText(/same machine checks its ingredients/)).toBeInTheDocument();
  expect(screen.getByRole("separator", { name: "Step 2 of 2: Check ingredients" })).toBeInTheDocument();
  expect(screen.getByRole("separator", { name: "Step 2 of 2: Check ingredients" })).toHaveClass("is-new-step");
  expect(document.querySelector(".socratic-step-divider + .socratic-message-card.assistant")).not.toHaveTextContent("Step 2: Check ingredients");
  expect(document.querySelector(".socratic-message-card.assistant.is-new-reply .message-avatar")).toHaveTextContent("S");
  expect(document.querySelectorAll(".socratic-message-card.assistant.is-current-reply")).toHaveLength(1);
  expect(within(screen.getByRole("list", { name: "Learning path steps" })).getByText("Check ingredients").closest("li")).toHaveAttribute("aria-current", "step");
  expect(screen.getByText("Choose a size").closest("li")).toHaveClass("is-completed");
  expect(within(screen.getByRole("list", { name: "Learning path steps" })).getByText("Check ingredients").closest("li")).toHaveClass("is-current");
  expect(within(screen.getByText("Choose a size").closest("li")).getByRole("img", { name: "Completed step" })).toHaveTextContent("✓");
  expect(within(within(screen.getByRole("list", { name: "Learning path steps" })).getByText("Check ingredients").closest("li")).queryByRole("img", { name: "Completed step" })).not.toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Learning path progress" })).toHaveAttribute("aria-valuenow", "1");
  expect(screen.getByText("50%")).toBeInTheDocument();
  expect(screen.getByText("1 of 2 steps complete · Stage 2 of 2")).toBeInTheDocument();
  expect(screen.getAllByRole("region", { name: "Your next thinking step" }).at(-1)).toHaveTextContent("What should it check before asking for coins?");
  expect(fetch.mock.calls.some(([url]) => url.endsWith("/next-step"))).toBe(true);
});

test("guided Socratic path hides legacy timer data without affecting step progression", async () => {
  const learning_steps = [
    { title: "Choose a size", goal: "Choose a size." },
    { title: "Check ingredients", goal: "Check ingredients." },
  ];
  const startedAt = new Date(Date.now() - 2 * 60 * 1000).toISOString();
  const started = {
    ...attempt,
    created_at: startedAt,
    messages: [...attempt.messages, { role: "user", content: "Small." }],
    engine_state: { socratic: { phase: "teaching", learning_step_index: 0, step_started_at_message_count: 1 } },
  };
  mockApi("student", {
    "/api/platform/assignments/assignment-1": { ...assignment, student_config: { minimum_messages: 1, learning_steps, learning_path_time_limit_seconds: 420 } },
    "/api/platform/assignments/assignment-1/attempt": started,
    "POST /api/platform/assignments/assignment-1/next-step": {
      ...started,
      engine_state: { socratic: { phase: "teaching", learning_step_index: 1, step_started_at_message_count: 2 } },
    },
  });
  open("/student/assignments/assignment-1");
  expect(await screen.findByRole("heading", { name: "Socratic Chat" })).toBeInTheDocument();
  expect(screen.queryByRole("timer", { name: "Total learning path time" })).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "Continue to next step" }));
  expect(within(screen.getByRole("list", { name: "Learning path steps" })).getByText("Check ingredients").closest("li")).toHaveAttribute("aria-current", "step");
  expect(screen.queryByRole("timer", { name: "Total learning path time" })).not.toBeInTheDocument();
});

test("legacy elapsed time does not block a student from finishing the guided path", async () => {
  const learning_steps = [{ title: "Choose a size", goal: "Choose a size." }];
  mockApi("student", {
    "/api/platform/assignments/assignment-1": { ...assignment, student_config: { minimum_messages: 1, learning_steps, learning_path_time_limit_seconds: 420 } },
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      created_at: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
      messages: [...attempt.messages, { role: "user", content: "Small." }],
      engine_state: { socratic: { phase: "teaching", learning_step_index: 0, step_started_at_message_count: 1 } },
    },
  });
  open("/student/assignments/assignment-1");
  expect(await screen.findByRole("heading", { name: "Socratic Chat" })).toBeInTheDocument();
  expect(screen.queryByRole("timer", { name: "Total learning path time" })).not.toBeInTheDocument();
  await userEvent.setup().type(screen.getByLabelText("Your message"), "Can we revisit this?");
  expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Finish conversation and summarize" })).toBeEnabled();
});

test("last guided step offers the summary action in the learning path", async () => {
  const learning_steps = [
    { title: "Choose a size", goal: "Choose a sandwich size." },
    { title: "Check ingredients", goal: "Check supplies before payment." },
  ];
  mockApi("student", {
    "/api/platform/assignments/assignment-1": { ...assignment, student_config: { minimum_messages: 1, learning_steps } },
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      messages: [
        { role: "assistant", content: "Which size?" },
        { role: "user", content: "Small." },
        { role: "assistant", content: "Step 2: Check ingredients. What should you check?" },
        { role: "user", content: "The bread and ham." },
      ],
      engine_state: { socratic: { phase: "teaching", learning_step_index: 1, step_started_at_message_count: 3 } },
    },
  });
  open("/student/assignments/assignment-1");
  const action = await screen.findByRole("button", { name: "Finish conversation and summarize" });
  expect(action).toHaveClass("next-learning-step");
  expect(action).toBeEnabled();
  expect(within(screen.getByText("Check ingredients").closest("li")).queryByRole("img", { name: "Completed step" })).not.toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Learning path progress" })).toHaveAttribute("aria-valuenow", "1");
  expect(screen.queryByRole("button", { name: "Continue to next step" })).not.toBeInTheDocument();
  await userEvent.setup().click(action);
  const summaryInput = screen.getByLabelText("Summarize what you learned in your own words");
  expect(summaryInput.closest("form")).toHaveClass("is-highlighted");
  expect(summaryInput).toHaveFocus();
  expect(screen.getByText("Final step complete · Summarize your learning")).toBeInTheDocument();
  expect(within(screen.getByText("Check ingredients").closest("li")).getByRole("img", { name: "Completed step" })).toHaveTextContent("✓");
  expect(screen.getByRole("progressbar", { name: "Learning path progress" })).toHaveAttribute("aria-valuenow", "2");
  expect(screen.getByText("2 of 2 steps complete")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Finish conversation and summarize" })).not.toBeInTheDocument();
});

test("student downloads the original selected material instead of opening extracted text", async () => {
  const documentId = "selected-pdf";
  const fetch = mockApi("student", {
    "/api/platform/assignments/assignment-1/materials": {
      materials: [
        { document_id: documentId, title: "Sandwich Maker.pdf", original_available: true, page_count: 2 },
        { document_id: "missing-file", title: "Starter code.py", original_available: false },
      ],
    },
    [`/api/platform/assignments/assignment-1/materials/${documentId}/download`]: new Blob(["%PDF-1.4"], { type: "application/pdf" }),
  });
  const createObjectURL = vi.fn(() => "blob:course-material");
  const revokeObjectURL = vi.fn();
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;
  URL.createObjectURL = createObjectURL;
  URL.revokeObjectURL = revokeObjectURL;
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  open("/student/assignments/assignment-1");
  expect(await screen.findByRole("heading", { name: "Course materials" })).toBeInTheDocument();
  const availableRow = (await screen.findByText("Sandwich Maker.pdf")).closest("li");
  expect(within(availableRow).getByRole("button", { name: "View Sandwich Maker.pdf" })).toHaveTextContent("View");
  expect(within(availableRow).getByRole("button", { name: "Download Sandwich Maker.pdf" })).toHaveTextContent("Download");
  expect(within(availableRow).getByRole("button", { name: "Download Sandwich Maker.pdf" })).not.toHaveClass("secondary");
  const unavailableRow = screen.getByText("Starter code.py").closest("li");
  expect(within(unavailableRow).getByText("Original file unavailable")).toBeInTheDocument();
  expect(within(unavailableRow).queryByRole("button")).not.toBeInTheDocument();
  await userEvent.setup().click(await screen.findByRole("button", { name: "Download Sandwich Maker.pdf" }));
  await waitFor(() => expect(createObjectURL).toHaveBeenCalled());
  expect(click).toHaveBeenCalledOnce();
  expect(fetch.mock.calls.some(([url]) => url.endsWith(`/materials/${documentId}/download`))).toBe(true);
  expect(screen.queryByRole("dialog", { name: /Course material/ })).not.toBeInTheDocument();
  click.mockRestore();
  URL.createObjectURL = originalCreateObjectURL;
  URL.revokeObjectURL = originalRevokeObjectURL;
});

test("student opens the original PDF beside the chat and can return to the learning path", async () => {
  const documentId = "selected-pdf";
  mockApi("student", {
    "/api/platform/assignments/assignment-1/materials": { materials: [
      { document_id: documentId, title: "Sandwich Maker.pdf", original_available: true, page_count: 2 },
    ] },
    [`/api/platform/assignments/assignment-1/materials/${documentId}/download`]:
      new Blob(["%PDF-1.4"], { type: "application/pdf" }),
  });
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;
  URL.createObjectURL = vi.fn(() => "blob:original-course-pdf");
  URL.revokeObjectURL = vi.fn();
  try {
    open("/student/assignments/assignment-1");
    await userEvent.setup().click(await screen.findByRole("button", { name: "View Sandwich Maker.pdf" }));
    const preview = await screen.findByRole("complementary", { name: "Course material preview: Sandwich Maker.pdf" });
    expect(within(preview).getByTitle("Sandwich Maker.pdf")).toHaveAttribute("src", "blob:original-course-pdf");
    expect(within(preview).getByRole("button", { name: "Download" })).toBeInTheDocument();
    expect(document.querySelector(".workspace-grid")).toHaveClass("material-preview-open");
    await userEvent.setup().click(within(preview).getByRole("button", { name: "Close document" }));
    expect(screen.queryByRole("complementary", { name: /Course material preview/ })).not.toBeInTheDocument();
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:original-course-pdf"));
    expect(screen.getByRole("heading", { name: "Course materials" })).toBeInTheDocument();
  } finally {
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
  }
});

test("student sees a download-only message for Office materials", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/materials": { materials: [
      { document_id: "slides", title: "Lecture.pptx", original_available: true },
    ] },
    "/api/platform/assignments/assignment-1/materials/slides/download":
      new Blob(["office document"], { type: "application/vnd.openxmlformats-officedocument.presentationml.presentation" }),
  });
  open("/student/assignments/assignment-1");
  await userEvent.setup().click(await screen.findByRole("button", { name: "View Lecture.pptx" }));
  const preview = await screen.findByRole("complementary", { name: "Course material preview: Lecture.pptx" });
  expect(within(preview).getByText(/cannot be displayed in the browser/)).toBeInTheDocument();
  expect(within(preview).getByRole("button", { name: "Download" })).toBeInTheDocument();
});

test("Debate shows the instructor scenario once when the student starts", async () => {
  const scenario = "Should teams require code review before merging a change?";
  mockApi("student", {
    "/api/platform/assignments/assignment-1": {
      ...assignment,
      tool: "debate",
      title: "Code review debate",
      instructions: "Defend your position with a reason.",
      student_config: { scenario, minimum_messages: 3 },
    },
    "/api/platform/assignments/assignment-1/start": {
      ...attempt,
      messages: [{ role: "assistant", content: scenario }],
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();

  expect(await screen.findAllByText(scenario)).toHaveLength(1);
  await user.click(screen.getByRole("button", { name: "Start assignment" }));
  await waitFor(() => expect(screen.getAllByText(scenario)).toHaveLength(1));
  expect(screen.getByLabelText("Your message")).toBeInTheDocument();
});

test("Canvas student landing shows assignments without course selection or enrollment controls", async () => {
  mockApi("student");
  open("/student");
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your assignments" }),
  ).toBeInTheDocument();
  expect(
    (await screen.findAllByRole("link", { name: "Open assignment" }))[0],
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("combobox", { name: "Filter by course" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Request access" }),
  ).not.toBeInTheDocument();
});

test("failed publish retains a saved draft and shows an actionable error", async () => {
  const saved = {
    ...assignment,
    status: "draft",
    audience: "course",
    recipient_ids: [],
    config: { document_ids: ["doc1"], prompt: "", minimum_messages: 1 },
  };
  const fetch = mockApi("instructor", {
    "POST /api/platform/assignments": saved,
    "/api/platform/assignments/assignment-1": saved,
    [`/api/platform/courses/${course}/documents`]: {
      files: [
        { file_id: "f1", document_id: "doc1", filename: "Requirements.txt" },
      ],
    },
    [`/api/courses/${course}/documents`]: {
      files: [
        { file_id: "f1", document_id: "doc1", filename: "Requirements.txt" },
      ],
    },
    [`/api/courses/${course}/learning-objectives`]: { objectives: [] },
    "/api/platform/assignments/assignment-1/publish": {
      error: "Upload course materials first.",
    },
  });
  open("/professor/activities/new");
  const user = userEvent.setup();
  await user.type(
    await screen.findByLabelText("Assignment title"),
    "Discuss requirements",
  );
  await user.click(
    await screen.findByRole("checkbox", { name: /Requirements.txt/ }),
  );
  await user.click(screen.getByRole("button", { name: /Socratic Chat/ }));
  await user.click(
    screen.getByRole("button", { name: "Review activity", exact: true }),
  );
  await user.click(
    screen.getByRole("button", { name: "Publish activity", exact: true }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Upload course materials first.",
  );
  expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled();
  expect(
    fetch.mock.calls.filter(
      ([url, opt]) =>
        url === "/api/platform/assignments" && opt.method === "POST",
    ),
  ).toHaveLength(1);
});

test("retrying a failed student message reuses its idempotency key", async () => {
  let count = 0;
  const fetch = mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": attempt,
    "/api/platform/assignments/assignment-1/messages": () =>
      ++count === 1
        ? { error: "Engine unavailable. Retry shortly." }
        : {
            ...attempt,
            messages: [
              ...attempt.messages,
              { role: "user", content: "My answer" },
              { role: "assistant", content: "Good example" },
            ],
          },
  });

  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Expand chat" }));
  expect(document.body).toHaveClass("socratic-workspace-open");
  expect(document.querySelector(".workspace-grid")).toHaveClass("socratic-workspace");
  expect(document.querySelector(".workspace-grid")).toHaveClass(
    "chat-expanded",
  );
  await user.click(screen.getByRole("button", { name: "Show assignment" }));
  expect(document.querySelector(".workspace-grid")).not.toHaveClass(
    "chat-expanded",
  );
  await user.type(await screen.findByLabelText("Your message"), "My answer");
  await user.click(screen.getByRole("button", { name: "Send message" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Engine unavailable",
  );
  expect(screen.getByLabelText("Your message")).toHaveValue("My answer");
  expect(
    document.querySelector(".socratic-message-card.user.is-pending"),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Send message" }));
  expect(await screen.findAllByText("Good example")).not.toHaveLength(0);
  const requests = fetch.mock.calls
    .filter(([url]) => url.endsWith("/messages"))
    .map(([, opts]) => JSON.parse(opts.body));
  expect(requests[0].request_id).toBe(requests[1].request_id);
});

test("Socratic response shows a generation timer, thinking step, and clickable evidence", async () => {
  let resolveMessage;
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": attempt,
    "/api/platform/assignments/assignment-1/messages": () =>
      new Promise((resolve) => {
        resolveMessage = resolve;
      }),
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Your message"), "My answer");
  await user.click(screen.getByRole("button", { name: "Send message" }));

  expect(screen.getByLabelText("Your message")).toHaveValue("");
  expect(
    document.querySelector(".socratic-message-card.user.is-pending"),
  ).toHaveTextContent("My answer");
  expect(await screen.findByRole("status")).toHaveAccessibleName(
    "Socratic tutor is thinking through your response",
  );
  expect(
    screen.getByText("Thinking through your response"),
  ).toBeInTheDocument();
  expect(screen.getByText(/^\d+s elapsed$/)).toBeInTheDocument();
  await act(async () => {
    resolveMessage({
      ...attempt,
      engine_state: {
        socratic: {
          active_concept: "version control",
          keywords: ["version control"],
          last_score: 76,
          next_thinking_step:
            "How does version control help two developers collaborate?",
        },
        sources: [
          {
            document_id: "doc",
            chunk_id: "chunk-2",
            title: "Version Control Notes",
            text: "Version control preserves revision history for a team.",
            page_number: 2,
          },
        ],
      },
      messages: [
        ...attempt.messages,
        { role: "user", content: "My answer" },
        {
          role: "assistant",
          content:
            "That identifies revision history. How does version control help two developers collaborate?",
        },
      ],
    });
  });

  expect(
    (await screen.findAllByText("Your next thinking step")).length,
  ).toBeGreaterThan(0);
  expect(
    screen.getByText("version control", { selector: "strong" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/^Generated in \d+s$/)).toBeInTheDocument();
  expect(document.querySelector(".socratic-message-card.assistant.is-new-reply")).toHaveTextContent(
    "How does version control help two developers collaborate?",
  );
  expect(document.querySelectorAll(".socratic-message-card.assistant.is-current-reply")).toHaveLength(1);
  expect(document.querySelector(".socratic-message-card.assistant.is-current-reply")).toHaveTextContent(
    "How does version control help two developers collaborate?",
  );
  expect(screen.queryByText("New reply")).not.toBeInTheDocument();
  expect(screen.queryByText(/Score 76\/100/)).not.toBeInTheDocument();
  expect(
    document.querySelector(".socratic-message-card.user.is-pending"),
  ).not.toBeInTheDocument();
  expect(within(document.querySelector(".messages")).getAllByText("My answer")).toHaveLength(1);
  expect(screen.queryByText("Why am I being asked this?")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "View passage" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "View supporting sources" }));
  expect(screen.getByRole("region", { name: "Visible course source" })).toHaveTextContent("Version control preserves revision history for a team.");
  await user.click(screen.getByRole("button", { name: "View passage" }));
  const drawer = screen.getByRole("dialog", {
    name: "Evidence document: Version Control Notes",
  });
  expect(drawer).toBeInTheDocument();
  expect(within(drawer).getByRole("region", { name: "Structured source evidence" })).toHaveTextContent("Version control preserves revision history for a team.");
  expect(within(drawer).queryByText("Original selected passage")).not.toBeInTheDocument();
  expect(document.querySelector(".workspace-grid")).toHaveClass(
    "evidence-open",
  );
  expect(document.body).toHaveClass("evidence-workspace-open");
  const resizer = screen.getByRole("separator", {
    name: "Resize evidence document",
  });
  expect(resizer).toHaveAttribute("aria-valuenow", "420");
  resizer.focus();
  await user.keyboard("{ArrowLeft}");
  expect(resizer).toHaveAttribute("aria-valuenow", "444");
  expect(
    within(drawer).getByText(/preserves revision history for a team/),
  ).toBeInTheDocument();
  expect(screen.getByText("Page 2")).toBeInTheDocument();
  expect(screen.getByText("Passage chunk-2")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Make visual steps" }));
  expect(await screen.findByRole("region", { name: "Visual steps from this passage" })).toBeInTheDocument();
  expect(screen.getByText("Step 1")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Regenerate visual steps" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Show original text" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Close passage" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(document.querySelector(".workspace-grid")).not.toHaveClass(
    "evidence-open",
  );
  expect(document.body).not.toHaveClass("evidence-workspace-open");
  await user.click(screen.getByRole("button", { name: "View passage" }));
  await user.click(
    screen.getByRole("button", { name: "Close evidence document" }),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "I’m not sure yet" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Draft an example answer" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Could you guide me?" })).not.toBeInTheDocument();
});

test("Socratic chat shows a relevant table excerpt but keeps other sources tucked away", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      engine_state: {
        sources: [{
          document_id: "doc",
          chunk_id: "table-1",
          title: "Sandwich requirements",
          page_number: 3,
          text: "Table 1: Sandwich sizes\nSize | Bread\nSmall | 2\nMedium | 4",
        }],
      },
      messages: [{
        role: "assistant",
        content: "Use the table in your course material. How much bread does a small sandwich need?",
      }],
    },
  });

  open("/student/assignments/assignment-1");
  expect(await screen.findByRole("region", { name: "Relevant source excerpt" })).toBeInTheDocument();
  expect(document.querySelectorAll(".socratic-message-card.assistant.is-current-reply")).toHaveLength(1);
  expect(document.querySelector(".socratic-message-card.assistant.is-current-reply .message-avatar")).toHaveTextContent("S");
  const excerpt = await screen.findByRole("region", { name: "Relevant source excerpt" });
  expect(within(excerpt).getByRole("row", { name: "Small 2" })).toBeInTheDocument();
  expect(screen.queryByText("Original selected passage")).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "View supporting sources" }));
  expect(screen.getByRole("region", { name: "Visible course source" })).toHaveTextContent("Sandwich requirements · page 3");
  expect(screen.getByRole("button", { name: "View passage" })).toBeInTheDocument();
});

test("console-style source evidence opens as choices and outcomes instead of a raw script", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      engine_state: { sources: [{
        document_id: "doc", chunk_id: "script-1", title: "Machine example", page_number: 3,
        text: "Bread: 6 slices What would you like? (small/ medium/ off): small Please insert coins. how many large dollars?: 1 how many quarters?: 2 Sorry, that's not enough money. Money refunded. What would you like? (small/ medium/ off): report Bread: 6 slices Ham: 8 slices",
      }] },
      messages: [{ role: "assistant", content: "What does the example show about payment?" }],
    },
  });
  open("/student/assignments/assignment-1");
  await userEvent.setup().click(await screen.findByRole("button", { name: "View supporting sources" }));
  const inlineTable = within(screen.getByRole("region", { name: "Visible course source" })).getByRole("table");
  expect(within(inlineTable).getByRole("row", { name: /1 small large dollars: 1 · quarters: 2 Sorry, that's not enough money/ })).toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "View passage" }));
  const drawer = screen.getByRole("dialog", { name: "Evidence document: Machine example" });
  const table = within(drawer).getByRole("table");
  expect(within(table).getByRole("row", { name: /1 small large dollars: 1 · quarters: 2 Sorry, that's not enough money/ })).toBeInTheDocument();
  expect(within(table).getByRole("row", { name: /2 report — Bread: 6 slices Ham: 8 slices/ })).toBeInTheDocument();
  expect(within(drawer).queryByText("Original selected passage")).not.toBeInTheDocument();
  expect(within(drawer).queryByRole("button", { name: "Show original text" })).not.toBeInTheDocument();
});

test("Socratic money question provides a table without solving the exercise", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      messages: [{
        role: "assistant",
        content: "If you insert three large dollars and two half dollars for a small sandwich that costs $1.75, how much total money did you insert, and what is the correct change message?",
      }, { role: "user", content: "I need to add them." }, { role: "assistant", content: "Yes, add them together." }],
    },
  });

  open("/student/assignments/assignment-1");
  const breakdown = await screen.findByRole("region", { name: "Money breakdown" });
  expect(within(breakdown).getByRole("row", { name: /Large dollar 3 \$1\.00 \?/ })).toBeInTheDocument();
  expect(within(breakdown).getByRole("row", { name: /Half dollar 2 \$0\.50 \?/ })).toBeInTheDocument();
  expect(within(breakdown).getByRole("row", { name: /Sandwich price \$1\.75/ })).toBeInTheDocument();
  expect(within(breakdown).getByRole("row", { name: /Change \?/ })).toBeInTheDocument();
  expect(within(breakdown).queryByText("$2.25")).not.toBeInTheDocument();
});

test("Socratic scope confirmation offers choices before generating an explanation", async () => {
  let replyCount = 0;
  const fetch = mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": attempt,
    "/api/platform/assignments/assignment-1/messages": () => {
      replyCount += 1;
      const reply = replyCount === 1
        ? "Do you mean 'prompt' in this assignment, or would a general explanation help?"
        : "A prompt is a question asking the user for input.";
      return {
        ...attempt,
        engine_state: {
          socratic: {
            ...(replyCount === 1 ? { pending_clarification: { inline: true, question: reply } } : {}),
            clarification_options: replyCount === 1 ? [
              { label: "In this assignment", message_role: "direct_answer_request", resolved_message: "Explain it directly in this assignment." },
              { label: "Generally, another example", message_role: "direct_answer_request", resolved_message: "Explain it directly with another example." },
            ] : [],
          },
        },
        messages: [
          ...attempt.messages,
          { role: "user", content: "what is the prompt?" },
          ...(replyCount === 1 ? [] : [{ role: "assistant", content: reply }]),
        ],
      };
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Your message"), "what is the prompt?");
  await user.click(screen.getByRole("button", { name: "Send message" }));
  expect(await screen.findByRole("group", { name: "Clarify your intent" })).toBeInTheDocument();
  expect(screen.getByText("Quick check before I answer")).toBeInTheDocument();
  expect(screen.getByText("Do you mean 'prompt' in this assignment, or would a general explanation help?")).toBeInTheDocument();
  expect(screen.getByText("what is the prompt?")).toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "Generally, another example" }));
  const requests = fetch.mock.calls
    .filter(([url]) => url.endsWith("/messages"))
    .map(([, options]) => JSON.parse(options.body));
  expect(requests).toHaveLength(2);
  expect(requests[1].clarification_index).toBe(1);
  expect(await screen.findByText("A prompt is a question asking the user for input.")).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Clarify your intent" })).not.toBeInTheDocument();
});

test("Socratic clarification accepts typed intent before the tutor answers", async () => {
  let replyCount = 0;
  const fetch = mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": attempt,
    "/api/platform/assignments/assignment-1/messages": () => {
      replyCount += 1;
      return {
        ...attempt,
        engine_state: { socratic: replyCount === 1 ? {
          pending_clarification: { inline: true, question: "Would a hint help, or did you mean something else?" },
          clarification_options: [{ label: "Give me a hint", message_role: "support_request", resolved_message: "Please give me a hint." }],
        } : { clarification_options: [] } },
        messages: [...attempt.messages, { role: "user", content: "ok" },
          ...(replyCount === 1 ? [] : [
            { role: "user", content: "I meant I need help with the question." },
            { role: "assistant", content: "Let's break the question down." },
          ])],
      };
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Your message"), "ok");
  await user.click(screen.getByRole("button", { name: "Send message" }));
  expect(await screen.findByRole("group", { name: "Clarify your intent" })).toBeInTheDocument();
  expect(screen.queryByText("Let's break the question down.")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Your message")).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Type your answer or tell me what you meant"), "I meant I need help with the question.");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  const requests = fetch.mock.calls.filter(([url]) => url.endsWith("/messages"))
    .map(([, options]) => JSON.parse(options.body));
  expect(requests[1]).toMatchObject({ message: "I meant I need help with the question.", clarification_text: true });
  expect(await screen.findByText("Let's break the question down.")).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Clarify your intent" })).not.toBeInTheDocument();
});

test("Socratic students choose when to summarize without seeing old scores", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      engine_state: { socratic: { phase: "teaching", last_score: 19 } },
      messages: [
        ...attempt.messages,
        { role: "user", content: "It probably adds my order to the list", total_score: 19 },
        { role: "assistant", content: "It checks resources first. What happens if bread runs out?", total_score: 19 },
      ],
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  expect(await screen.findByRole("button", { name: "Finish conversation and summarize" })).toBeInTheDocument();
  expect(screen.queryByText(/Score 19\/100/)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Finish conversation and summarize" }));
  expect(screen.getByLabelText("Summarize what you learned in your own words")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Keep chatting" }));
  expect(screen.getByLabelText("Your message")).toBeInTheDocument();
});

test("final feedback shows the centered active loading display until evaluation returns", async () => {
  let resolveFeedback;
  const feedbackPending = new Promise((resolve) => { resolveFeedback = resolve; });
  const inProgress = {
    ...attempt,
    engine_state: { socratic: { phase: "teaching" } },
    messages: [...attempt.messages, { role: "user", content: "Check ingredients first." }],
  };
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": inProgress,
    "POST /api/platform/assignments/assignment-1/reflection": () => feedbackPending,
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Finish conversation and summarize" }));
  await user.type(screen.getByLabelText("Summarize what you learned in your own words"), "Check the ingredients before asking for money.");
  await user.click(screen.getByRole("button", { name: "Get final feedback" }));
  expect(await screen.findByRole("status", { name: "BrainTutor is preparing final feedback" })).toHaveClass("generation-overlay");
  expect(screen.queryByLabelText("Socratic tutor is thinking through your response")).not.toBeInTheDocument();
  resolveFeedback(inProgress);
  await waitFor(() => expect(screen.queryByRole("status", { name: "BrainTutor is preparing final feedback" })).not.toBeInTheDocument());
});

test("final feedback highlights evidenced misunderstandings and enables the green submit button", async () => {
  const readyAttempt = {
    ...attempt,
    engine_state: {
      socratic: {
        phase: "ready_to_submit",
        completion_summary: {
          original_question: "How does code review help?",
          student_reflection: "Review guarantees no bugs.",
          demonstrated: [],
          final_comment: "You identified that a teammate checks a change.",
          misconception_correction: "Review cannot guarantee no bugs.",
          concepts_to_revisit: [{
            student_quote: "Review guarantees no bugs.",
            correction: "Review can catch problems, but it cannot guarantee a change has no bugs.",
            source_title: "Code review guide",
          }],
          scenario_wrap_up: "A teammate checks the change before merging.",
          opening_answer: "Code review helps a team inspect changes.",
        },
      },
    },
  };
  mockApi("student", { "/api/platform/assignments/assignment-1/attempt": readyAttempt });
  open("/student/assignments/assignment-1");

  const revisit = await screen.findByRole("region", { name: "Concepts to revisit" });
  expect(within(revisit).getByText("Review guarantees no bugs.").closest("mark")).toBeInTheDocument();
  expect(within(revisit).getByText("Course source: Code review guide")).toBeInTheDocument();
  expect(within(revisit).getByText(/cannot guarantee a change has no bugs/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Submit assignment" })).toHaveClass("submit-assignment-ready");
});

test("submitted assignments show the vivid green completed state", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": {
      ...attempt,
      status: "completed",
      result: {},
    },
  });
  open("/student/assignments/assignment-1");

  expect(await screen.findByRole("heading", { name: "Assignment complete" })).toHaveClass("result-complete-title");
  expect(screen.getByText("Completed")).toHaveClass("badge", "completed");
});

test("Enter sends a student message and Shift Enter inserts a new line", async () => {
  const fetch = mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": attempt,
    "/api/platform/assignments/assignment-1/messages": {
      ...attempt,
      messages: [
        ...attempt.messages,
        { role: "user", content: "First line\nSecond line" },
        { role: "assistant", content: "What evidence supports that?" },
      ],
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  const input = await screen.findByLabelText("Your message");

  await user.type(input, "First line{Shift>}{Enter}{/Shift}Second line");
  expect(input).toHaveValue("First line\nSecond line");
  expect(
    fetch.mock.calls.filter(([url]) => url.endsWith("/messages")),
  ).toHaveLength(0);

  await user.type(input, "{Enter}");
  expect(
    await screen.findAllByText("What evidence supports that?"),
  ).not.toHaveLength(0);
  const requests = fetch.mock.calls.filter(([url]) =>
    url.endsWith("/messages"),
  );
  expect(requests).toHaveLength(1);
  expect(JSON.parse(requests[0][1].body).message).toBe(
    "First line\nSecond line",
  );
});

test("student returns to the message box after the tutor replies", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": attempt,
    "/api/platform/assignments/assignment-1/messages": {
      ...attempt,
      messages: [
        ...attempt.messages,
        { role: "user", content: "My answer" },
        { role: "assistant", content: "What would you try next?" },
      ],
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  const input = await screen.findByLabelText("Your message");

  await user.type(input, "My answer");
  await user.click(screen.getByRole("button", { name: "Send message" }));

  expect(await screen.findByText("What would you try next?")).toBeInTheDocument();
  await waitFor(() => expect(input).toHaveFocus());
  expect(input).toHaveValue("");
  expect(input.scrollIntoView).toHaveBeenCalled();
});

test("concept check selection records understanding without sending a tutor message", async () => {
  const check = {
    id: "after-3-answers",
    question: 'Which situation best demonstrates "code review"?',
    hint: "Look for a concrete review decision.",
    options: [
      { id: "option-1", text: "A teammate reviews a change before merging." },
      { id: "option-2", text: "A teammate memorizes the term." },
    ],
  };
  const quizAttempt = {
    ...attempt,
    engine_state: { socratic: { concept_check: check } },
  };
  const fetch = mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": quizAttempt,
    "POST /api/platform/assignments/assignment-1/messages": {
      ...quizAttempt,
      engine_state: {
        socratic: {
          concept_check_completed: true,
          concept_check_response: {
            correct: true,
            selected_option: check.options[0],
            correct_option: check.options[0],
          },
        },
      },
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("radio", { name: check.options[0].text }));

  expect(await screen.findByText("Correct—this example applies the concept.")).toBeInTheDocument();
  expect(screen.queryByText("Why did you choose this option?")).not.toBeInTheDocument();
  expect(document.querySelectorAll(".socratic-message-card.user")).toHaveLength(0);
  const requests = fetch.mock.calls.filter(([url]) => url.endsWith("/messages"));
  expect(requests).toHaveLength(1);
  expect(JSON.parse(requests[0][1].body).concept_check_option).toBe(0);
});

test("earlier tutor questions keep their question-card design after a new reply", async () => {
  mockApi("student", {
    "/api/platform/assignments/assignment-1/attempt": attempt,
    "POST /api/platform/assignments/assignment-1/messages": {
      ...attempt,
      messages: [
        ...attempt.messages,
        { role: "user", content: "A requirement should be clear." },
        {
          role: "assistant",
          content: "That helps the team. What else makes it useful?",
        },
      ],
    },
  });
  open("/student/assignments/assignment-1");
  const user = userEvent.setup();
  const input = await screen.findByLabelText("Your message");

  expect(screen.getAllByRole("region", { name: "Your next thinking step" })).toHaveLength(1);
  await user.type(input, "A requirement should be clear.");
  await user.click(screen.getByRole("button", { name: "Send message" }));

  await waitFor(() => {
    const questions = screen.getAllByRole("region", { name: "Your next thinking step" });
    expect(questions).toHaveLength(2);
    expect(questions[0]).toHaveTextContent("What makes a requirement useful?");
    expect(questions[1]).toHaveTextContent("What else makes it useful?");
  });
});

test("student cannot enter professor configuration routes", async () => {
  mockApi("student");
  open("/professor/tools/reflections");
  expect(
    await screen.findByRole("heading", { name: "Your assignments" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "New assignment" }),
  ).not.toBeInTheDocument();
});

test("Reflections launches its student interface in a new tab without starting inline", async () => {
  const tab = { opener: {}, location: { replace: vi.fn() }, close: vi.fn() };
  vi.spyOn(window, "open").mockReturnValue(tab);
  const fetch = mockApi("student", {
    "/api/platform/assignments/assignment-1": {
      ...assignment,
      tool: "reflections",
      student_config: { module_type: "topic_based" },
    },
    "/api/platform/assignments/assignment-1/reflection-launch": {
      code: "launch-code",
    },
  });
  open("/student/assignments/assignment-1");
  const link = await screen.findByRole("link", { name: "Start assignment" });
  expect(link).toHaveAttribute(
    "href",
    "/platform/reflections.html?assignment=assignment-1",
  );
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  await userEvent.setup().click(link);
  await waitFor(() =>
    expect(tab.location.replace).toHaveBeenCalledWith(
      "/platform/reflections.html?assignment=assignment-1#code=launch-code",
    ),
  );
  expect(tab.opener).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url.endsWith("/start"))).toBe(false);
});

test("professor catalog loads all courses without requiring Canvas context", async () => {
  const fetch = mockApi("instructor", {
    "/api/platform/context": { error: "No Canvas course context" },
    "/api/platform/assignments": [
      { ...assignment, can_manage: true },
      { ...assignment, id: "other-course-activity", course_code: "CS202", title: "Another instructor's activity", can_manage: false },
    ],
  });
  open("/professor");
  expect(await screen.findByText("Another instructor's activity")).toBeInTheDocument();
  expect(screen.getByText("Course instructor access required to open")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Another instructor's activity" })).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url === "/api/platform/assignments")).toBe(true);
  expect(fetch.mock.calls.some(([url]) => url.startsWith("/api/platform/assignments?"))).toBe(false);
});
