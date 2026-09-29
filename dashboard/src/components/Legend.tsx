// The legend toggle: the four kinds (icon and word), the six category
// colour, icon and label triples, and what blocked and completed mean.
import { useId, useState } from 'react';

import { CATEGORIES, CATEGORY, categoryClass, KIND, KINDS } from '../lib/display.ts';

export function Legend() {
  const [open, setOpen] = useState(false);
  const panel = useId();
  return (
    <div className="legend">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panel}
        onClick={() => {
          setOpen(!open);
        }}
      >
        Legend
      </button>
      {open && (
        <section id={panel} className="legend-panel" aria-label="Legend">
          <h2>Kinds</h2>
          <p className="muted">
            A goal holds batches; a batch holds subtasks. Backlog is open work found
            along the way, on a batch, a goal or the project.
          </p>
          <ul className="list">
            {KINDS.map((kind) => (
              <li
                key={kind}
                className={kind === 'backlog' ? 'legend-backlog' : undefined}
              >
                <span aria-hidden="true">{KIND[kind].icon}</span> {KIND[kind].label}
              </li>
            ))}
          </ul>
          <h2>States</h2>
          <ul className="list">
            {CATEGORIES.map((category) => (
              <li key={category}>
                <span className={categoryClass(category)}>
                  <span aria-hidden="true">{CATEGORY[category].icon}</span>{' '}
                  {CATEGORY[category].label}
                </span>
              </li>
            ))}
          </ul>
          <h2>Completion</h2>
          <p className="muted">
            Goals and batches complete on their own when every child is done or dropped
            and no backlog is open on them. Open backlog blocks completion: such a node
            says how much is open.
          </p>
        </section>
      )}
    </div>
  );
}
