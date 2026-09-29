import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Legend } from './Legend.tsx';

describe('Legend', () => {
  it('toggles the kinds and the seven categories, each with icon and label', () => {
    render(<Legend />);
    const toggle = screen.getByRole('button', { name: 'Legend' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const panel = screen.getByRole('region', { name: 'Legend' });
    for (const kind of ['Goal', 'Batch', 'Subtask']) {
      expect(within(panel).getByText(kind)).toBeInTheDocument();
    }
    const states = panel.querySelectorAll('.cat');
    expect(states).toHaveLength(7);
    expect(within(panel).getByText('Awaiting input')).toBeInTheDocument();
    expect(
      within(panel).getByText(
        'Unfiled: a subtask not yet placed under a batch — usually a side item captured during a session, waiting for triage.',
      ),
    ).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.queryByRole('region', { name: 'Legend' })).toBeNull();
  });
});
