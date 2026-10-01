// /:project/backlog: every open backlog item, grouped goal > batch, then
// the project backlog; filterable by goal (?goal=) and batch (?batch=),
// each showing only that group, or saying it has no open backlog. Values
// that name no goal or batch of the project are ignored.
import { useParams, useSearchParams } from 'react-router-dom';

import { useBacklog, useTree } from '../api/queries.ts';
import { BacklogsSection } from '../components/BacklogsSection.tsx';
import { Disclosure } from '../components/Disclosure.tsx';
import { Filter } from '../components/Filter.tsx';
import { QueryState } from '../components/QueryState.tsx';
import { TabHelp } from '../components/TabHelp.tsx';
import { useCollapsed } from '../hooks/useCollapsed.ts';
import { useTitles } from '../hooks/useTitles.ts';
import { filterChoices, holdersOf, validFilter } from '../lib/backlogGroups.ts';
import { PARAM, withParam } from '../lib/search.ts';
import { labelOf } from '../lib/titles.ts';

function ActionsHelp() {
  return (
    <Disclosure label="About Cover and Push up">
      {() => (
        <dl className="facts actions-help">
          <dt>Cover</dt>
          <dd>
            Turn a backlog item into a subtask in a batch you choose. The backlog item
            is then closed, and the new subtask carries the work.
          </dd>
          <dt>Push up</dt>
          <dd>
            Move an item one level up: from a batch to its goal, or from a goal to the
            project. Nothing is closed; it waits there instead.
          </dd>
        </dl>
      )}
    </Disclosure>
  );
}

export function BacklogPage() {
  const { project = '' } = useParams();
  const [search, setSearch] = useSearchParams();
  const query = useBacklog(project);
  const tree = useTree(project);
  const titles = useTitles(project);
  const collapsed = useCollapsed(project, 'backlog');
  return (
    <div className="view">
      <h1 className="view-title">Backlog</h1>
      <TabHelp tab="backlog" />
      <ActionsHelp />
      <QueryState query={query} what="backlog">
        {(view) => {
          const filter = validFilter(
            view,
            search.get(PARAM.goal),
            search.get(PARAM.batch),
            holdersOf(tree.data?.nodes ?? []),
          );
          const choices = filterChoices(view, filter);
          const choose = (value: string | null) => ({
            value: value ?? '',
            label: value === null ? '' : labelOf(value, titles),
          });
          return (
            <>
              <div className="filters" role="group" aria-label="Filter backlog">
                <Filter
                  label="Goal"
                  value={filter.goal}
                  options={choices.goals.map(choose)}
                  onChange={(goal) => {
                    // A batch of another goal would be ignored anyway.
                    const kept = new URLSearchParams(
                      withParam(search, PARAM.batch, null),
                    );
                    setSearch(new URLSearchParams(withParam(kept, PARAM.goal, goal)));
                  }}
                />
                <Filter
                  label="Batch"
                  value={filter.batch}
                  options={choices.batches.map(choose)}
                  onChange={(batch) => {
                    setSearch(
                      new URLSearchParams(withParam(search, PARAM.batch, batch)),
                    );
                  }}
                />
              </div>
              <BacklogsSection
                prefix={project}
                view={view}
                titles={titles}
                filter={filter}
                collapsed={collapsed.keys}
                onToggle={collapsed.toggle}
              />
            </>
          );
        }}
      </QueryState>
    </div>
  );
}
