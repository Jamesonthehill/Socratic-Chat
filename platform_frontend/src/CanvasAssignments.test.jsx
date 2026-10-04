import React from "react";
import { expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CanvasAssignments from "./CanvasAssignments";
import { SESSION_KEY } from "./api";

const course = {
  course_id: "8b71218d-71f3-436e-a4a6-1b279c4fda79",
  canvas_course_id: "77",
  title: "Software Engineering",
};

function mockApi(assignments) {
  localStorage.setItem(
    SESSION_KEY,
    JSON.stringify({ access_token: "test-session" }),
  );
  const draft = { id: "draft-1", status: "draft", title: "First essay" };
  const fetch = vi.fn(async (url, options = {}) => {
    if (url.endsWith("/integrations/canvas/assignments")) {
      const result =
        typeof assignments === "function" ? assignments() : assignments;
      return {
        ok: !result?.error,
        status: result?.error ? 502 : 200,
        json: async () => (result?.error ? { detail: result.error } : result),
      };
    }
    if (url.endsWith("/integrations/canvas/import")) {
      return { ok: true, status: 201, json: async () => draft };
    }
    throw new Error(`Unexpected API call: ${url}`);
  });
  vi.stubGlobal("fetch", fetch);
  return { fetch, draft };
}

test("loads only when opened and creates a draft with the selected chatbot", async () => {
  const { fetch, draft } = mockApi([
    {
      id: "88",
      name: "First essay",
      description: "Write a short essay.",
      due_at: null,
    },
    {
      id: "89",
      name: "Second essay",
      description: "Revise your essay.",
      due_at: null,
    },
  ]);
  const onImported = vi.fn();
  const user = userEvent.setup();
  render(<CanvasAssignments course={course} onImported={onImported} />);

  expect(fetch).not.toHaveBeenCalled();
  await user.click(screen.getByText("Choose a Canvas assignment"));
  expect(await screen.findByText("2 available")).toBeInTheDocument();
  expect(screen.getByText("First essay")).toBeInTheDocument();
  expect(screen.getByText("Second essay")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ course_id: "77" });

  await user.click(screen.getByText("Choose a Canvas assignment"));
  await user.click(screen.getByText("Choose a Canvas assignment"));
  expect(fetch).toHaveBeenCalledTimes(1);
  await user.selectOptions(screen.getByLabelText("Chatbot"), "reflections");
  await user.type(screen.getByLabelText("Find an assignment"), "First");
  expect(screen.queryByText("Second essay")).not.toBeInTheDocument();
  await user.click(
    screen.getByRole("button", {
      name: "Create Reflections draft for First essay",
    }),
  );

  await waitFor(() => expect(onImported).toHaveBeenCalledWith(draft));
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    course_id: "77",
    assignment_id: "88",
    platform_course_id: course.course_id,
    tool: "reflections",
  });
  expect(
    screen.getByRole("button", {
      name: "Create Reflections draft for First essay",
    }),
  ).toBeDisabled();
  expect(screen.getByText(/Draft created for First essay/)).toBeInTheDocument();
});

test("shows a load error, retries, and explains an empty Canvas course", async () => {
  let attempts = 0;
  const { fetch } = mockApi(() =>
    ++attempts === 1 ? { error: "Canvas is temporarily unavailable." } : [],
  );
  const user = userEvent.setup();
  render(<CanvasAssignments course={course} onImported={vi.fn()} />);

  await user.click(screen.getByText("Choose a Canvas assignment"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Canvas is temporarily unavailable.",
  );
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByText(
      "There are no assignments in this Canvas course yet.",
    ),
  ).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});
