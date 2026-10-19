import React from "react";
import {test,expect} from "vitest";
import {render,screen,fireEvent,within} from "@testing-library/react";
import StudentAssignmentBrowser from "./StudentAssignmentBrowser";
const items=[{title:"Fresh activity",progress:"not_started"},{title:"Started activity",progress:"in_progress"},{title:"Finished activity",progress:"completed"}];
const renderItems=(rows,view)=><div data-testid="results" data-view={view}>{rows.map(item=><p key={item.title}>{item.title}</p>)}</div>;
test("four stacked groups show matching assignments and icon-only view preference persists",()=>{
  const {unmount}=render(<StudentAssignmentBrowser items={items} renderItems={renderItems}/>);
  expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  expect(within(screen.getByRole("region",{name:/^New/})).getByText("Fresh activity")).toBeInTheDocument();
  expect(within(screen.getByRole("region",{name:/^In progress/})).getByText("Started activity")).toBeInTheDocument();
  expect(within(screen.getByRole("region",{name:/^Completed/})).getByText("Finished activity")).toBeInTheDocument();
  expect(within(screen.getByRole("region",{name:/^All assignments/})).getByText("Fresh activity")).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Grid view"})).toHaveAttribute("aria-pressed","true");
  expect(screen.getByRole("button",{name:"Grid view"})).toHaveTextContent("");
  fireEvent.click(screen.getByRole("button",{name:"List view"}));
  expect(screen.getAllByTestId("results").every(el=>el.dataset.view==="list")).toBe(true);
  unmount();
  render(<StudentAssignmentBrowser items={items} renderItems={renderItems}/>);
  expect(screen.getByRole("button",{name:"List view"})).toHaveAttribute("aria-pressed","true");
});
test("empty groups remain visible",()=>{
  render(<StudentAssignmentBrowser items={[]} renderItems={renderItems}/>);
  expect(screen.getAllByRole("region")).toHaveLength(4);
  expect(screen.getByText("No new assignments.")).toBeInTheDocument();
});
