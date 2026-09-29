// The legend toggle: what the kind icons and the seven category colour,
// icon and label pairs mean, and what a session is.
import { useId, useState } from 'react';

import type { Category, ItemKind } from '../api/types.gen.ts';
import { CATEGORY, categoryClass, KIND } from '../lib/display.ts';

const KINDS: readonly ItemKind[] = ['goal', 'batch', 'subtask'];
const CATEGORIES = Object.keys(CATEGORY) as Category[];

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
          <p className="muted">A goal holds batches; a batch holds subtasks.</p>
          <ul className="list">
            {KINDS.map((kind) => (
              <li key={kind}>
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
          <h2>Sessions</h2>
          <p className="muted">
            A session is one working sitting. It links every item it focused on, touched
            or captured, and its close gives each open one a disposition.
          </p>
        </section>
      )}
    </div>
  );
}
