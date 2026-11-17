import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import LearningDifficultyChart from "./LearningDifficultyChart";
import { api } from "./api";
vi.mock("./api", () => ({ api: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

test("includes the learner in the distribution, even when they are the only respondent", async () => {
  api.mockResolvedValue({ steps: [
    { step_index: 0, title: "Inventory", available: true, responses: 4, counts: { easy: 1, moderate: 1, hard: 2 } },
    { step_index: 1, title: "Payment", available: false, responses: null, counts: null },
    { step_index: 2, title: "Change", available: false, responses: null, counts: null },
  ] });
  render(<LearningDifficultyChart assignmentId="test" metrics={{ "0": { difficulty: "easy" }, "1": { difficulty: "somewhat_hard" } }} />);
  expect(await screen.findByText("5 responses, including yours")).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith("/platform/assignments/test/learning-journey");
  expect(screen.getByText("You: Easy")).toBeInTheDocument();
  expect(screen.getByText("You: Easy")).toHaveClass("is-your-difficulty");
  expect(screen.getAllByText("You")[0].parentElement).toHaveClass("difficulty-easy", "is-your-difficulty");
  expect(screen.getByRole("img", { name: /^Easy: 2 of 5/ })).toHaveAccessibleName("Easy: 2 of 5, Somewhat easy: 0 of 5, Moderate: 1 of 5, Somewhat hard: 0 of 5, Hard: 2 of 5");
  expect(screen.getByText("You: Somewhat hard")).toBeInTheDocument();
  expect(screen.getByText("1 response (yours)")).toBeInTheDocument();
  expect(screen.getByText("100%").parentElement).toHaveClass("difficulty-somewhat_hard", "is-your-difficulty");
  expect(screen.getByText("No ratings yet.")).toBeInTheDocument();
  expect(screen.getAllByRole("img")).toHaveLength(2);
});

test("shows an honest unavailable state when the request fails", async () => {
  api.mockRejectedValue(new Error("offline"));
  render(<LearningDifficultyChart assignmentId="test" />);
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("unavailable"));
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
