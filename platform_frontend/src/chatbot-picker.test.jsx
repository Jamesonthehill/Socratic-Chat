import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import ChatbotPicker from "./ChatbotPicker";

test("the assignment editor offers active chatbots for a legacy assignment", () => {
  render(<ChatbotPicker value="student-agent" onChange={vi.fn()} />);

  expect(screen.queryByRole("radio", { name: "Student Agent Bot" })).not.toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "Socratic Chat" })).not.toBeChecked();
  expect(screen.getAllByRole("radio")).toHaveLength(5);
});
