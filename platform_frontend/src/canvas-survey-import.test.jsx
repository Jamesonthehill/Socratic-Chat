import React from "react";
import { expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CanvasSurveyImport, { parseSurveyCsv, matchStudentGrades } from "./CanvasSurveyImport";
import { readFileSync } from "node:fs";

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

const gradingText = 'Student,ID,SIS Login ID,Reflection 1,Current Score\n,,,,\n    Points Possible,,,5,(read only)\nstudent-1,100,S419832,0,78.52\nstudent-2,101,S416034,,90';
test("grading imports skip posting/points rows and preserve zeros and missing grades", () => {
  const csv = gradingText.replace(',,,,', ',,,Manual Posting,');
  const grading = parseSurveyCsv(csv, {grading:true});
  expect(grading.rows).toHaveLength(2);
  expect(grading.excludedRows).toBe(2);
  expect(grading.points[3]).toBe('5');
  const matches=matchStudentGrades({rows:[['S419832@charlotte.edu'],['s416034@charlotte.edu'],['missing'],['']]}, grading, 0, 2);
  expect(matches.map(m=>m.status)).toEqual(['Matched','Matched','No grade match','Missing ID']);
  expect(matches[0].grade[3]).toBe('0');
  expect(matches[1].grade[3]).toBe('');
  expect(matchStudentGrades({rows:[['s419832']]},{rows:[['S419832'],['s419832']]},0,0)[0]).toEqual({status:'Duplicate grading ID',grade:null});
});

test("two uploads match by SIS ID instead of unrelated Canvas ID and show the selected grade", async () => {
  const user=userEvent.setup();render(<CanvasSurveyImport/>);
  const reflection=new File([], 'reflection.csv', {type:'text/csv'});
  reflection.text=async()=> 'ID,section,What was difficult?\nS419832@charlotte.edu,SE3155,Writing Python';
  const grading=new File([], 'grading.csv', {type:'text/csv'});
  grading.text=async()=>gradingText;
  await user.upload(screen.getByLabelText('Canvas survey CSV file'),reflection);
  await screen.findByText('reflection.csv');
  await user.upload(screen.getByLabelText('Grading CSV file'),grading);
  await screen.findByText('grading.csv');
  expect(screen.getByLabelText('Grading student ID')).toHaveValue('2');
  expect(screen.getByRole('button',{name:'Review imported responses'})).toBeDisabled();
  await user.selectOptions(screen.getByLabelText('Grade to display'),'3');
  await user.click(screen.getByRole('button',{name:'Review imported responses'}));
  expect(screen.getByRole('table')).toHaveTextContent('Matched');
  expect(screen.getByRole('table')).toHaveTextContent('Writing Python');
  expect(screen.getByRole('table')).toHaveTextContent('0');
});

test.skipIf(!process.env.REFLECTION_SAMPLE || !process.env.GRADING_SAMPLE)("provided reflection and grading files join without dropping records",()=>{
  const reflection=parseSurveyCsv(readFileSync(process.env.REFLECTION_SAMPLE,'utf8'));
  const grading=parseSurveyCsv(readFileSync(process.env.GRADING_SAMPLE,'utf8'),{grading:true});
  const matches=matchStudentGrades(reflection,grading,reflection.headers.indexOf('ID'),grading.headers.indexOf('SIS Login ID'));
  expect(reflection.rows).toHaveLength(75);
  expect(grading.rows).toHaveLength(75);
  expect(matches).toHaveLength(75);
  expect(matches.every(m=>m.status==='Matched')).toBe(true);
});
