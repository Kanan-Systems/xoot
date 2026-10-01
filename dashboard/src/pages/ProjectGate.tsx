// The project route's gate: a key prefix opens the project, an alias
// redirects to the same view under the prefix (the dashboard builds every
// URL from the prefix), and any other name says no project has it.
import { Navigate, useLocation, useParams } from 'react-router-dom';

import { useProjects } from '../api/queries.ts';
import { QueryState } from '../components/QueryState.tsx';
import { resolveProjectName, withProject } from '../lib/projectName.ts';
import { ProjectPage } from './ProjectPage.tsx';

export function ProjectGate() {
  const { project = '' } = useParams();
  const location = useLocation();
  const query = useProjects();
  return (
    <QueryState query={query} what="projects">
      {(view) => {
        const name = resolveProjectName(view.projects, project);
        if (name.kind === 'prefix') {
          return <ProjectPage />;
        }
        if (name.kind === 'alias') {
          const to = `${withProject(location.pathname, name.prefix)}${location.search}`;
          return <Navigate to={to} replace />;
        }
        return (
          <main className="home">
            <p role="alert">No project named “{project}”.</p>
          </main>
        );
      }}
    </QueryState>
  );
}
