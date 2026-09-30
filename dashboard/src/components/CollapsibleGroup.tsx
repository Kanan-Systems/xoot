// A heading whose button collapses the group under it (aria-expanded and
// aria-controls), for the grouped Backlog and Decisions views. Whether it is
// open is the caller's: those views keep it per viewer in browser storage.
import { useId, type ReactNode } from 'react';

interface CollapsibleGroupProps {
  // 2 for a top group, 3 and 4 for groups inside it.
  depth: number;
  label: ReactNode;
  count: number;
  open: boolean;
  onToggle: () => void;
  className: string;
  children: ReactNode;
}

function Heading({
  depth,
  id,
  children,
}: {
  depth: number;
  id: string;
  children: ReactNode;
}) {
  if (depth === 2) {
    return <h2 id={id}>{children}</h2>;
  }
  return depth === 3 ? <h3 id={id}>{children}</h3> : <h4 id={id}>{children}</h4>;
}

export function CollapsibleGroup(props: CollapsibleGroupProps) {
  const { depth, label, count, open, onToggle, className, children } = props;
  const headingId = useId();
  const panelId = `${headingId}-panel`;
  return (
    <section
      aria-labelledby={headingId}
      className={`${className} depth-${String(depth)}`}
    >
      <Heading depth={depth} id={headingId}>
        <button
          type="button"
          className="group-toggle"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={onToggle}
        >
          <span aria-hidden="true">{open ? '▾' : '▸'}</span> {label}{' '}
          <span className="count">({count})</span>
        </button>
      </Heading>
      {open && <div id={panelId}>{children}</div>}
    </section>
  );
}
