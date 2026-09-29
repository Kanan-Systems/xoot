// The top bar: project switcher, goal selector, view tabs, legend and the
// live indicator.
import { NavLink, useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import { useProjects, useTree } from '../api/queries.ts';
import { truncate } from '../lib/display.ts';
import { PARAM, withParam } from '../lib/search.ts';
import { LastUpdated } from './LastUpdated.tsx';
import { Legend } from './Legend.tsx';

const TABS = [
  { path: 'tree', label: 'Tree' },
  { path: 'sessions', label: 'Sessions' },
  { path: 'backlog', label: 'Backlog' },
  { path: 'decisions', label: 'Decisions' },
] as const;

interface TopBarProps {
  prefix: string;
  checkedAt: number;
  failing: boolean;
}

export function TopBar({ prefix, checkedAt, failing }: TopBarProps) {
  const { pathname } = useLocation();
  const onTree = (path: string) =>
    path === 'tree' && pathname.startsWith(`/${prefix}/focus/`);
  return (
    <header className="topbar">
      <h1>xoot</h1>
      <ProjectSwitcher prefix={prefix} />
      <GoalSelector prefix={prefix} />
      <nav aria-label="Views" className="tabs">
        {TABS.map((tab) => (
          <NavLink
            key={tab.path}
            to={`/${prefix}/${tab.path}`}
            className={({ isActive }) =>
              isActive || onTree(tab.path) ? 'tab tab-active' : 'tab'
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Legend />
      <LastUpdated checkedAt={checkedAt} failing={failing} />
    </header>
  );
}

function ProjectSwitcher({ prefix }: { prefix: string }) {
  const projects = useProjects();
  const navigate = useNavigate();
  const listed = projects.data?.projects ?? [
    { key_prefix: prefix, name: prefix, aliases: [] },
  ];
  return (
    <label className="control">
      Project{' '}
      <select
        value={prefix}
        onChange={(event) => {
          void navigate(`/${event.target.value}/tree`);
        }}
      >
        {listed.map((project) => (
          <option key={project.key_prefix} value={project.key_prefix}>
            {project.name} ({project.key_prefix})
          </option>
        ))}
      </select>
    </label>
  );
}

// "All goals" or one goal; a goal becomes the tree's root.
function GoalSelector({ prefix }: { prefix: string }) {
  const tree = useTree(prefix);
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const goals = (tree.data?.nodes ?? []).filter(
    (entry) => entry.depth === 0 && !entry.unfiled && entry.item.kind === 'goal',
  );
  return (
    <label className="control">
      Goal{' '}
      <select
        value={search.get(PARAM.goal) ?? ''}
        onChange={(event) => {
          const goal = event.target.value === '' ? null : event.target.value;
          const kept = withParam(search, PARAM.item, null);
          void navigate({
            pathname: `/${prefix}/tree`,
            search: withParam(new URLSearchParams(kept), PARAM.goal, goal),
          });
        }}
      >
        <option value="">All goals</option>
        {goals.map((entry) => (
          <option key={entry.item.key} value={entry.item.key}>
            {truncate(entry.item.title).text} ({entry.item.key}, {entry.item.state})
          </option>
        ))}
      </select>
    </label>
  );
}
