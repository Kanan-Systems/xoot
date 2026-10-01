// One backlog group's rows, as a list under its heading like the Decisions
// tab's, not a boxed table per group. The title is a link that opens the
// drawer; it is stretched over the row, so a click anywhere on the row
// opens it too, except on the actions.
import type { BacklogRow as Row } from '../api/types.gen.ts';
import type { Titles } from '../lib/titles.ts';
import { BacklogRow } from './BacklogRow.tsx';

interface BacklogListProps {
  prefix: string;
  // Names the list for assistive technology: the group it belongs to.
  label: string;
  rows: readonly Row[];
  titles: Titles;
  onDone: (message: string) => void;
}

export function BacklogList({ prefix, label, rows, titles, onDone }: BacklogListProps) {
  return (
    <ul className="backlog-list" aria-label={label}>
      {rows.map((row) => (
        <BacklogRow
          key={row.key}
          prefix={prefix}
          row={row}
          titles={titles}
          onDone={onDone}
        />
      ))}
    </ul>
  );
}
