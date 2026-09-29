// The detail drawer, shared by every view: full height on the right, closed
// by its button or Escape. Every stored string is rendered as a text node:
// bodies keep their whitespace in <pre>, nothing is parsed as markdown or
// HTML.
import { useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useItem } from '../api/queries.ts';
import type { EventEntry, ItemView } from '../api/types.gen.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { categoryClass, categoryGlyph, DECISION_STATUS, KIND } from '../lib/display.ts';
import { PARAM, withParam } from '../lib/search.ts';
import { QueryState } from './QueryState.tsx';

export function DetailPanel({ prefix }: { prefix: string }) {
  const { itemKey, close } = useDrawer();
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (itemKey === null) {
      return undefined;
    }
    closeButton.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [itemKey, close]);
  if (itemKey === null) {
    return null;
  }
  return (
    <aside className="drawer" aria-label={`Details of ${itemKey}`}>
      <button ref={closeButton} type="button" className="drawer-close" onClick={close}>
        ✕ Close
      </button>
      <DrawerItem prefix={prefix} itemKey={itemKey} />
    </aside>
  );
}

function DrawerItem({ prefix, itemKey }: { prefix: string; itemKey: string }) {
  const query = useItem(itemKey);
  return (
    <QueryState query={query} what="item">
      {(view) => <ItemDetails prefix={prefix} view={view} />}
    </QueryState>
  );
}

export function ItemDetails({ prefix, view }: { prefix: string; view: ItemView }) {
  const { item } = view;
  const { hrefFor } = useDrawer();
  const navigate = useNavigate();
  const category = categoryGlyph(item.category);
  const focusable = item.kind === 'goal' || item.kind === 'batch';
  return (
    <>
      <h2>
        <span aria-hidden="true">{KIND[item.kind].icon}</span> {KIND[item.kind].label}{' '}
        {item.key}
      </h2>
      <p className="detail-title">{item.title}</p>
      {focusable && (
        <button
          type="button"
          className="action"
          onClick={() => {
            void navigate(`/${prefix}/focus/${item.key}`);
          }}
        >
          ⌖ Focus on this {item.kind}
        </button>
      )}
      <dl className="facts">
        <dt>State</dt>
        <dd>
          <span className={categoryClass(item.category)}>
            <span aria-hidden="true">{category.icon}</span> {item.state} (
            {category.label})
          </span>
        </dd>
        <dt>Version</dt>
        <dd>{item.version}</dd>
        <dt>Parent</dt>
        <dd>
          {item.parent === null ? (
            'none'
          ) : (
            <Link to={hrefFor(item.parent)}>{item.parent}</Link>
          )}
        </dd>
      </dl>
      <h3>Body</h3>
      {item.body === '' ? (
        <p className="muted">No body.</p>
      ) : (
        <pre className="body">{item.body}</pre>
      )}
      <h3>Sessions</h3>
      {view.sessions.length === 0 ? (
        <p className="muted">Not linked to any session.</p>
      ) : (
        <ul>
          {view.sessions.map((session) => (
            <li key={session.key}>
              <Link
                to={{
                  pathname: `/${prefix}/sessions`,
                  search: withParam(new URLSearchParams(), PARAM.session, session.key),
                }}
              >
                {session.key}
              </Link>{' '}
              ({session.status}): {session.title}
            </li>
          ))}
        </ul>
      )}
      <h3>Decisions</h3>
      {view.decisions.length === 0 ? (
        <p className="muted">No decisions scoped here.</p>
      ) : (
        view.decisions.map((decision) => (
          <article key={decision.key} className="decision">
            <h4>
              {decision.key} ({DECISION_STATUS[decision.status].label}):{' '}
              {decision.title}
            </h4>
            <pre className="body">{decision.body}</pre>
          </article>
        ))
      )}
      <h3>Recent history</h3>
      <ol className="history">
        {view.events.map((event, index) => (
          <li key={`${event.created_at}-${String(index)}`}>{describe(event)}</li>
        ))}
      </ol>
    </>
  );
}

function describe(event: EventEntry): string {
  const who = `${event.actor_kind}/${event.client}`;
  const where = event.session === null ? '' : ` in ${event.session}`;
  const what = event.changed.length > 0 ? `: ${event.changed.join(', ')}` : '';
  const redacted = event.redacted ? ' (redacted)' : '';
  return `${event.created_at} ${event.action} by ${who}${where}${what}${redacted}`;
}
