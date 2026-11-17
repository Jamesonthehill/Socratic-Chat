import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { ImprovementConsentDialog } from "./StudentWorkspace";
vi.mock("./PdfMaterialPreview", () => ({ default: () => null }));
afterEach(cleanup);

test.each([["Allow use", true], ["Submit without sharing", false]])("%s records the explicit choice", async (label, value) => {
  const choose = vi.fn();
  render(<ImprovementConsentDialog onChoose={choose} onClose={() => {}} busy={false} />);
  expect(screen.getByRole("dialog")).toHaveAccessibleName("Help us improve BrainTutor?");
  await userEvent.click(screen.getByRole("button", { name: label }));
  expect(choose).toHaveBeenCalledWith(value);
});

test("celebrates only a successful submission", () => {
  const { rerender } = render(<ImprovementConsentDialog busy onChoose={() => {}} onClose={() => {}} />);
  expect(screen.getByRole("status")).toHaveTextContent("Submitting your assignment");
  expect(screen.queryByText("Assignment submitted!")).not.toBeInTheDocument();
  rerender(<ImprovementConsentDialog complete onChoose={() => {}} onClose={() => {}} />);
  expect(screen.getByRole("status")).toHaveTextContent("Assignment submitted!");
  expect(screen.queryByRole("button", { name: "Allow use" })).not.toBeInTheDocument();
});
