// A table of items. The key cell is a link that opens the drawer; it is
// stretched over the row, so a click anywhere on the row opens it too.
import { Link } from 'react-router-dom';

import type { ItemSummary } from '../api/types.gen.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { categoryClass, categoryGlyph, KIND } from '../lib/display.ts';

export type ItemRow = ItemSummary & { created_at?: string };

interface ItemTableProps {
  caption: string;
  rows: readonly ItemRow[];
  holder?: boolean;
  created?: boolean;
}

export function ItemTable({
  caption,
  rows,
  holder = false,
  created = false,
}: ItemTableProps) {
  const { hrefFor } = useDrawer();
  if (rows.length === 0) {
    return <p className="muted">{caption}: none.</p>;
  }
  return (
    <table className="items">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Key</th>
          <th scope="col">Kind</th>
          <th scope="col">State</th>
          <th scope="col">Title</th>
          {holder && <th scope="col">Held by</th>}
          {created && <th scope="col">Created</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const category = categoryGlyph(row.category);
          return (
            <tr key={row.key} className="row">
              <td>
                <Link className="row-link" to={hrefFor(row.key)}>
                  {row.key}
                </Link>
              </td>
              <td>
                <span aria-hidden="true">{KIND[row.kind].icon}</span>{' '}
                {KIND[row.kind].label}
              </td>
              <td>
                <span className={categoryClass(row.category)}>
                  <span aria-hidden="true">{category.icon}</span> {row.state}
                </span>
              </td>
              <td className="cell-title">{row.title}</td>
              {holder && <td>{row.backlog_session ?? '—'}</td>}
              {created && (
                <td>{row.created_at?.slice(0, 16).replace('T', ' ') ?? '—'}</td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
