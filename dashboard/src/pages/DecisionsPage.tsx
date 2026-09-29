// /:project/decisions: full width, filterable by status (?status=).
import { useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { useDecisions } from '../api/queries.ts';
import type { DecisionStatus } from '../api/types.gen.ts';
import { DecisionsSection, supersededBy } from '../components/DecisionsSection.tsx';
import { QueryState } from '../components/QueryState.tsx';
import { TabHelp } from '../components/TabHelp.tsx';
import { useTitles } from '../hooks/useTitles.ts';
import { DECISION_STATUS } from '../lib/display.ts';
import { PARAM, withParam } from '../lib/search.ts';

const STATUSES = Object.keys(DECISION_STATUS) as DecisionStatus[];

function statusOf(value: string | null): DecisionStatus | null {
  return STATUSES.find((status) => status === value) ?? null;
}

export function DecisionsPage() {
  const { project = '' } = useParams();
  const [search, setSearch] = useSearchParams();
  const query = useDecisions(project);
  const titles = useTitles(project);
  const status = statusOf(search.get(PARAM.status));
  const successors = useMemo(
    () => supersededBy(query.data?.decisions ?? []),
    [query.data],
  );
  return (
    <div className="view">
      <h1 className="view-title">Decisions</h1>
      <TabHelp tab="decisions" />
      <label className="control">
        Status{' '}
        <select
          value={status ?? ''}
          onChange={(event) => {
            const value = event.target.value === '' ? null : event.target.value;
            setSearch(new URLSearchParams(withParam(search, PARAM.status, value)));
          }}
        >
          <option value="">All</option>
          {STATUSES.map((option) => (
            <option key={option} value={option}>
              {DECISION_STATUS[option].label}
            </option>
          ))}
        </select>
      </label>
      <QueryState query={query} what="decisions">
        {(view) => (
          <>
            <DecisionsSection
              decisions={view.decisions.filter(
                (decision) => status === null || decision.status === status,
              )}
              successors={successors}
              titles={titles}
            />
            {view.truncated && (
              <p className="warning">Only the newest 500 are shown.</p>
            )}
          </>
        )}
      </QueryState>
    </div>
  );
}
