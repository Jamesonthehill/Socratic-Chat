import { test, expect } from "vitest";
import { presentTutorMessage } from "../../self-directed-learning/student-app/src/learning-presentation";
test("maps generated instruction envelopes without discarding feedback and follow-ups", () => {
  const prompt = "What is the risk?";
  const content = `Good reasoning.\n\nScenario: Team context.\n\nApplication part 1 of 3 — Identify\n\n${prompt}\n\nA couple of sentences or bullets is enough.\n\nWhat evidence supports your view?`;
  const result = presentTutorMessage(content, {
    scenario: "Team context.",
    activeQuestion: { prompt },
  });
  expect(result.questions).toEqual([]);
  expect(result.text).toContain("Good reasoning.");
  expect(result.text).toContain("What evidence supports your view?");
  expect(result.text).not.toContain(prompt);
  expect(
    presentTutorMessage(content, { scenario: "Team context." }).questions,
  ).toEqual([{ title: "Identify", prompt }]);
  expect(
    presentTutorMessage(
      "Scenario: An unexpected hint.\n\nWhy might that matter?",
    ).text,
  ).toContain("An unexpected hint.");
});

test("retains malformed envelopes, unknown instructions and hint content", () => {
  const text =
    "Application part 1 of 3 — Explore\n\nThink about the goal.\n\nHint: inspect the current evidence.";
  expect(presentTutorMessage(text).text).toBe(text);
  expect(presentTutorMessage("What evidence supports your view?").text).toBe(
    "What evidence supports your view?",
  );
});
