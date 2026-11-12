import { expect, test } from "vitest";
import { emphasizeFeedbackReason } from "./SocraticLearningSummary";
import SocraticLearningSummary from "./SocraticLearningSummary";
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
afterEach(cleanup);

test("emphasizes the reason in saved feedback without emphasizing praise", () => {
  expect(emphasizeFeedbackReason("Good progress. Tests matter because review cannot catch every defect."))
    .toBe("Good progress. Tests matter **because review cannot catch every defect.**");
  expect(emphasizeFeedbackReason("Review **cannot catch every defect**."))
    .toBe("Review **cannot catch every defect**.");
  expect(emphasizeFeedbackReason("Good progress." )).toBe("Good progress.");
});

test("lists feedback in learning-step order and finishes with overall tutor feedback", () => {
  render(<SocraticLearningSummary steps={[{ title: "First", goal: "Explain inspection" }, { title: "Second" }]}
    summary={{ student_reflection: "I learned.", final_comment: "Inspection matters because it guides adaptation.", step_reviews: [
      { step_index: 1, title: "Second", understood: [{ explanation: "You explained adaptation.", student_quotes: ["Change the plan."] }] },
      { step_index: 0, title: "First", understood: [{ explanation: "You explained inspection.", student_quotes: ["Inspect results."] }] },
    ] }} />);
  const first = screen.getByRole("heading", { name: "Step 1 · First" });
  const second = screen.getByRole("heading", { name: "Step 2 · Second" });
  const overall = screen.getByRole("heading", { name: "Overall tutor feedback" });
  expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(second.compareDocumentPosition(overall) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText("because it guides adaptation.").tagName).toBe("STRONG");
});

test("shows a source passage instead of the student's chat evidence", () => {
  render(<SocraticLearningSummary steps={[{ title: "Inspection", source: {
    text: "Inspect the results. Adapt the plan.", evidence_quote: "Adapt the plan.", title: "Scrum guide", page_number: 2,
  } }]} summary={{ student_reflection: "My summary", final_comment: "Use evidence.", step_reviews: [
    { step_index: 0, title: "Inspection", understood: [{ explanation: "You connected evidence to adaptation.", student_quotes: ["My private answer"] }] },
  ] }} />);
  expect(screen.getByText("Adapt the plan.")).toBeInTheDocument();
  expect(screen.getByText("Scrum guide · Page 2")).toBeInTheDocument();
  expect(screen.queryByText("View chat evidence")).not.toBeInTheDocument();
  expect(screen.queryByText("My private answer")).not.toBeInTheDocument();
});
