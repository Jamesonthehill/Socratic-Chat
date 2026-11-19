import React from "react";
import { test, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import CompletionFeedback from "../../self-directed-learning/student-app/src/CompletionFeedback";

test("renders four descriptive cards and expandable student evidence safely", () => {
  const cards = ["well", "improve", "application", "next"].map(key => ({key, text:`Specific ${key} feedback from your lesson.`, evidence:[{id:"q1",quote:"<script>student response</script>"}]}));
  render(<CompletionFeedback feedback={{source:"ai",cards}} />);
  const region = screen.getByRole("region", {name:"Your learning feedback"});
  expect(within(region).getAllByRole("article")).toHaveLength(4);
  for (const title of ["What You Did Well","Areas for Improvement","Application & Critical Thinking","Recommended Next Steps"]) {
    expect(within(region).getByRole("heading", {name:title})).toBeInTheDocument();
  }
  expect(region.querySelector("script")).toBeNull();
  expect(within(region).getAllByText("From your responses")).toHaveLength(4);
});

test("missing evidence is not filled with invented responses", () => {
  render(<CompletionFeedback feedback={{source:"recorded_evidence",cards:[{key:"application",text:"No written responses are available to assess.",evidence:[]}]}} />);
  expect(screen.getByText(/Detailed AI feedback is unavailable/)).toBeInTheDocument();
  expect(screen.queryByText("From your responses")).not.toBeInTheDocument();
});
