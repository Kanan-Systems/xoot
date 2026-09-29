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
    const { container } = render(<Titled title="Ship it" itemKey="x-1" />);
    const [title, key] = [...container.children];
    expect(title).toHaveTextContent('Ship it');
    expect(key).toHaveTextContent('x-1');
    expect(key).toHaveClass('key');
  });

  it('cuts a long title and keeps the full text on hover', () => {
    render(<Titled title={LONG} itemKey="x-1" />);
    expect(screen.getByTitle(LONG).textContent).toHaveLength(60);
  });

  it('shows a key-only reference as "title (key)", or the key when unknown', () => {
    const titles = new Map([['x-D1', 'old rule']]);
    const { container, rerender } = render(<KeyLabel itemKey="x-D1" titles={titles} />);
    expect(container).toHaveTextContent(/^old rule \(x-D1\)$/);
    expect(container.querySelector('.key')).toHaveTextContent('(x-D1)');
    rerender(<KeyLabel itemKey="x-D9" titles={titles} />);
    expect(container).toHaveTextContent(/^x-D9$/);
  });
});

describe('a table row', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockApi(projectRoutes());
  });

  it('leads with the title; the key and holder follow as secondary text', async () => {
    renderApp('/x/backlog');
    const table = await screen.findByRole('table', { name: 'Project backlog' });
    const [, row] = within(table).getAllByRole('row');
    const link = within(row as HTMLElement).getByRole('link');
    expect(link.firstElementChild).toHaveTextContent('title of x-10');
    expect(link.lastElementChild).toHaveTextContent('x-10');
    expect(link.lastElementChild).toHaveClass('key');
    const [first] = within(table).getAllByRole('columnheader');
    expect(first).toHaveTextContent('Title');
    const session = await screen.findByRole('table', { name: 'open one' });
    const holder = await within(session).findByText('(x-S2)');
    expect(holder).toHaveClass('key');
    expect(holder.parentElement).toHaveTextContent(/^open one \(x-S2\)$/);
  });
});
