// Each open session's backlog, then the project backlog, then unfiled.
import { Link } from 'react-router-dom';

import type { BacklogsView, ItemSummary } from '../api/types.gen.ts';
import { categoryGlyph } from '../lib/display.ts';

interface BacklogsSectionProps {
  prefix: string;
  view: BacklogsView;
}

export function BacklogsSection({ prefix, view }: BacklogsSectionProps) {
  return (
    <>
      {view.sessions.map((entry) => (
        <ItemList
          key={entry.session.key}
          prefix={prefix}
          title={`${entry.session.key} (open): ${entry.session.title}`}
          items={entry.items}
          truncated={entry.truncated}
        />
      ))}
      <ItemList
        prefix={prefix}
        title="Project backlog"
        items={view.project_backlog}
        truncated={view.project_backlog_truncated}
      />
      <ItemList
        prefix={prefix}
        title="Unfiled"
        items={view.unfiled}
        truncated={view.unfiled_truncated}
      />
    </>
  );
}

interface ItemListProps {
  prefix: string;
  title: string;
  items: readonly ItemSummary[];
  truncated: boolean;
}

function ItemList({ prefix, title, items, truncated }: ItemListProps) {
  return (
    <details className="backlog" open={items.length > 0}>
      <summary>
        {title} ({items.length}
        {truncated ? '+' : ''})
      </summary>
      {items.length === 0 ? (
        <p className="muted">Empty.</p>
      ) : (
        <ul className="list">
          {items.map((item) => (
            <li key={item.key}>
              <Link to={`/${prefix}/item/${item.key}`}>
                <span aria-hidden="true">{categoryGlyph(item.category).icon}</span>{' '}
                {item.key}: {item.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
