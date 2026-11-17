import React, { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { test, expect } from "vitest";
import SdlLessonSetup from "./SdlLessonSetup";

test("lesson setup preserves the existing focus, concepts and learning-boundary fields", () => {
  let saved;
  function Form() {
    const [value, setValue] = useState({
      prompt: "Scrum",
      custom_questions: ["Sprint Planning", "Daily Scrum"],
      starting_point: "Teamwork",
      ending_point: "Apply Scrum",
    });
    saved = value;
    return <SdlLessonSetup value={value} onChange={setValue} />;
  }
  render(<Form />);
  expect(
    screen.getByRole("heading", { name: "Create a learning lesson" }),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("group")).toHaveLength(4);
  expect(screen.getByLabelText("Learning focus")).toHaveValue("Scrum");
  expect(
    screen.getByLabelText("What specific concepts should the lesson cover?"),
  ).toHaveValue("Sprint Planning\nDaily Scrum");
  fireEvent.change(screen.getByLabelText("What do students already know?"), {
    target: { value: "Basic software development" },
  });
  fireEvent.change(screen.getByLabelText("Additional instructions"), {
    target: { value: "Use a campus project example." },
  });
  expect(saved).toMatchObject({
    prompt: "Scrum",
    custom_questions: ["Sprint Planning", "Daily Scrum"],
    starting_point: "Basic software development",
    ending_point: "Apply Scrum",
    additional_instructions: "Use a campus project example.",
  });
});
