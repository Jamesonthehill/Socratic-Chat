import React from 'react';
import {test, expect, vi} from 'vitest';
import {render, screen, fireEvent, waitFor} from '@testing-library/react';
import ApplicationInterview from '../../self-directed-learning/student-app/src/ApplicationInterview';
import ApplicationInterviewReports from './ApplicationInterviewReports';
import {api as studentApi} from '../../self-directed-learning/student-app/src/api';
import {api as platformApi} from './api';
vi.mock('../../self-directed-learning/student-app/src/api',()=>({api:vi.fn()}));
vi.mock('./api',()=>({api:vi.fn()}));

const active = {status:'active',question:{id:'q-1',text:'Why did you choose that boundary?'},turns:[]};

test('starts after feedback, sends only its question ID, and shows a follow-up',async()=>{
  studentApi.mockReset();
  studentApi.mockResolvedValueOnce(active).mockResolvedValueOnce({...active,question:{id:'q-2',text:'How would a different actor change your boundary?'},
    turns:[{question:active.question.text,response:'The boundary defines what my system controls.',feedback:'You identified the boundary; explain its effect.'}]});
  render(<ApplicationInterview assignmentId="lesson-a" initial={null}/>);
  await screen.findByText(active.question.text);
  fireEvent.change(screen.getByLabelText('Explain your reasoning'),{target:{value:'The boundary defines what my system controls.'}});
  fireEvent.click(screen.getByRole('button',{name:'Send interview response'}));
  await screen.findByText('How would a different actor change your boundary?');
  expect(screen.getByText('The boundary defines what my system controls.')).toBeInTheDocument();
  const [path,options] = studentApi.mock.calls[1];
  expect(path).toBe('/student/assignments/lesson-a/application-interview');
  expect(JSON.parse(options.body)).toMatchObject({action:'answer',question_id:'q-1'});
  expect(options.body).not.toMatch(/student_id|grade|score/);
  expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
});

test('reload preserves the current question and saved failed response',async()=>{
  studentApi.mockReset();
  render(<ApplicationInterview assignmentId="lesson-a" initial={{...active,error:'Try again',retry_response:'My saved reasoning'}}/>);
  expect(screen.getByLabelText('Explain your reasoning')).toHaveValue('My saved reasoning');
  expect(studentApi).not.toHaveBeenCalled();
});

test('network retry reuses its turn ID and a model failure does not clear the answer',async()=>{
  studentApi.mockReset();
  studentApi.mockRejectedValueOnce(new Error('Network interrupted')).mockResolvedValueOnce({...active,error:'Feedback unavailable'});
  render(<ApplicationInterview assignmentId="lesson-a" initial={active}/>);
  fireEvent.change(screen.getByLabelText('Explain your reasoning'),{target:{value:'My explanation'}});
  fireEvent.click(screen.getByRole('button',{name:'Send interview response'}));
  await screen.findByText('Network interrupted');
  fireEvent.click(screen.getByRole('button',{name:'Send interview response'}));
  await screen.findByText('Feedback unavailable');
  expect(studentApi.mock.calls[0][1].body).toBe(studentApi.mock.calls[1][1].body);
  expect(screen.getByLabelText('Explain your reasoning')).toHaveValue('My explanation');
});

test('stop remains available when question generation fails',async()=>{
  studentApi.mockReset();
  studentApi.mockResolvedValueOnce({status:'pending',error:'Unavailable',turns:[]}).mockResolvedValueOnce({status:'stopped',turns:[]});
  render(<ApplicationInterview assignmentId="lesson-a" initial={null}/>);
  await screen.findByText('Unavailable');
  fireEvent.click(screen.getByRole('button',{name:'Stop interview and keep my result'}));
  await screen.findByText('Interview stopped. Your application result is unchanged.');
  expect(screen.queryByLabelText('Explain your reasoning')).not.toBeInTheDocument();
});

test('completed interview does not restart or claim a published grade',async()=>{
  studentApi.mockReset();
  render(<ApplicationInterview assignmentId="lesson-a" initial={{status:'complete',outcome:'needs_review',turns:[]}}/>);
  expect(screen.getByText(/Some reasoning needs further review/)).toBeInTheDocument();
  expect(studentApi).not.toHaveBeenCalled();
});

test('instructor report fetch is explicit and access errors do not show stale reports',async()=>{
  platformApi.mockReset();
  platformApi.mockResolvedValueOnce([{student_id:'student-a',display_name:'Synthetic Student',interview:null}])
    .mockRejectedValueOnce(new Error('You do not manage this course.'));
  render(<ApplicationInterviewReports assignmentId="lesson-a"/>);
  expect(platformApi).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Load interview evidence'}));
  await screen.findByText(/Synthetic Student/);
  fireEvent.click(screen.getByRole('button',{name:'Load interview evidence'}));
  await screen.findByRole('alert');
  expect(screen.queryByText(/Synthetic Student/)).not.toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('You do not manage this course.');
  expect(platformApi).toHaveBeenCalledWith('/platform/assignments/lesson-a/application-interviews');
});
