import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Legend } from './Legend.tsx';

describe('Legend', () => {
  it('toggles the four kinds and the six categories, each with icon and label', () => {
    render(<Legend />);
    const toggle = screen.getByRole('button', { name: 'Legend' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const panel = screen.getByRole('region', { name: 'Legend' });
    const kinds = [...panel.querySelectorAll('ul')][0]?.querySelectorAll('li') ?? [];
    expect([...kinds].map((li) => li.textContent)).toEqual([
      '◎ Goal',
      '▤ Batch',
      '• Subtask',
      '⚑ Backlog',
    ]);
    const states = panel.querySelectorAll('.cat');
    expect([...states].map((state) => state.textContent)).toEqual([
      '○ Open',
      '▶ Active',
      '■ Blocked',
      '? Awaiting input',
      '✓ Done',
      '✕ Dropped',
    ]);
    expect(
      within(panel).getByText(/Open backlog blocks completion/),
    ).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.queryByRole('region', { name: 'Legend' })).toBeNull();
  });
});
