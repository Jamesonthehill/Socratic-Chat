import React from "react";
import {test,expect,vi} from "vitest";
import {render,screen,fireEvent,waitFor} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import SDLWorkspace from "./SDLWorkspace";
import {api} from "./api";
vi.mock("./api",()=>({api:vi.fn()}));
test("resumes SDL in the platform and sends choices through the SDL adapter",async()=>{
  const attempt={messages:[{id:"m1",role:"assistant",content:"Welcome to the lesson."}],objective_progress:[],learning_state:{stage:"welcome"}};
  api.mockImplementation(async(path)=>path.endsWith("/start") || path.endsWith("/learning-turn") ? attempt : {title:"Requirements activity",learning_plan:{topic:"Requirements",study_resources:[]}});
  render(<MemoryRouter><SDLWorkspace assignmentId="sdl1"/></MemoryRouter>);
  expect(await screen.findByRole("heading",{name:"Requirements activity"})).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"I'm completely new"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith("/platform/self-directed/assignments/sdl1/learning-turn",expect.objectContaining({method:"POST",body:expect.objectContaining({content:"I'm completely new",turn_id:expect.any(String)})})));
});

test("shows selected course materials without a broken external link", async () => {
  const resource = {title: "Selected course materials", url: "", provider: "Instructor course materials", description: "Included in the lesson.", focus: "Study the examples. Instructor sub-questions to address: Which accountability applies?"};
  const attempt = {messages: [], objective_progress: [], learning_state: {stage: "study_resources", study_concepts: [], familiarity: "new", recommended_resource_url: null}};
  api.mockImplementation(async path => path.endsWith("/start") ? attempt : {title: "SDL activity", learning_plan: {topic: "Databases", study_resources: [resource]}});

  render(<MemoryRouter><SDLWorkspace assignmentId="sdl-local"/></MemoryRouter>);

  expect(await screen.findByText("Course readings")).toBeInTheDocument();
  expect(screen.queryByText("Selected course materials")).not.toBeInTheDocument();
  expect(screen.queryByText(/Instructor sub-questions/)).not.toBeInTheDocument();
  expect(screen.queryByText("Included in this lesson")).not.toBeInTheDocument();
  expect(screen.getByText(/No downloadable files are available/)).toBeInTheDocument();
});

function completedLesson(choice, notice = {version:"research-use-v1",title:"One last thing before you go",text:"May your chat be used for research?",optional:"Your choice is optional."}) {
  const attempt={messages:[],objective_progress:[],learning_state:{bounded_flow:true,stage:"completed",completion_code:"SDL-TEST-123",research_notice:notice,research_choice:choice}};
  api.mockReset();
  api.mockImplementation(async(path)=>path.endsWith("/start") ? attempt : path.endsWith("/materials") ? {files:[]} : {title:"Completed activity",learning_plan:{topic:"Testing",study_resources:[]}});
  render(<MemoryRouter><SDLWorkspace assignmentId="sdl1"/></MemoryRouter>);
}

test.each(["yes","no"])("unlocks the result card only after the %s research choice is saved",async(choice)=>{
  completedLesson();
  await screen.findByRole("heading",{name:"One last thing before you go"});
  expect(screen.queryByRole("button",{name:"View result card"})).not.toBeInTheDocument();
  let confirm;
  api.mockImplementationOnce(()=>new Promise(resolve=>{confirm=resolve;}));
  fireEvent.click(screen.getByRole("button",{name:choice === "yes" ? "Yes, happy to help!" : "No thanks, not this time"}));
  expect(screen.getByRole("status")).toHaveTextContent("Saving your choice");
  expect(screen.queryByRole("button",{name:"View result card"})).not.toBeInTheDocument();
  confirm({choice,notice_version:"research-use-v1"});
  expect(await screen.findByRole("button",{name:"View result card"})).toBeInTheDocument();
});

test.each(["failed","unconfirmed"])("keeps the result card hidden after an %s research save",async(mode)=>{
  completedLesson();
  await screen.findByRole("heading",{name:"One last thing before you go"});
  if(mode === "failed") api.mockRejectedValueOnce(new Error("Please retry saving."));
  else api.mockResolvedValueOnce({});
  fireEvent.click(screen.getByRole("button",{name:"No thanks, not this time"}));
  await screen.findByRole("alert");
  expect(screen.queryByRole("button",{name:"View result card"})).not.toBeInTheDocument();
  expect(screen.getByRole("button",{name:"No thanks, not this time"})).toBeEnabled();
});

test.each(["yes","no"])("restores result card access for a saved %s choice",async(choice)=>{
  completedLesson({choice,notice_version:"research-use-v1"});
  expect(await screen.findByRole("button",{name:"View result card"})).toBeInTheDocument();
});

test("keeps legacy completed lessons without a research question accessible",async()=>{
  completedLesson(null,null);
  expect(await screen.findByRole("button",{name:"View result card"})).toBeInTheDocument();
});


test("short assessment submits the current application ID and exposes interview retry",async()=>{
  api.mockReset();
  let attempt={messages:[],objective_progress:[],learning_state:{bounded_flow:true,assessment_version:2,stage:"application",quiz_count:3,application_count:3,interview_count:2,application_answers:[],current_application:{id:"identify",title:"Identify the actor",prompt:"Who requests delivery?"}}};
  api.mockImplementation(async(path,options)=>{
    if(path.endsWith("/learning-turn")) {
      expect(options.body).toMatchObject({action:"answer",question_id:"identify",content:"The customer."});
      attempt={...attempt,learning_state:{...attempt.learning_state,stage:"interview",current_application:null,interview_retry:true}};
      return attempt;
    }
    return path.endsWith("/start") ? attempt : path.endsWith("/materials") ? {files:[]} : {title:"Short activity",learning_plan:{topic:"Delivery",study_resources:[]}};
  });
  render(<MemoryRouter><SDLWorkspace assignmentId="short1"/></MemoryRouter>);
  await screen.findByText("Who requests delivery?");
  fireEvent.change(screen.getByLabelText("Your reply"),{target:{value:"The customer."}});
  fireEvent.click(screen.getByRole("button",{name:"Save answer & continue"}));
  expect(await screen.findByRole("button",{name:"Try again"})).toBeEnabled();
  expect(screen.queryByLabelText("Your reply")).not.toBeInTheDocument();
});

test('three application parts show each active question once and preserve submissions and history',async()=>{
 api.mockReset();
 const sections=[{id:'identify',title:'Identify the Issue',prompt:'Which sprint risk matters most?'},{id:'decide',title:'Decide on an Approach',prompt:'How will you address that risk?'},{id:'apply',title:'Apply the Solution',prompt:'What will you do next sprint?'}];
 const task={title:'Responding to Sprint Risks',description:'A team has a blocked dependency.',submission_prompt:'Use the sprint context to explain your decision.'};
 const envelope=i=>`Application part ${i+1} of 3 — ${sections[i].title}\n\n${sections[i].prompt}\n\nA couple of sentences or bullets is enough.`;
 const messages=[{id:'enter',role:'assistant',content:`Useful quiz feedback.\n\nScenario: ${task.submission_prompt}\n\n${envelope(0)}`}];
 let index=0;
 const current=()=>({messages:[...messages],objective_progress:[],learning_state:{bounded_flow:true,assessment_version:2,stage:index<3?'application':'interview',quiz_count:3,application_count:3,interview_count:2,application_answers:sections.slice(0,index),application_task:task,current_application:sections[index],current_interview:index===3?{id:'interview-1',prompt:'Why is that approach appropriate?'}:null}});
 api.mockImplementation(async(path,options)=>{
  if(path.endsWith('/learning-turn')) {
   expect(options.body).toMatchObject({action:'answer',question_id:sections[index].id,content:`Response ${index+1}`});
   messages.push({id:`student-${index}`,role:'student',content:options.body.content});
   index++;
   messages.push({id:`tutor-${index}`,role:'assistant',content:index<3?`Saved.\n\n${envelope(index)}`:'Application saved.\n\nInterview question 1 of 2\n\nWhy is that approach appropriate?\n\nOne or two sentences is enough.'});
   return current();
  }
  return path.endsWith('/start')?current():path.endsWith('/materials')?{files:[]}:{title:'Sprint activity',learning_plan:{topic:'Scrum',study_resources:[],required_task:task,application_sections:sections}};
 });
 render(<MemoryRouter><SDLWorkspace assignmentId="three-stage"/></MemoryRouter>);
 for(let part=0;part<3;part++) {
  await screen.findByText(sections[part].prompt);
  expect(screen.getAllByText(sections[part].prompt)).toHaveLength(1);
  expect(screen.getAllByText(task.description)).toHaveLength(1);
  expect(screen.getAllByText(task.submission_prompt)).toHaveLength(1);
  expect(screen.getByRole('form',{name:sections[part].title})).toContainElement(screen.getByLabelText('Your reply'));
  expect(screen.getByText('Useful quiz feedback.')).toBeInTheDocument();
  for(let future=part+1;future<3;future++) expect(screen.queryByText(sections[future].prompt)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Your reply'),{target:{value:`Response ${part+1}`}});
  fireEvent.click(screen.getByRole('button',{name:'Save answer & continue'}));
 }
 await screen.findByText('Why is that approach appropriate?');
 expect(screen.getAllByText('Why is that approach appropriate?')).toHaveLength(1);
 expect(screen.queryByRole('region',{name:'Application task scenario'})).not.toBeInTheDocument();
 sections.forEach(section=>expect(screen.getAllByText(section.prompt)).toHaveLength(1));
 expect(screen.getByText('Response 1')).toBeInTheDocument();
});

test('resumes interview questions, preserves Socratic prose, and reaches completion',async()=>{
 api.mockReset();
 const prompts=['Why does that protect the Sprint Goal?','What changes if the dependency remains blocked?'];
 let index=0;
 const messages=[{id:'i1',role:'assistant',content:`Application saved. Let’s explore your reasoning.\n\nInterview question 1 of 2\n\n${prompts[0]}\n\nOne or two sentences is enough.`}];
 const attempt=()=>({messages:[...messages],objective_progress:[],learning_state:{bounded_flow:true,assessment_version:2,stage:index<2?'interview':'completed',quiz_count:3,application_count:3,interview_count:2,interview_answers:prompts.slice(0,index),current_interview:index<2?{id:`interview-${index+1}`,prompt:prompts[index]}:null}});
 api.mockImplementation(async(path,options)=>{
  if(path.endsWith('/learning-turn')) {
   expect(options.body).toMatchObject({action:'answer',question_id:`interview-${index+1}`,content:'My reasoning.'});
   messages.push({id:`s${index}`,role:'student',content:'My reasoning.'}); index++;
   messages.push({id:`t${index}`,role:'assistant',content:index<2?`Saved.\n\nInterview question 2 of 2\n\n${prompts[1]}\n\nOne or two sentences is enough.`:'Application and interview feedback: You explained the tradeoff.\n\nConsider how you would inspect the result.\n\nIntended outcome: Protect the Sprint Goal.\nApply the Definition of Done.\n\nLesson complete. Completion records participation; feedback describes the evidence of understanding.'});
   return attempt();
  }
  return path.endsWith('/start')?attempt():path.endsWith('/materials')?{files:[]}:{title:'Interview activity',learning_plan:{topic:'Scrum',study_resources:[]}};
 });
 const mounted=render(<MemoryRouter><SDLWorkspace assignmentId="interview-resume"/></MemoryRouter>);
 for(let i=0;i<2;i++) {
  await screen.findByText(prompts[i]); expect(screen.getAllByText(prompts[i])).toHaveLength(1);
  fireEvent.change(screen.getByLabelText('Your reply'),{target:{value:'My reasoning.'}});
  fireEvent.click(screen.getByRole('button',{name:i===0?'Save answer & continue':'Submit & view feedback'}));
 }
 expect(await screen.findByText('Consider how you would inspect the result.')).toBeInTheDocument();
 expect(screen.getByRole('heading',{name:'Application and interview feedback'})).toBeInTheDocument();
 fireEvent.click(screen.getByText('Learning outcomes'));
 expect(screen.getByText('Apply the Definition of Done.')).toBeVisible();
 expect(screen.queryByLabelText('Your reply')).not.toBeInTheDocument();
 expect(screen.getByRole('progressbar',{name:'Lesson progress'})).toHaveAttribute('value','100');
 prompts.forEach(prompt=>expect(screen.getAllByText(prompt)).toHaveLength(1));
 mounted.unmount();
 render(<MemoryRouter><SDLWorkspace assignmentId="interview-resume"/></MemoryRouter>);
 expect(await screen.findByText('Consider how you would inspect the result.')).toBeInTheDocument();
 expect(screen.queryByLabelText('Your reply')).not.toBeInTheDocument();
});

test('study fallback resolves to actual files while authored readings appear once',async()=>{
 api.mockReset();
 const placeholder={title:'Selected course materials',url:'',provider:'Instructor course materials',description:'Generic fallback',focus:'Instructor sub-questions to address: hidden metadata'};
 const reading={title:'Sprint field notes',url:'',provider:'Course team',description:'Inspect this worked Sprint example.',focus:'Compare the three accountabilities.'};
 const attempt={messages:[{id:'study',role:'assistant',content:'Study the Sprint example and compare accountabilities.'}],objective_progress:[],learning_state:{bounded_flow:true,stage:'study_resources'}};
 api.mockImplementation(async path=>path.endsWith('/start')?attempt:path.endsWith('/materials')?{files:[{id:'doc1',filename:'scrum.pdf'}]}:{title:'Study activity',learning_plan:{topic:'Scrum',study_resources:[placeholder]}});
 const view=render(<MemoryRouter><SDLWorkspace assignmentId="readings"/></MemoryRouter>);
 expect(await screen.findByRole('button',{name:'↓ Download scrum.pdf'})).toBeEnabled();
 expect(screen.getAllByText('Study the Sprint example and compare accountabilities.')).toHaveLength(1);
 expect(screen.queryByText(/Instructor sub-questions/)).not.toBeInTheDocument();
 view.unmount();
 api.mockImplementation(async path=>path.endsWith('/start')?attempt:path.endsWith('/materials')?{files:[]}:{title:'Study activity',learning_plan:{topic:'Scrum',study_resources:[reading]}});
 render(<MemoryRouter><SDLWorkspace assignmentId="authored-reading"/></MemoryRouter>);
 expect(await screen.findByText('Sprint field notes')).toBeInTheDocument();
 expect(screen.getAllByText('Sprint field notes')).toHaveLength(1);
 expect(screen.getByText('Compare the three accountabilities.')).toBeInTheDocument();
});
