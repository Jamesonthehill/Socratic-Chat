import React from "react";
import { expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CanvasCourseLink from "./CanvasCourseLink";
import { SESSION_KEY } from "./api";

const course = {
  course_id: "8b71218d-71f3-436e-a4a6-1b279c4fda79",
  title: "Software Engineering",
};

function mockApi(courses) {
  localStorage.setItem(
    SESSION_KEY,
    JSON.stringify({ access_token: "test-session" }),
  );
  const linked = { ...course, canvas_course_id: "77" };
  const fetch = vi.fn(async (url) => {
    if (url.endsWith("/integrations/canvas/courses")) {
      const result = typeof courses === "function" ? courses() : courses;
      return {
        ok: !result?.error,
        status: result?.error ? 422 : 200,
        json: async () => (result?.error ? { detail: result.error } : result),
      };
    }
    if (url.endsWith("/integrations/canvas/link-course")) {
      return { ok: true, status: 200, json: async () => linked };
    }
    throw new Error(`Unexpected API call: ${url}`);
  });
  vi.stubGlobal("fetch", fetch);
  return { fetch, linked };
}

test("loads Canvas courses only when opened and links only the professor's explicit choice", async () => {
  const { fetch, linked } = mockApi([
    {
      id: "77",
      name: "Software Engineering",
      course_code: "SE101",
      enrollment_role: "teacher",
    },
    {
      id: "88",
      name: "Human Computer Interaction",
      course_code: "HCI201",
      enrollment_role: "ta",
    },
  ]);
  const onLinked = vi.fn();
  const user = userEvent.setup();
  render(<CanvasCourseLink course={course} onLinked={onLinked} />);

  expect(fetch).not.toHaveBeenCalled();
  await user.click(screen.getByText("Link Canvas course"));
  expect(
    await screen.findByRole("option", {
      name: "SE101 — Software Engineering (Teacher)",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Link selected Canvas course" }),
  ).toBeDisabled();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({});

  await user.selectOptions(screen.getByLabelText("Canvas course"), "88");
  await user.click(
    screen.getByRole("button", { name: "Link selected Canvas course" }),
  );
  await waitFor(() => expect(onLinked).toHaveBeenCalledWith(linked));
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    platform_course_id: course.course_id,
    course_id: "88",
  });
});

test("explains how to connect Canvas and lets the professor retry", async () => {
  let attempts = 0;
  const { fetch } = mockApi(() =>
    ++attempts === 1
      ? { error: "Connect your Canvas account before loading Canvas data." }
      : [],
  );
  const user = userEvent.setup();
  render(<CanvasCourseLink course={course} onLinked={vi.fn()} />);

  await user.click(screen.getByText("Link Canvas course"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Connect Canvas below first",
  );
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByText(/No active Canvas courses/),
  ).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});
