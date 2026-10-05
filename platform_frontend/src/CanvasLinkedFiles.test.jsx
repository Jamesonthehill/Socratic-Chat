import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CanvasLinkedFiles from "./CanvasLinkedFiles";
import { api } from "./api";

vi.mock("./api", () => ({ api: vi.fn() }));

beforeEach(() => api.mockReset());

test("Canvas files are only added after the instructor selects and confirms them", async () => {
  let imported = false;
  api.mockImplementation(async (_path, options) => {
    if (options?.method === "POST") {
      imported = true;
      return { imported: [{ id: 99, filename: "project.pdf", document_id: "doc-99" }], skipped: [] };
    }
    return { files: [
      { id: 99, filename: "project.pdf", size: 2048, importable: true, imported },
      { id: 100, filename: "source.zip", size: 4096, importable: false, imported: false,
        reason: "This file type cannot be indexed." },
    ] };
  });
  const onImported = vi.fn();
  const user = userEvent.setup();
  render(<CanvasLinkedFiles assignmentId="draft-1" onImported={onImported} />);

  expect(await screen.findByText("project.pdf")).toBeInTheDocument();
  expect(api).toHaveBeenCalledTimes(1);
  const checkboxes = screen.getAllByRole("checkbox");
  expect(checkboxes[0]).not.toBeChecked();
  expect(checkboxes[1]).toBeDisabled();
  const button = screen.getByRole("button", { name: "Add selected files to course materials" });
  expect(button).toBeDisabled();

  await user.click(checkboxes[0]);
  await user.click(button);

  await waitFor(() => expect(onImported).toHaveBeenCalledTimes(1));
  expect(api).toHaveBeenCalledWith("/platform/assignments/draft-1/canvas-files", {
    method: "POST", body: { file_ids: [99] },
  });
  expect(screen.getByText("Already in course materials")).toBeInTheDocument();
});
