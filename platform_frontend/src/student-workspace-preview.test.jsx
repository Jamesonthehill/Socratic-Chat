import React from 'react';
import { expect, test, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api, streamApi } from './api';
import { StudentActivityPreview } from './StudentActivityPreview';
vi.mock('./PdfMaterialPreview', () => ({default: () => <div>PDF viewer</div>}));

const { previewData } = vi.hoisted(() => ({previewData: {
  assignment: {id: 'a1', tool: 'socratic', title: 'Registration decisions', status: 'published',
    student_config: {guidance_mode: 'guided', learning_steps: [{title: 'Inspect feedback', goal: 'Use evidence to adapt.'}]}},
  opening: {id: 'preview-only', status: 'in_progress', messages: [{role: 'assistant',
    content: 'Step 1: Inspect feedback\n\nStudents report that registration is too slow.\n\nWhat should the team inspect?',
    next_thinking_step: 'What should the team inspect?'}],
    engine_state: {socratic: {phase: 'teaching', learning_step_index: 0, next_thinking_step: 'What should the team inspect?'}}},
}}));
vi.mock('./api', async original => ({...await original(), api: vi.fn(async path => {
  if (path.endsWith('/student-preview')) return previewData;
  if (path.endsWith('/materials')) return {materials: [{document_id: 'doc1', title: 'Guide.pdf', original_available: true}]};
  throw Error(`Unexpected request: ${path}`);
}), streamApi: vi.fn()}));

function mountPreview() {
  render(<MemoryRouter initialEntries={['/professor/activities/a1']}><Routes>
    <Route path='/professor/activities/:id' element={<StudentActivityPreview item={{id: 'a1', tool: 'socratic'}} />} />
  </Routes></MemoryRouter>);
}

test('Socratic preview uses the actual student materials, path, start screen and chat interface', async () => {
  api.mockClear(); streamApi.mockClear();
  const user = userEvent.setup();
  mountPreview();
  expect(await screen.findByRole('heading', {name: 'Registration decisions'})).toBeInTheDocument();
  expect(screen.getByText('Ready when you are.')).toBeInTheDocument();
  expect(screen.getByRole('heading', {name: 'Your learning path'})).toBeInTheDocument();
  expect(await screen.findByRole('button', {name: /View Guide.pdf/})).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Start assignment'}));
  expect(await screen.findByText('Students report that registration is too slow.')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Send message'})).toBeDisabled();
  expect(screen.getByPlaceholderText('Share your thinking…')).toBeDisabled();
  expect(api.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true);
  expect(api.mock.calls.some(([path]) => path.endsWith('/attempt') || path.endsWith('/start'))).toBe(false);
  expect(streamApi).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', {name: 'Reset preview'}));
  expect(await screen.findByRole('button', {name: 'Start assignment'})).toBeInTheDocument();
  expect(screen.queryByText('Students report that registration is too slow.')).not.toBeInTheDocument();
});

test('preview loading failures are shown without opening a student attempt', async () => {
  api.mockRejectedValueOnce(Error('You do not manage this course.'));
  mountPreview();
  expect(await screen.findByText('You do not manage this course.')).toBeInTheDocument();
  expect(within(screen.getByRole('region', {name: 'Student-view preview'})).queryByRole('button', {name: 'Start assignment'})).not.toBeInTheDocument();
});
