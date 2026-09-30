// /:project/decisions: full width, grouped goal > batch > subtask,
// filterable by goal (?goal=), owner level (?level=) and status (?status=).
import { useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { useDecisions } from '../api/queries.ts';
import type { DecisionStatus } from '../api/types.gen.ts';
import { DecisionHierarchy } from '../components/DecisionHierarchy.tsx';
import { Filter } from '../components/Filter.tsx';
import { QueryState } from '../components/QueryState.tsx';
import { TabHelp } from '../components/TabHelp.tsx';
import { useCollapsed } from '../hooks/useCollapsed.ts';
import { useTitles } from '../hooks/useTitles.ts';
import {
  decisionGoals,
  decisionHierarchy,
  supersededBy,
  type DecisionFilter,
} from '../lib/decisionGroups.ts';
import { DECISION_STATUS, OWNER_LEVEL } from '../lib/display.ts';
import type { OwnerLevel } from '../lib/keys.ts';
import { PARAM, withParam } from '../lib/search.ts';
import { labelOf } from '../lib/titles.ts';

const STATUSES = Object.keys(DECISION_STATUS) as DecisionStatus[];
const LEVELS = Object.keys(OWNER_LEVEL) as OwnerLevel[];

function oneOf<T extends string>(
  options: readonly T[],
  value: string | null,
): T | null {
  return options.find((option) => option === value) ?? null;
}

export function DecisionsPage() {
  const { project = '' } = useParams();
  const [search, setSearch] = useSearchParams();
  const query = useDecisions(project);
  const titles = useTitles(project);
  const collapsed = useCollapsed(project, 'decisions');
  const decisions = useMemo(() => query.data?.decisions ?? [], [query.data]);
  const successors = useMemo(() => supersededBy(decisions), [decisions]);
  const goals = useMemo(() => decisionGoals(decisions), [decisions]);
  const filter: DecisionFilter = {
    goal: search.get(PARAM.goal),
    level: oneOf(LEVELS, search.get(PARAM.level)),
    status: oneOf(STATUSES, search.get(PARAM.status)),
  };
  const set = (name: string) => (value: string | null) => {
    setSearch(new URLSearchParams(withParam(search, name, value)));
  };
  return (
    <div className="view">
      <h1 className="view-title">Decisions</h1>
      <TabHelp tab="decisions" />
      <div className="filters" role="group" aria-label="Filter decisions">
        <Filter
          label="Goal"
          value={filter.goal}
          options={goals.map((goal) => ({ value: goal, label: labelOf(goal, titles) }))}
          onChange={set(PARAM.goal)}
        />
        <Filter
          label="Level"
          value={filter.level}
          options={LEVELS.map((level) => ({ value: level, label: OWNER_LEVEL[level] }))}
          onChange={set(PARAM.level)}
        />
        <Filter
          label="Status"
          value={filter.status}
          options={STATUSES.map((s) => ({ value: s, label: DECISION_STATUS[s].label }))}
          onChange={set(PARAM.status)}
        />
      </div>
      <QueryState query={query} what="decisions">
        {(view) => {
          const hierarchy = decisionHierarchy(view.decisions, filter);
          const none = hierarchy.goals.length === 0 && hierarchy.ownerless.length === 0;
          return (
            <>
              {view.decisions.length === 0 ? (
                <p className="muted">No decisions recorded yet</p>
              ) : (
                none && <p className="muted">No decisions match.</p>
              )}
              <DecisionHierarchy
                prefix={project}
                hierarchy={hierarchy}
                successors={successors}
                titles={titles}
                collapsed={collapsed.keys}
                onToggle={collapsed.toggle}
              />
              {view.truncated && (
                <p className="warning">Only the newest 500 are shown.</p>
              )}
            </>
          );
        }}
      </QueryState>
    </div>
  );
}
