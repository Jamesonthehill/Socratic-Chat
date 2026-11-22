import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PipelineLogs from "./PipelineLogs";
import { api } from "./api";
vi.mock("./api", () => ({ api: vi.fn() }));
const trace = {
  trace_id: "request-123", assignment_id: "assignment-a", assignment_title: "Scrum values",
  course_title: "Software Engineering", started_at: "2026-11-22T12:00:00Z", duration_ms: 1200,
  status: "complete", step_index: 0,
  events: [{ stage: "7", event: "step_readiness_completed", elapsed_ms: 1200,
    fields: { provider: "OpenAI", model: "gpt-6-luna", ready: true } }],
};
beforeEach(() => { api.mockReset(); api.mockResolvedValue({ traces: [trace] }); });

test("shows stage, model, readiness and request details", async () => {
  render(<PipelineLogs />);
  const details = await screen.findByRole("region", { name: "Request details" });
  expect(within(details).getByText("Check readiness / prepare prompt")).toBeInTheDocument();
  expect(within(details).getAllByText("gpt-6-luna").length).toBeGreaterThan(0);
  expect(within(details).getByText("true")).toBeInTheDocument();
  expect(screen.getByText("Learning step 1 · 1.20s")).toBeInTheDocument();
});

test("filters errors and assignment names", async () => {
  api.mockResolvedValue({ traces: [trace, { ...trace, trace_id: "request-error", assignment_id: "b",
    assignment_title: "Threads", status: "attention", events: [{ stage: "6", event: "evaluation_failed", elapsed_ms: 100,
      fields: { error_type: "AuthenticationError", status_code: 401 } }] }] });
  render(<PipelineLogs />);
  await screen.findByRole("region", { name: "Request details" });
  await userEvent.click(screen.getByLabelText("Needs attention only"));
  expect(screen.queryByRole("button", { name: /Scrum values/ })).not.toBeInTheDocument();
  expect(screen.getByText("AuthenticationError")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Assignment"), { target: { value: "assignment-a" } });
  expect(screen.getByText("No matching requests")).toBeInTheDocument();
});

test("refresh errors keep existing logs and offer retry", async () => {
  render(<PipelineLogs />);
  await screen.findByRole("region", { name: "Request details" });
  api.mockRejectedValueOnce(Error("Connection interrupted"));
  await userEvent.click(screen.getByRole("button", { name: "Refresh logs" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Showing the last available logs");
  expect(screen.getByRole("region", { name: "Request details" })).toBeInTheDocument();
});

test("automatically refreshes live requests and stops polling after unmount", async () => {
  vi.useFakeTimers();
  try {
    const view = render(<PipelineLogs />);
    await act(async () => {});
    expect(api).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(api).toHaveBeenCalledTimes(2);
    view.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(api).toHaveBeenCalledTimes(2);
  } finally { vi.useRealTimers(); }
});

test("empty state explains how to create traces", async () => {
  api.mockResolvedValue({ traces: [] });
  render(<PipelineLogs />);
  expect(await screen.findByText("No assignment logs yet")).toBeInTheDocument();
  expect(screen.getByText(/Send a message in a Socratic assignment/)).toBeInTheDocument();
});

test('shows expandable prompt instructions with preserved lines and a truncation notice', async () => {
  api.mockResolvedValue({traces: [{...trace, events: [{stage: '7', event: 'model_prompt', elapsed_ms: 50,
    fields: {phase: 'step-readiness', model: 'gpt-6-luna'},
    prompt: {role: 'system', text: 'Judge the student’s reasoning.\nAsk one focused follow-up question.', truncated: true}}]}]});
  render(<PipelineLogs />);
  const toggle = await screen.findByText('View prompt instructions (system)');
  await userEvent.click(toggle);
  expect(toggle.closest('details')).toHaveAttribute('open');
  expect(toggle.closest('details').querySelector('pre').textContent).toBe('Judge the student’s reasoning.\nAsk one focused follow-up question.');
  expect(screen.getByText(/exceeded the log limit/)).toBeInTheDocument();
});

test('explains why older requests have no captured prompts', async () => {
  render(<PipelineLogs />);
  expect(await screen.findByText(/Prompt instructions were not captured for this request/)).toBeInTheDocument();
});

test('generates a separate instructor test and selects its prompt log', async () => {
  const diagnostic = {...trace, trace_id: 'diagnostic-request', diagnostic: true, events: [{stage: '8', event: 'model_prompt', elapsed_ms: 20,
    fields: {model: 'gpt-6-luna'}, prompt: {role: 'system', text: 'Use one focused Socratic question.', truncated: false}}]};
  let generated = false;
  api.mockImplementation(async (path, options) => {
    if (path === '/platform/pipeline-logs/test') {
      expect(options).toEqual({method: 'POST', body: {assignment_id: 'assignment-a'}});
      generated = true; return {trace_id: diagnostic.trace_id, failed: false};
    }
    return {traces: generated ? [diagnostic, trace] : [trace]};
  });
  render(<PipelineLogs />);
  await screen.findByRole('region', {name: 'Request details'});
  await userEvent.click(screen.getByRole('button', {name: 'Generate test log'}));
  const details = screen.getByRole('region', {name: 'Request details'});
  expect(await within(details).findByText('View prompt instructions (system)')).toBeInTheDocument();
  expect(within(details).getByText(/Instructor test using the published assignment/)).toBeInTheDocument();
});

test('shows diagnostic failure and keeps the previous logs', async () => {
  render(<PipelineLogs />);
  await screen.findByRole('region', {name: 'Request details'});
  api.mockRejectedValueOnce(Error('The model service is unavailable.'));
  await userEvent.click(screen.getByRole('button', {name: 'Generate test log'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('The model service is unavailable.');
  expect(screen.getByRole('region', {name: 'Request details'})).toBeInTheDocument();
});
