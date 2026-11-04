import React from "react";
import { expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import {api} from "./api";
import InstructorActivityPage, { AnalyticsPage, progressMetrics } from "./InstructorActivityPage";
vi.mock("./courseContext",()=>({cachedCourseContext:()=>null,loadCourseContext:async()=>({course_id:"course1"})}));
vi.mock("./api",async original=>({...await original(),api:vi.fn(async path=>{
 if(path.includes("/documents"))return {files:[]};
 if(path==="/courses")return {courses:[{course_id:"course1",course_code:"SE101",title:"Software Engineering",membership_role:"instructor",membership_status:"approved"}]};
 if(path==="/platform/assignments")return [{id:"r1",course_id:"course1",course_code:"SE101",course_title:"Software Engineering",tool:"reflections",status:"published",title:"Project check-in",can_manage:true}];
 if(path.includes("reflection-analysis"))return {assignment:{id:"r1",title:"Project check-in"},summary:{assigned:1,started:1,completed:1,responses:1},students:[{student_id:"s1",name:"Student One",status:"completed",response_count:1,responses:["I want to study campus transit."]}]};
 return {id:"a1",course_id:"course1",tool:"debate",status:"published",title:"Design tradeoffs",instructions:"Defend a position",config:{scenario:"Should teams favor simple design?"},students:[{progress:"completed",result:{score_percent:80}},{progress:"in_progress"},{progress:"not_started"}]};
})}));

test("published assignment opens summary and KPIs with navigation to Analytics",async()=>{
 render(<MemoryRouter initialEntries={["/professor/activities/a1"]}><Routes><Route path="/professor/activities/:id" element={<InstructorActivityPage/>}/><Route path="/professor/analytics" element={<AnalyticsPage/>}/></Routes></MemoryRouter>);
 expect(await screen.findByRole("heading",{name:"Design tradeoffs"})).toBeInTheDocument();
 expect(screen.getByRole("heading",{name:"At a glance"})).toBeInTheDocument();
 expect(screen.getByText("Students started").parentElement).toHaveTextContent("2");
 expect(screen.getByText("Average grade").parentElement).toHaveTextContent("80%");
 expect(screen.queryByRole("heading",{name:"Select activity"})).not.toBeInTheDocument();
 await userEvent.setup().click(screen.getByRole("link",{name:"Detailed Insights →"}));
 expect(await screen.findByRole("heading",{name:"AIducate dashboard"})).toBeInTheDocument();
});
test("instructor selects a Reflection assignment and opens saved responses",async()=>{
 render(<MemoryRouter><AnalyticsPage/></MemoryRouter>);
 const user=userEvent.setup();
 await user.click(await screen.findByRole("button",{name:/Software Engineering/}));
 await user.click(screen.getByRole("button",{name:/Project check-in/}));
 await user.click(screen.getByRole("button",{name:"Run analysis"}));
 await user.click(await screen.findByRole("tab",{name:"Students"}));
 expect(screen.getByRole("heading",{name:"Student reflections"})).toBeInTheDocument();
 await user.click(screen.getByText("Student One"));
 expect(screen.getByText("I want to study campus transit.")).toBeInTheDocument();
});
test("published assignment can preview the student start without creating an attempt",async()=>{
 api.mockClear();
 render(<MemoryRouter initialEntries={[{pathname:"/professor/activities/a1",state:{showStudentPreview:true}}]}><Routes><Route path="/professor/activities/:id" element={<InstructorActivityPage/>}/></Routes></MemoryRouter>);
 const preview=await screen.findByRole("region",{name:"Student-view preview"});
 expect(preview).toHaveTextContent("Design tradeoffs");
 expect(preview).toHaveTextContent("read only");
 expect(screen.queryByRole("complementary",{name:"Instructor quick guide"})).not.toBeInTheDocument();
 await userEvent.setup().click(screen.getByRole("button",{name:"Preview start"}));
 expect(preview).toHaveTextContent("Should teams favor simple design?");
 expect(screen.getByLabelText("Your response")).toBeDisabled();
 expect(api.mock.calls.some(([path])=>path.includes("/start") || path.includes("/attempt"))).toBe(false);
 await userEvent.setup().click(screen.getByRole("button",{name:"Hide student preview"}));
 expect(screen.queryByRole("region",{name:"Student-view preview"})).not.toBeInTheDocument();
});
test("missing grade data is unavailable rather than a fabricated score",()=>{
 expect(progressMetrics([{progress:"completed",result:{message_count:4}},{progress:"not_started"}])).toMatchObject({assigned:2,started:1,completed:1,pending:1,completionRate:50,averageGrade:null});
});

test("draft editor reuses the loaded assignment instead of fetching it twice",async()=>{
 api.mockClear();
 api.mockImplementationOnce(async()=>({id:"draft1",course_id:"course1",tool:"self-directed-learning",status:"draft",title:"Saved draft",instructions:"Saved description",config:{document_ids:[],prompt:"Saved focus",custom_questions:[]}}));
 render(<MemoryRouter initialEntries={["/professor/activities/draft1"]}><Routes><Route path="/professor/activities/:id" element={<InstructorActivityPage/>}/></Routes></MemoryRouter>);
 expect(await screen.findByLabelText("Assignment title")).toHaveValue("Saved draft");
 expect(screen.getByLabelText("Learning focus")).toHaveValue("Saved focus");
 expect(api.mock.calls.filter(([path])=>path==="/platform/assignments/draft1")).toHaveLength(1);
});
