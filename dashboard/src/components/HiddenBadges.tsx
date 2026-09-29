// The done and dropped children a node hides, one badge per category, each
// labelled with its own category so a dropped item is never counted as
// done. A click shows every closed item.
import type { MouseEvent } from 'react';

import { CATEGORY } from '../lib/display.ts';
import type { Closed, HiddenCounts } from '../lib/tree.ts';
import { useNodeActions } from './nodeActions.ts';

const ORDER: readonly Closed[] = ['done', 'dropped'];

export function HiddenBadges({ hidden }: { hidden: HiddenCounts }) {
  const actions = useNodeActions();
  const shown = ORDER.filter((category) => (hidden[category] ?? 0) > 0);
  if (shown.length === 0) {
    return null;
  }
  const onClick = (event: MouseEvent) => {
    // Inner buttons act alone: their click must not also open the drawer.
    event.stopPropagation();
    actions.showDone();
  };
  return (
    <span className="node-badges">
      {shown.map((category) => {
        const count = String(hidden[category] ?? 0);
        const label = CATEGORY[category].label.toLowerCase();
        return (
          <button
            key={category}
            type="button"
            className={`badge badge-${category}`}
            onClick={onClick}
            aria-label={`Show ${count} hidden ${label} items`}
          >
            <span aria-hidden="true">{CATEGORY[category].icon}</span> {count} {label}
          </button>
        );
      })}
    </span>
  );
}
