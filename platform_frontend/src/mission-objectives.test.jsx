import React from 'react';
import { render, screen } from '@testing-library/react';
import { test, expect } from 'vitest';
import MissionObjectiveProgress from './MissionObjectiveProgress';

const objectives = ['Explain why stock is checked before payment.', 'Explain what to do when ingredients are missing.'];
const evidence = {quote: 'Check stock first so we do not charge for an unavailable order.', reason: 'Explains the consequence.'};

test('shows objective coverage as a percentage and restores saved evidence', () => {
  const {rerender} = render(<MissionObjectiveProgress objectives={objectives} mission={1} />);
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0');
  rerender(<MissionObjectiveProgress objectives={objectives} mission={1} saved={{objectives, met:{'0':evidence}}} />);
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50');
  expect(screen.getByText('1 of 2 objectives demonstrated')).toBeInTheDocument();
  expect(screen.getByText(objectives[0]).closest('li')).toHaveClass('is-demonstrated');
  expect(screen.getByText(objectives[1]).closest('li')).not.toHaveClass('is-demonstrated');
  rerender(<MissionObjectiveProgress objectives={objectives} mission={1} saved={{objectives, met:{'0':evidence,'1':evidence}}} />);
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
});

test('edited objectives cannot inherit stale percentages', () => {
  render(<MissionObjectiveProgress mission={1} objectives={['Explain how a refund affects inventory.']}
    saved={{objectives, met:{'0':evidence,'1':evidence}}} />);
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0');
});

test('legacy missions keep their existing interface', () => {
  const {container} = render(<MissionObjectiveProgress mission={1} />);
  expect(container).toBeEmptyDOMElement();
});
