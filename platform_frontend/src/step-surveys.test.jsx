import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { StepSurveyEditor, StudentStepSurvey } from "./StepSurveys";
import AiducateWorkspace from "./AiducateWorkspace";
import { api } from "./api";
vi.mock("./api", async original=>({...await original(),api:vi.fn()}));
beforeEach(()=>{api.mockReset();});
const questions=[{id:"q1",kind:"confidence",prompt:"How confident are you about evidence?"},{id:"q2",kind:"text",prompt:"Which part was confusing?"}];
const survey={title:"Evidence reflection",version:"v1",published_at:"2026-11-11T12:00:00Z",questions};
const steps=[{index:0,title:"Inspect evidence",goal:"Explain an evidence-based decision",published:survey}];

test("instructor reviews generated questions before publishing a step survey",async()=>{
  const user=userEvent.setup();
  api.mockImplementation(async(path,options)=>{
    if(path.endsWith('/generate'))return {title:"Generated evidence reflection",questions};
    if(options?.method==='PUT')return {draft:options.body,published:{...survey,...options.body}};
    return {steps};
  });
  render(<StepSurveyEditor assignment={{id:"a1"}}/>);
  await user.click(await screen.findByRole("button",{name:"Generate step survey"}));
  await waitFor(()=>expect(screen.getByLabelText("Survey title")).toHaveValue("Generated evidence reflection"));
  expect(api.mock.calls.filter(([,options])=>options?.method==='PUT')).toHaveLength(0);
  await user.clear(screen.getByLabelText("Survey title"));await user.type(screen.getByLabelText("Survey title"),"Teacher reviewed survey");
  await user.click(screen.getByRole("button",{name:"Publish survey"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/platform/assignments/a1/step-surveys/0',expect.objectContaining({method:'PUT',body:expect.objectContaining({title:'Teacher reviewed survey',publish:true})})));
  expect(await screen.findByRole('status')).toHaveTextContent('Survey published');
});

test("student submits an ungraded survey independently of tutor messages or progression",async()=>{
  const user=userEvent.setup();api.mockResolvedValue({steps});
  render(<StudentStepSurvey assignmentId="a1" stepIndex={0}/>);
  expect(api).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button',{name:'Quiz / Survey'}));
  expect(await screen.findByRole('dialog')).toHaveTextContent('does not affect your grade');
  const submit=await screen.findByRole('button',{name:'Submit survey'});expect(submit).toBeDisabled();
  await user.click(screen.getByRole('radio',{name:'4'}));
  await user.type(screen.getByRole('textbox'),'I need more practice interpreting feedback.');
  expect(submit).toBeEnabled();await user.click(submit);
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/platform/assignments/a1/step-surveys/0/submit',{method:'POST',body:{version:'v1',answers:{q1:4,q2:'I need more practice interpreting feedback.'}}}));
  expect(await screen.findByRole('status')).toHaveTextContent('Survey submitted');
  expect(api.mock.calls.every(([path])=>!path.endsWith('/messages')&&!path.endsWith('/next-step'))).toBe(true);
});

test("AIDucate groups saved survey responses by step and version",async()=>{
  const user=userEvent.setup();
  api.mockImplementation(async(path)=>{
    if(path==='/courses')return {courses:[{course_id:'c1',course_code:'SE101',title:'Software Engineering',membership_role:'instructor',membership_status:'approved'}]};
    if(path==='/platform/assignments')return [{id:'a1',course_id:'c1',title:'Evidence activity',status:'published',tool:'socratic',config:{step_surveys:{0:{published:survey}}}}];
    if(path.endsWith('/step-survey-analysis'))return {groups:[{step_index:0,step_title:'Inspect evidence',survey,responses:[{student_id:'s1',name:'James',submitted_at:'2026-11-11T12:10:00Z',answers:{q1:4,q2:'I need more practice.'}}]}]};
    if(path.endsWith('/reflection-analysis'))return {summary:{assigned:1,started:1,completed:0,responses:1},students:[]};
    throw Error(path);
  });
  render(<MemoryRouter><AiducateWorkspace/></MemoryRouter>);
  await user.click(await screen.findByRole('button',{name:/Software Engineering/}));
  await user.click(screen.getByRole('button',{name:/Evidence activity/}));
  await user.click(screen.getByRole('button',{name:'Run analysis'}));
  await user.click(await screen.findByRole('tab',{name:'Step surveys'}));
  expect(screen.getByRole('heading',{name:'Step 1: Inspect evidence'})).toBeInTheDocument();
  await user.click(screen.getByText(/James · View responses/));
  expect(screen.getByText('4 / 5 (self-reported)')).toBeInTheDocument();
  expect(screen.getByText('I need more practice.')).toBeInTheDocument();
});
