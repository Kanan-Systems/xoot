// Routes and the query client. Each view is its own route under the
// project; the drawer, goal, focus and filters are query parameters on top
// of it, so nested keys never become path segments.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom';

import { PARAM } from './lib/search.ts';
import { BacklogPage } from './pages/BacklogPage.tsx';
import { DecisionsPage } from './pages/DecisionsPage.tsx';
import { HomePage } from './pages/HomePage.tsx';
import { ProjectPage } from './pages/ProjectPage.tsx';
import { TreePage } from './pages/TreePage.tsx';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // Freshness comes from /changes polling, not from timers per query.
      queries: { staleTime: Infinity, retry: 1, refetchOnWindowFocus: false },
    },
  });
}

// Older links carried the key in the path; they land on the tree with the
// key moved into its query parameter.
function KeyRedirect({ param }: { param: string }) {
  const { project = '', '*': key = '' } = useParams();
  const search = new URLSearchParams({ [param]: key });
  return <Navigate to={`/${project}/tree?${search.toString()}`} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/:project" element={<ProjectPage />}>
        <Route index element={<Navigate to="tree" replace />} />
        <Route path="tree" element={<TreePage />} />
        <Route path="backlog" element={<BacklogPage />} />
        <Route path="decisions" element={<DecisionsPage />} />
        <Route path="item/*" element={<KeyRedirect param={PARAM.item} />} />
        <Route path="focus/*" element={<KeyRedirect param={PARAM.focus} />} />
        <Route path="*" element={<p role="alert">No such view.</p>} />
      </Route>
    </Routes>
  );
}

export function App({ client }: { client: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
