// One heading's decisions: title (key second), status chip, the owner's
// level and title (opens the drawer) and supersede links, each shown as
// "title (key)". A body loads when its row is expanded and is shown as plain
// text. Edit opens the decision's title, body and status in place.
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useDecision } from '../api/queries.ts';
import type { DecisionSummary } from '../api/types.gen.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { DECISION_STATUS, OWNER_LEVEL } from '../lib/display.ts';
import { ownerLevel } from '../lib/keys.ts';
import type { Titles } from '../lib/titles.ts';
import { DecisionEditor } from './DecisionForms.tsx';
import { QueryState } from './QueryState.tsx';
import { KeyLabel, KeyTag, TitleText } from './Titled.tsx';

export function anchorOf(key: string): string {
  return `decision-${key}`;
}

interface DecisionsSectionProps {
  prefix: string;
  decisions: readonly DecisionSummary[];
  successors: ReadonlyMap<string, string>;
  titles: Titles;
}

export function DecisionsSection({
  prefix,
  decisions,
  successors,
  titles,
}: DecisionsSectionProps) {
  return (
    <ul className="decision-list">
      {decisions.map((decision) => (
        <DecisionRow
          key={decision.key}
          prefix={prefix}
          decision={decision}
          successor={successors.get(decision.key) ?? null}
          titles={titles}
        />
      ))}
    </ul>
  );
}

interface DecisionRowProps {
  prefix: string;
  decision: DecisionSummary;
  successor: string | null;
  titles: Titles;
}

function DecisionRow({ prefix, decision, successor, titles }: DecisionRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [notice, setNotice] = useState('');
  const { hrefFor } = useDrawer();
  const status = DECISION_STATUS[decision.status];
  const level = decision.owner === null ? null : ownerLevel(decision.owner);
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
        {decision.owner === null ? (
          <span className="muted">Owner gone</span>
        ) : (
          <span>
            {level === null ? 'Owner' : OWNER_LEVEL[level]}:{' '}
            <Link to={hrefFor(decision.owner)}>
              <KeyLabel itemKey={decision.owner} titles={titles} />
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
        <button
          type="button"
          aria-expanded={editing}
          aria-label={`Edit ${decision.key}`}
          onClick={() => {
            setNotice('');
            setEditing(!editing);
          }}
        >
          Edit
        </button>
        <span role="status" className="notice">
          {notice}
        </span>
      </div>
      {editing && (
        <DecisionEditor
          prefix={prefix}
          decisionKey={decision.key}
          onDone={(message) => {
            setEditing(false);
            setNotice(message);
          }}
          onCancel={() => {
            setEditing(false);
          }}
        />
      )}
      {expanded && (
        <div id={bodyId}>
          <DecisionBody prefix={prefix} decisionKey={decision.key} />
        </div>
      )}
    </li>
  );
}

function DecisionBody({
  prefix,
  decisionKey,
}: {
  prefix: string;
  decisionKey: string;
}) {
  const query = useDecision(prefix, decisionKey, true);
  return (
    <QueryState query={query} what="decision">
      {(view) => <pre className="body">{view.decision.body}</pre>}
    </QueryState>
  );
}
