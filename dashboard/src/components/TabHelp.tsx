// A one-line "What is this?" under a tab's heading, collapsed by default,
// ending with a link to the concepts page on GitHub. The link opens a new
// tab without an opener or a referrer; it is a navigation, so the CSP's
// connect-src does not apply to it.
import { useId, useState } from 'react';

export const CONCEPTS_URL =
  'https://github.com/Kanan-Systems/xoot/blob/main/docs/concepts.md';

export const TAB_HELP = {
  tree: 'Goals hold batches, batches hold subtasks; click an item for details.',
  sessions:
    'Each working session with Claude, what it covered and what it left behind.',
  backlog: 'Parked items: per open session, project-wide, and unfiled.',
  decisions:
    'Recorded choices and why they were made; superseded ones link to their replacement.',
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
