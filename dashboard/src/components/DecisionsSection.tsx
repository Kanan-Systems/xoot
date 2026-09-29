// The project's decisions; a body is fetched only when its entry is opened.
import { useState } from 'react';

import { useDecision, useDecisions } from '../api/queries.ts';
import type { DecisionSummary } from '../api/types.gen.ts';
import { QueryState } from './QueryState.tsx';

export function DecisionsSection({ prefix }: { prefix: string }) {
  const query = useDecisions(prefix);
  return (
    <section aria-labelledby="decisions-heading">
      <h2 id="decisions-heading">Decisions</h2>
      <QueryState query={query} what="decisions">
        {(view) => (
          <ul className="list">
            {view.decisions.map((decision) => (
              <li key={decision.key}>
                <DecisionEntry decision={decision} />
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </section>
  );
}

function DecisionEntry({ decision }: { decision: DecisionSummary }) {
  const [open, setOpen] = useState(false);
  const detail = useDecision(decision.key, open);
  return (
    <details
      onToggle={(event) => {
        setOpen(event.currentTarget.open);
      }}
    >
      <summary>
        {decision.key} ({decision.status}): {decision.title}
      </summary>
      {open && (
        <QueryState query={detail} what="decision">
          {(view) => <pre className="body">{view.decision.body}</pre>}
        </QueryState>
      )}
    </details>
  );
}
