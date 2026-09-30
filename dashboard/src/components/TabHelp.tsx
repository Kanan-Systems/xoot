// A one-line "What is this?" under a tab's heading, collapsed by default,
// ending with a link to the concepts page on GitHub. The link opens a new
// tab without an opener or a referrer; it is a navigation, so the CSP's
// connect-src does not apply to it.
import { useId, useState } from 'react';

export const CONCEPTS_URL =
  'https://github.com/Kanan-Systems/xoot/blob/main/docs/concepts.md';

export const TAB_HELP = {
  tree:
    'The project holds goals, goals hold batches, batches hold subtasks; backlog ' +
    'hangs off the batch, goal or project it sits on. Goals and batches complete ' +
    'on their own once their work is done and no backlog is open. Click an item ' +
    'for details.',
  backlog:
    'Open work found along the way, by level: on a batch, on a goal, then the ' +
    'project backlog. Open backlog keeps its batch or goal from completing until ' +
    'it is covered, resolved or pushed up.',
  decisions:
    'Recorded choices and why they were made, grouped by goal, batch and subtask; ' +
    'each belongs to the item it was made on. Superseded ones link to their ' +
    'replacement.',
} as const;

export function TabHelp({ tab }: { tab: keyof typeof TAB_HELP }) {
  const [open, setOpen] = useState(false);
  const panel = useId();
  return (
    <div className="tab-help">
      <button
        type="button"
        className="help-toggle"
        aria-expanded={open}
        aria-controls={panel}
        onClick={() => {
          setOpen(!open);
        }}
      >
        <span aria-hidden="true">{open ? '▾' : '▸'}</span> What is this?
      </button>
      {open && (
        <p id={panel} className="muted help-text">
          {TAB_HELP[tab]}{' '}
          <a href={CONCEPTS_URL} target="_blank" rel="noopener noreferrer">
            Concepts
          </a>
        </p>
      )}
    </div>
  );
}
