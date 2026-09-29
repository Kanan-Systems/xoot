// Routes and the query client. Each view is its own route under the
// project; the drawer and filters are query parameters on top of it.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom';

import { BacklogPage } from './pages/BacklogPage.tsx';
import { DecisionsPage } from './pages/DecisionsPage.tsx';
import { HomePage } from './pages/HomePage.tsx';
import { ProjectPage } from './pages/ProjectPage.tsx';
import { SessionsPage } from './pages/SessionsPage.tsx';
import { TreePage } from './pages/TreePage.tsx';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // Freshness comes from /changes polling, not from timers per query.
      queries: { staleTime: Infinity, retry: 1, refetchOnWindowFocus: false },
    },
  });
}

// B4a's /:project/item/:key links open the drawer on the tree.
function ItemRedirect() {
  const { project = '', key = '' } = useParams();
  const search = new URLSearchParams({ item: key });
  return <Navigate to={`/${project}/tree?${search.toString()}`} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/:project" element={<ProjectPage />}>
        <Route index element={<Navigate to="tree" replace />} />
        <Route path="tree" element={<TreePage focus={false} />} />
        <Route path="focus/:key" element={<TreePage focus />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="backlog" element={<BacklogPage />} />
        <Route path="decisions" element={<DecisionsPage />} />
        <Route path="item/:key" element={<ItemRedirect />} />
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
