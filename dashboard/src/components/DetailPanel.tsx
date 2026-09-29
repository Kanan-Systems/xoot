// The detail panel of one item. Every stored string is rendered as a text
// node: bodies keep their whitespace in <pre>, nothing is parsed as markdown
// or HTML.
import { Link } from 'react-router-dom';

import { useItem } from '../api/queries.ts';
import type { EventEntry, ItemView } from '../api/types.gen.ts';
import { categoryClass, categoryGlyph, KIND } from '../lib/display.ts';
import { QueryState } from './QueryState.tsx';

interface DetailPanelProps {
  prefix: string;
  itemKey: string;
}

export function DetailPanel({ prefix, itemKey }: DetailPanelProps) {
  const query = useItem(itemKey);
  return (
    <aside className="detail" aria-label={`Details of ${itemKey}`}>
      <Link className="detail-close" to={`/${prefix}`}>
        Close
      </Link>
      <QueryState query={query} what="item">
        {(view) => <ItemDetails prefix={prefix} view={view} />}
      </QueryState>
    </aside>
  );
}

export function ItemDetails({ prefix, view }: { prefix: string; view: ItemView }) {
  const { item } = view;
  const category = categoryGlyph(item.category);
  const focusable = item.kind === 'goal' || item.kind === 'batch';
  return (
    <>
      <h2>
        <span aria-hidden="true">{KIND[item.kind].icon}</span> {item.key}
      </h2>
      <p className="detail-title">{item.title}</p>
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
            <Link to={`/${prefix}/item/${item.parent}`}>{item.parent}</Link>
          )}
        </dd>
      </dl>
      {focusable && (
        <Link to={`/${prefix}/focus/${item.key}`}>Focus on this {item.kind}</Link>
      )}
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
              {session.key} ({session.status}): {session.title}
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
              {decision.key} ({decision.status}): {decision.title}
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
