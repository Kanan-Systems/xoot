// The sidebar: project switcher, sessions (the overlay picker), backlogs and
// decisions.
import { useNavigate } from 'react-router-dom';

import { useBacklogs, useProjects, useSessions } from '../api/queries.ts';
import { BacklogsSection } from './BacklogsSection.tsx';
import { DecisionsSection } from './DecisionsSection.tsx';
import { QueryState } from './QueryState.tsx';

interface SidebarProps {
  prefix: string;
  selectedSession: string | null;
  onSelectSession: (key: string | null) => void;
}

export function Sidebar({ prefix, selectedSession, onSelectSession }: SidebarProps) {
  return (
    <nav className="sidebar" aria-label="Project">
      <ProjectSwitcher prefix={prefix} />
      <SessionsSection
        prefix={prefix}
        selected={selectedSession}
        onSelect={onSelectSession}
      />
      <BacklogsFromApi prefix={prefix} />
      <DecisionsSection prefix={prefix} />
    </nav>
  );
}

function ProjectSwitcher({ prefix }: { prefix: string }) {
  const projects = useProjects();
  const navigate = useNavigate();
  return (
    <label className="switcher">
      Project{' '}
      <select
        value={prefix}
        onChange={(event) => {
          void navigate(`/${event.target.value}`);
        }}
      >
        {(
          projects.data?.projects ?? [{ key_prefix: prefix, name: prefix, aliases: [] }]
        ).map((project) => (
          <option key={project.key_prefix} value={project.key_prefix}>
            {project.name} ({project.key_prefix})
          </option>
        ))}
      </select>
    </label>
  );
}

interface SessionsSectionProps {
  prefix: string;
  selected: string | null;
  onSelect: (key: string | null) => void;
}

function SessionsSection({ prefix, selected, onSelect }: SessionsSectionProps) {
  const query = useSessions(prefix);
  return (
    <section aria-labelledby="sessions-heading">
      <h2 id="sessions-heading">Sessions</h2>
      <QueryState query={query} what="sessions">
        {(view) => (
          <ul className="list">
            {view.sessions.map((session) => {
              const active = session.key === selected;
              return (
                <li key={session.key}>
                  <button
                    type="button"
                    aria-pressed={active}
                    className={active ? 'selected' : undefined}
                    onClick={() => {
                      onSelect(active ? null : session.key);
                    }}
                  >
                    <span className={`status status-${session.status}`}>
                      {session.status === 'open' ? '● open' : '○ closed'}
                    </span>{' '}
                    {session.key}: {session.title}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </QueryState>
    </section>
  );
}

function BacklogsFromApi({ prefix }: { prefix: string }) {
  const query = useBacklogs(prefix);
  return (
    <section aria-labelledby="backlogs-heading">
      <h2 id="backlogs-heading">Backlogs</h2>
      <QueryState query={query} what="backlogs">
        {(view) => <BacklogsSection prefix={prefix} view={view} />}
      </QueryState>
    </section>
  );
}
