// One backlog group's table. The title cell is a link that opens the drawer;
// it is stretched over the row, so a click anywhere on the row opens it too,
// except on the actions. Title first, then the key; "found on" is the item's
// title with its key.
import type { BacklogRow as Row } from '../api/types.gen.ts';
import type { Titles } from '../lib/titles.ts';
import { BacklogRow } from './BacklogRow.tsx';

interface BacklogTableProps {
  prefix: string;
  caption: string;
  rows: readonly Row[];
  titles: Titles;
  onDone: (message: string) => void;
}

export function BacklogTable({
  prefix,
  caption,
  rows,
  titles,
  onDone,
}: BacklogTableProps) {
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
          <th scope="col">Actions</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <BacklogRow
            key={row.key}
            prefix={prefix}
            row={row}
            titles={titles}
            onDone={onDone}
          />
        ))}
      </tbody>
    </table>
  );
}
