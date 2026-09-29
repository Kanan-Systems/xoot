// The project list; with a single project it opens that project directly.
import { Link, Navigate } from 'react-router-dom';

import { useProjects } from '../api/queries.ts';
import { QueryState } from '../components/QueryState.tsx';

export function HomePage() {
  const query = useProjects();
  return (
    <main className="home">
      <h1>xoot</h1>
      <QueryState query={query} what="projects">
        {(view) => {
          const [only] = view.projects;
          if (view.projects.length === 1 && only !== undefined) {
            return <Navigate to={`/${only.key_prefix}`} replace />;
          }
          if (view.projects.length === 0) {
            return <p>No projects yet: run `xoot init --prefix &lt;prefix&gt;`.</p>;
          }
          return (
            <ul className="list">
              {view.projects.map((project) => (
                <li key={project.key_prefix}>
                  <Link to={`/${project.key_prefix}`}>
                    {project.name} ({project.key_prefix})
                  </Link>
                </li>
              ))}
            </ul>
          );
        }}
      </QueryState>
    </main>
  );
}
