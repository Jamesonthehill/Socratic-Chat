import React from "react";
import { expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import MaterialExpansion from "./MaterialExpansion";

test("instructor can review, edit, approve and remove draft additions",()=>{
  const expand=vi.fn();
  function Editor(){
    const [draft,setDraft]=React.useState({materialExpansion:"A class describes structure. Each object has its own state.",expansionApproved:false,expansionSourceHash:"source-hash"});
    return <MaterialExpansion value={draft.materialExpansion} approved={draft.expansionApproved} sourceHash={draft.expansionSourceHash} canExpand onExpand={expand} onChange={patch=>setDraft(d=>({...d,...patch}))}/>;
  }
  render(<Editor/>);
  const approval=screen.getByRole("checkbox",{name:"I reviewed these additions for accuracy and scope"});
  expect(approval).not.toBeChecked();
  fireEvent.click(approval);
  expect(approval).toBeChecked();
  fireEvent.change(screen.getByLabelText("AI-drafted additions"),{target:{value:"A class is a blueprint. Each instance has separate state."}});
  expect(approval).not.toBeChecked();
  fireEvent.click(screen.getByRole("button",{name:"Generate a new expansion"}));
  expect(expand).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button",{name:"Remove additions"}));
  expect(screen.queryByLabelText("AI-drafted additions")).not.toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Expand this material"})).toBeInTheDocument();
});

test("changed source blocks approval until the expansion is regenerated or removed",()=>{
  render(<MaterialExpansion value="Old additions" sourceHash="" canExpand onExpand={()=>{}} onChange={()=>{}}/>);
  expect(screen.getByRole("checkbox")).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("learning scope changed");
});
