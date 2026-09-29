// A table of items. The title cell (title first, key after it) is a link that
// opens the drawer; it is stretched over the row, so a click anywhere on the
// row opens it too.
import { Link } from 'react-router-dom';

import type { ItemSummary } from '../api/types.gen.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { categoryClass, categoryGlyph, KIND } from '../lib/display.ts';
import { NO_TITLES, type Titles } from '../lib/titles.ts';
import { KeyLabel, Titled } from './Titled.tsx';

export type ItemRow = ItemSummary & { created_at?: string };

interface ItemTableProps {
  caption: string;
  rows: readonly ItemRow[];
  holder?: boolean;
  created?: boolean;
  titles?: Titles;
}

export function ItemTable({
  caption,
  rows,
  holder = false,
  created = false,
  titles = NO_TITLES,
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
          <th scope="col">Title</th>
          <th scope="col">Kind</th>
          <th scope="col">State</th>
          {holder && <th scope="col">Held by</th>}
          {created && <th scope="col">Created</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const category = categoryGlyph(row.category);
          return (
            <tr key={row.key} className="row">
              <td className="cell-title">
                <Link className="row-link" to={hrefFor(row.key)}>
                  <Titled title={row.title} itemKey={row.key} />
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
              {holder && (
                <td>
                  {row.backlog_session === null ? (
                    '—'
                  ) : (
                    <KeyLabel itemKey={row.backlog_session} titles={titles} />
                  )}
                </td>
              )}
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
