// One backlog group's table. The title cell is a link that opens the drawer;
// it is stretched over the row, so a click anywhere on the row opens it too.
// Title first, then the key; "found on" is the item's title with its key.
import { Link } from 'react-router-dom';

import type { BacklogRow } from '../api/types.gen.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { categoryClass, categoryGlyph, when } from '../lib/display.ts';
import type { Titles } from '../lib/titles.ts';
import { KeyLabel, KeyTag, TitleText } from './Titled.tsx';

interface BacklogTableProps {
  caption: string;
  rows: readonly BacklogRow[];
  titles: Titles;
}

export function BacklogTable({ caption, rows, titles }: BacklogTableProps) {
  const { hrefFor } = useDrawer();
  return (
    <table className="items">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Title</th>
          <th scope="col">Key</th>
          <th scope="col">State</th>
          <th scope="col">Found on</th>
          <th scope="col">Why</th>
          <th scope="col">Created</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const category = categoryGlyph(row.category);
          return (
            <tr key={row.key} className="row row-backlog">
              <td className="cell-title">
                <Link className="row-link" to={hrefFor(row.key)}>
                  <span aria-hidden="true">⚑</span> <TitleText title={row.title} />
                </Link>
              </td>
              <td>
                <KeyTag value={row.key} />
              </td>
              <td>
                <span className={categoryClass(row.category)}>
                  <span aria-hidden="true">{category.icon}</span> {row.state}
                </span>
              </td>
              <td>
                {row.found_on === null ? (
                  '—'
                ) : (
                  <KeyLabel itemKey={row.found_on} titles={titles} />
                )}
              </td>
              <td className="cell-why">{row.why === '' ? '—' : row.why}</td>
              <td>{when(row.created_at)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
