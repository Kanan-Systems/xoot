// The decisions list: title (key second), status chip, the scoped item
// (opens the drawer) and supersede links, each shown as "title (key)". A
// body loads when its row is expanded and is shown as plain text.
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useDecision } from '../api/queries.ts';
import type { DecisionSummary } from '../api/types.gen.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { DECISION_STATUS } from '../lib/display.ts';
import type { Titles } from '../lib/titles.ts';
import { QueryState } from './QueryState.tsx';
import { KeyLabel, KeyTag, TitleText } from './Titled.tsx';

export function anchorOf(key: string): string {
  return `decision-${key}`;
}

// Which decision supersedes each one, from the supersedes links.
export function supersededBy(
  decisions: readonly DecisionSummary[],
): Map<string, string> {
  const next = new Map<string, string>();
  for (const decision of decisions) {
    if (decision.supersedes !== null) {
      next.set(decision.supersedes, decision.key);
    }
  }
  return next;
}

interface DecisionsSectionProps {
  decisions: readonly DecisionSummary[];
  successors: ReadonlyMap<string, string>;
  titles: Titles;
}

export function DecisionsSection({
  decisions,
  successors,
  titles,
}: DecisionsSectionProps) {
  if (decisions.length === 0) {
    return <p className="muted">No decisions match.</p>;
  }
  return (
    <ul className="decision-list">
      {decisions.map((decision) => (
        <DecisionRow
          key={decision.key}
          decision={decision}
          successor={successors.get(decision.key) ?? null}
          titles={titles}
        />
      ))}
    </ul>
  );
}

interface DecisionRowProps {
  decision: DecisionSummary;
  successor: string | null;
  titles: Titles;
}

function DecisionRow({ decision, successor, titles }: DecisionRowProps) {
  const [expanded, setExpanded] = useState(false);
  const { hrefFor } = useDrawer();
  const status = DECISION_STATUS[decision.status];
  const bodyId = `${anchorOf(decision.key)}-body`;
  return (
    <li id={anchorOf(decision.key)} className="decision-row">
      <div className="decision-head">
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={bodyId}
          onClick={() => {
            setExpanded(!expanded);
          }}
        >
          <span aria-hidden="true">{expanded ? '▾' : '▸'}</span>{' '}
          <span className="decision-title">
            <TitleText title={decision.title} />
          </span>{' '}
          <KeyTag value={decision.key} />
        </button>
        <span className={`chip chip-${decision.status}`}>
          <span aria-hidden="true">{status.icon}</span> {status.label}
        </span>
        {decision.scope !== null && (
          <span>
            Scope:{' '}
            <Link to={hrefFor(decision.scope)}>
              <KeyLabel itemKey={decision.scope} titles={titles} />
            </Link>
          </span>
        )}
        {decision.supersedes !== null && (
          <span>
            Supersedes{' '}
            <a href={`#${anchorOf(decision.supersedes)}`}>
              <KeyLabel itemKey={decision.supersedes} titles={titles} />
            </a>
          </span>
        )}
        {successor !== null && (
          <span>
            Superseded by{' '}
            <a href={`#${anchorOf(successor)}`}>
              <KeyLabel itemKey={successor} titles={titles} />
            </a>
          </span>
        )}
      </div>
      {expanded && (
        <div id={bodyId}>
          <DecisionBody decisionKey={decision.key} />
        </div>
      )}
    </li>
  );
}

function DecisionBody({ decisionKey }: { decisionKey: string }) {
  const query = useDecision(decisionKey, true);
  return (
    <QueryState query={query} what="decision">
      {(view) => <pre className="body">{view.decision.body}</pre>}
    </QueryState>
  );
}
