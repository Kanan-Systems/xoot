// /:project/decisions: full width, grouped by goal, filterable by goal
// (?goal=), owner level (?level=) and status (?status=).
import { useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { useDecisions } from '../api/queries.ts';
import type { DecisionStatus } from '../api/types.gen.ts';
import { DecisionsSection } from '../components/DecisionsSection.tsx';
import { QueryState } from '../components/QueryState.tsx';
import { TabHelp } from '../components/TabHelp.tsx';
import { KeyTag, TitleText } from '../components/Titled.tsx';
import { useTitles } from '../hooks/useTitles.ts';
import {
  decisionGoals,
  decisionGroups,
  NO_GOAL,
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

interface FilterProps {
  label: string;
  value: string | null;
  options: readonly { value: string; label: string }[];
  onChange: (value: string | null) => void;
}

function Filter({ label, value, options, onChange }: FilterProps) {
  return (
    <label className="control">
      {label}{' '}
      <select
        value={value ?? ''}
        onChange={(event) => {
          onChange(event.target.value === '' ? null : event.target.value);
        }}
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function DecisionsPage() {
  const { project = '' } = useParams();
  const [search, setSearch] = useSearchParams();
  const query = useDecisions(project);
  const titles = useTitles(project);
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
          const groups = decisionGroups(view.decisions, filter);
          return (
            <>
              {view.decisions.length === 0 ? (
                <p className="muted">No decisions recorded yet</p>
              ) : (
                groups.length === 0 && <p className="muted">No decisions match.</p>
              )}
              {groups.map((group) => (
                <section key={group.goal} aria-labelledby={`goal-${group.goal}`}>
                  <h2 id={`goal-${group.goal}`}>
                    {group.goal === NO_GOAL ? (
                      'Owner gone'
                    ) : (
                      <>
                        <TitleText title={titles.get(group.goal) ?? group.goal} />{' '}
                        <KeyTag value={group.goal} />
                      </>
                    )}{' '}
                    <span className="count">({group.decisions.length})</span>
                  </h2>
                  <DecisionsSection
                    prefix={project}
                    decisions={group.decisions}
                    successors={successors}
                    titles={titles}
                  />
                </section>
              ))}
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
