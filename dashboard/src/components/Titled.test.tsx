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
    const list = await screen.findByRole('list', {
      name: 'title of goal-1 › title of goal-1/batch-1',
    });
    const row = within(list).getByRole('listitem');
    const link = within(row).getByRole('link');
    expect(link).toHaveTextContent('title of goal-1/batch-1/backlog-1');
    // The title comes first; the key follows it as secondary text.
    const key = within(row).getByText('goal-1/batch-1/backlog-1', { selector: '.key' });
    expect(
      link.compareDocumentPosition(key) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const found = within(row).getByText('(goal-1/batch-1)');
    expect(found).toHaveClass('key');
    expect(within(row).getByText('Found on').nextElementSibling).toHaveTextContent(
      /^title of goal-1\/batch-1 \(goal-1\/batch-1\)$/,
    );
  });
});
