import React from "react";
import { expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CanvasSurveyImport, { parseSurveyCsv } from "./CanvasSurveyImport";

test("reads quoted commas, escaped quotes, multiline responses and BOM", () => {
  expect(parseSurveyCsv('\uFEFFID,Question\r\ns1,"A, B\nHe said ""hello"""').rows).toEqual([["s1", 'A, B\nHe said "hello"']]);
});
test("rejects broken CSV and gradebooks", () => {
  for (const csv of ['ID,Q\na,"unfinished', 'ID,Q\na,b,c', 'ID,Q,Q\na,b,c', 'Student,Current Score\ns1,90']) expect(() => parseSurveyCsv(csv)).toThrow();
});
test("imports the supplied reflection shape, excludes identities, and counts answered rows", async () => {
  const user = userEvent.setup();
  render(<CanvasSurveyImport />);
  const file = new File([], "reflection.csv", {type:"text/csv"});
  file.text = async () => 'ID,section,How do you feel?,Current challenges?\na@example.edu,SE3155,Confused,"Writing code, from scratch"\nb@example.edu,SE3155,,';
  await user.upload(screen.getByLabelText("Canvas survey CSV file"), file);
  expect(await screen.findByText("reflection.csv")).toBeInTheDocument();
  expect(screen.getByLabelText("ID")).not.toBeChecked();
  await user.click(screen.getByRole("button", {name:"Review imported responses"}));
  expect(screen.getByText(/records contain responses/)).toHaveTextContent("1 records contain responses");
  expect(screen.getByText("Writing code, from scratch")).toBeInTheDocument();
  expect(screen.queryByText("a@example.edu")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", {name:"Clear imported data"}));
  expect(screen.queryByText("reflection.csv")).not.toBeInTheDocument();
});
