// The entry point: redirects to the first project's tree.
import { Navigate } from 'react-router-dom';

import { useProjects } from '../api/queries.ts';
import { QueryState } from '../components/QueryState.tsx';

export function HomePage() {
  const query = useProjects();
  return (
    <main className="home">
      <h1>xoot</h1>
      <QueryState query={query} what="projects">
        {(view) => {
          const [first] = view.projects;
          if (first === undefined) {
            return <p>No projects yet: run `xoot init --prefix &lt;prefix&gt;`.</p>;
          }
          return <Navigate to={`/${first.key_prefix}/tree`} replace />;
        }}
      </QueryState>
    </main>
  );
}
