import React from "react";
import { test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LessonProgress, ActiveQuestion } from "../../self-directed-learning/student-app/src/LearningCards";

test("progress uses actual question counts and resumes the current phase", () => {
  const { container } = render(<LessonProgress plan={{}} state={{stage:"paused",resume_stage:"interview",assessment_version:2,quiz_count:3,quiz_index:3,application_count:3,application_answers:[{},{},{}],interview_count:2,interview_answers:[{}]}} />);
  expect(screen.getByRole("progressbar",{name:"Quiz progress"})).toHaveAttribute("aria-valuemax","3");
  const interview = screen.getByRole("progressbar",{name:"Interview progress"});
  expect(interview.children).toHaveLength(2);
  expect(interview).toHaveAttribute("aria-valuenow","1");
  expect(container.querySelector('[aria-current="step"]')).toHaveTextContent("Interview");
  expect(screen.queryByText(/%/)).not.toBeInTheDocument();
});

test("written question numbers appear inside the active card", () => {
  render(<ActiveQuestion question={{title:"Explain your reasoning",prompt:"Why?"}} interview number={2} />);
  expect(screen.getByText(/Question 2/)).toBeInTheDocument();
  expect(screen.getByRole("heading",{name:"Explain your reasoning"})).toHaveAttribute("id","sdl-active-question");
});
