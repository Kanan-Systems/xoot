// kanan-90: titles first, keys second.
import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes } from '../test/api.ts';
import { renderApp } from '../test/renderApp.tsx';
import { KeyLabel, Titled } from './Titled.tsx';

const LONG =
  'A very long title that goes on and on well past the sixty character limit';

describe('Titled and KeyLabel', () => {
  it('puts the title first and the key after it as a secondary label', () => {
    const { container } = render(<Titled title="Ship it" itemKey="goal-1" />);
    const [title, key] = [...container.children];
    expect(title).toHaveTextContent('Ship it');
    expect(key).toHaveTextContent('goal-1');
    expect(key).toHaveClass('key');
  });

  it('cuts a long title and keeps the full text on hover', () => {
    render(<Titled title={LONG} itemKey="goal-1" />);
    expect(screen.getByTitle(LONG).textContent).toHaveLength(60);
  });

  it('shows a key-only reference as "title (key)", or the key when unknown', () => {
    const titles = new Map([['goal-1/decision-1', 'old rule']]);
    const { container, rerender } = render(
      <KeyLabel itemKey="goal-1/decision-1" titles={titles} />,
    );
    expect(container).toHaveTextContent(/^old rule \(goal-1\/decision-1\)$/);
    expect(container.querySelector('.key')).toHaveTextContent('(goal-1/decision-1)');
    rerender(<KeyLabel itemKey="goal-9/decision-1" titles={titles} />);
    expect(container).toHaveTextContent(/^goal-9\/decision-1$/);
  });
});

describe('a backlog row', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockApi(projectRoutes());
  });

  it('leads with the title; key and "found on" follow as secondary text', async () => {
    renderApp('/x/backlog');
    const table = await screen.findByRole('table', {
      name: 'title of goal-1 › title of goal-1/batch-1',
    });
    const [, row] = within(table).getAllByRole('row');
    const cells = within(row as HTMLElement).getAllByRole('cell');
    const link = within(cells[0] as HTMLElement).getByRole('link');
    expect(link).toHaveTextContent('title of goal-1/batch-1/backlog-1');
    expect(cells[1]?.firstElementChild).toHaveClass('key');
    expect(cells[1]).toHaveTextContent('goal-1/batch-1/backlog-1');
    const found = within(cells[3] as HTMLElement).getByText('(goal-1/batch-1)');
    expect(found).toHaveClass('key');
    expect(cells[3]).toHaveTextContent(
      /^title of goal-1\/batch-1 \(goal-1\/batch-1\)$/,
    );
  });
});
