import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import AiducateStudentProfiles from "./AiducateStudentProfiles";

test("profiles show saved responses first and allow viewing students without responses", async () => {
  const user = userEvent.setup();
  render(<AiducateStudentProfiles analysis={{ students: [
    { student_id: "1", name: "Record 1", responses: [] },
    { student_id: "2", name: "Record 2", responses: ["Git was hard"] },
  ] }} />);

  expect(screen.getByText("Showing 1 of 2 students · 1 with responses")).toBeInTheDocument();
  expect(screen.queryByText("Record 1")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "View reflections for Record 2" }));
  expect(screen.getByText("Git was hard")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Clear all filters" }));
  expect(screen.getByText("Record 1")).toBeInTheDocument();
  expect(screen.getByText("No response")).toBeInTheDocument();
});
