import React from "react";
import {test,expect} from "vitest";
import {render,screen} from "@testing-library/react";
import LessonPreview from "./LessonPreview";

test("shows generated questions, answer keys, practice and rubrics",()=>{
  render(<LessonPreview plan={{diagnostic_quiz:[{id:"q1",question:"What makes this measurable?",options:["A","B","C","D"],correct_index:2,explanation:"Use an observable measure."}],learning_assets:[{standard:[{prompt:"Write a measurable requirement.",rubric:"Includes a threshold."}]}]}}/>);
  expect(screen.getByText("What makes this measurable?")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Option C: C - correct" })).toBeDisabled();
  expect(screen.getByText("Correct answer")).toBeTruthy();
  expect(screen.getAllByText("Option C").length).toBeGreaterThan(0);
  expect(screen.getByText("Use an observable measure.")).toBeTruthy();
  expect(screen.getByText("Write a measurable requirement.")).toBeTruthy();
  expect(screen.getByText("Includes a threshold.")).toBeTruthy();
});

test('shows actionable instructional issues while keeping the draft editable',()=>{
 render(<LessonPreview plan={{instructional_quality_version:1,instructional_review:{passed:false,fingerprint:'internal-hash',issues:['The application rubric only assesses the first stage.']}}} onChange={()=>{}}/>);
 expect(screen.getByRole('alert')).toHaveTextContent('The application rubric only assesses the first stage.');
 expect(screen.getByRole('alert')).toHaveTextContent('Publishing will rerun the checks.');
 expect(screen.getAllByRole('button',{name:/Edit/}).length).toBeGreaterThan(0);
 expect(screen.queryByText('internal-hash')).not.toBeInTheDocument();
});


test('shows a readable source title and complete supporting passage without passage IDs',()=>{
 const passage='Plants capture sunlight and convert its energy into chemical energy.';
 render(<LessonPreview plan={{study_resources:[{title:'Ecology course notes.pdf',url:''}],diagnostic_quiz:[{id:'q1',question:'Which change affects energy entering the food web?',options:['A','B','C','D'],correct_index:0,material_reference:'S1: '+passage}]}}/>);
 expect(screen.getByText('Source: Ecology course notes.pdf')).toBeInTheDocument();
 expect(screen.getByText(passage)).toBeInTheDocument();
 expect(screen.queryByText('S1: '+passage)).not.toBeInTheDocument();
});
