import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import LearningDifficultyChart from "./LearningDifficultyChart";
import { api } from "./api";
import userEvent from "@testing-library/user-event";
vi.mock("./api", () => ({ api: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

test("shows class distribution and the learner's separate rating", async () => {
  api.mockResolvedValue({ minimum_responses: 3, steps: [
    { step_index: 0, title: "Inventory", available: true, responses: 4, counts: { easy: 1, moderate: 1, hard: 2 } },
    { step_index: 1, title: "Payment", available: false, responses: null, counts: null },
  ] });
  render(<LearningDifficultyChart assignmentId="test" metrics={{ "0": { difficulty: "easy" } }} />);
  expect(await screen.findByText("4 classmates rated")).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith("/platform/assignments/test/learning-journey");
  expect(screen.getByText("You: Easy")).toBeInTheDocument();
  expect(screen.getByText("You: Easy")).toHaveClass("is-your-difficulty");
  expect(screen.getByText("You").parentElement).toHaveClass("difficulty-easy", "is-your-difficulty");
  expect(screen.getByRole("img")).toHaveAccessibleName("Easy: 1 of 4, Moderate: 1 of 4, Hard: 2 of 4");
  expect(screen.getByText(/after 3 classmates/)).toBeInTheDocument();
});

test("shows an honest unavailable state when the request fails", async () => {
  api.mockRejectedValue(new Error("offline"));
  render(<LearningDifficultyChart assignmentId="test" />);
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("unavailable"));
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});

test("sample ratings are a reversible preview and never written to the server", async () => {
  api.mockResolvedValue({ minimum_responses: 3, steps: [
    { step_index: 0, title: "Inventory", available: false, counts: null, responses: null },
  ] });
  render(<LearningDifficultyChart assignmentId="test" metrics={{ "0": { difficulty: "hard" } }} />);
  await screen.findByText("Awaiting class ratings");
  const toggle = screen.getByRole("checkbox", { name: "Preview sample ratings" });
  await userEvent.click(toggle);
  expect(screen.getByText(/12 fictional classmates/)).toBeInTheDocument();
  expect(screen.getByRole("img")).toHaveAccessibleName("Easy: 8 of 12, Moderate: 3 of 12, Hard: 1 of 12");
  expect(screen.getByText("You: Hard")).toBeInTheDocument();
  await userEvent.click(toggle);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.getByText("Awaiting class ratings")).toBeInTheDocument();
  expect(api).toHaveBeenCalledTimes(1);
});
