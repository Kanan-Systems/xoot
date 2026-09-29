import { fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { DecisionView } from '../api/types.gen.ts';
import { mockApi, projectRoutes } from '../test/api.ts';
import { renderApp } from '../test/renderApp.tsx';

const BODY = '<script>alert(1)</script>\n  kept as text';

function decisionView(): DecisionView {
  return {
    decision: {
      key: 'x-D1',
      title: 'old rule',
      status: 'superseded',
      scope: null,
      supersedes: null,
      version: 1,
      updated_at: 't',
      created_at: 't',
      body: BODY,
    },
  };
}

function row(key: string): HTMLElement {
  const element = document.getElementById(`decision-${key}`);
  if (element === null) {
    throw new Error(`no row ${key}`);
  }
  return element;
}

describe('the decisions view', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockApi(projectRoutes({ '/decisions/x-D1': decisionView() }));
  });

  it('expands a body inline as plain text', async () => {
    renderApp('/x/decisions');
    const toggle = await screen.findByRole('button', { name: /x-D1/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const body = await within(row('x-D1')).findByText(/kept as text/);
    expect(body.tagName).toBe('PRE');
    expect(body.textContent).toBe(BODY);
    expect(document.querySelector('.decision-list script')).toBeNull();
  });

  it('links supersedes both ways, with a status chip and the scope', async () => {
    renderApp('/x/decisions');
    await screen.findByRole('button', { name: /x-D2/ });
    const newer = within(row('x-D2'));
    expect(newer.getByRole('link', { name: 'x-D1' })).toHaveAttribute(
      'href',
      '#decision-x-D1',
    );
    expect(newer.getByText('Locked')).toHaveClass('chip');
    expect(newer.getByRole('link', { name: 'x-1' })).toHaveAttribute(
      'href',
      '/x/decisions?item=x-1',
    );
    const older = within(row('x-D1'));
    expect(older.getByText(/Superseded by/)).toBeInTheDocument();
    expect(older.getByRole('link', { name: 'x-D2' })).toHaveAttribute(
      'href',
      '#decision-x-D2',
    );
  });

  it('filters by status', async () => {
    renderApp('/x/decisions');
    await screen.findByRole('button', { name: /x-D2/ });
    fireEvent.change(screen.getByRole('combobox', { name: 'Status' }), {
      target: { value: 'deferred' },
    });
    expect(await screen.findByRole('button', { name: /x-D3/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /x-D2/ })).toBeNull();
  });
});
