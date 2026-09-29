// Routes and the query client.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { HomePage } from './pages/HomePage.tsx';
import { ProjectPage } from './pages/ProjectPage.tsx';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // Freshness comes from /changes polling, not from timers per query.
      queries: { staleTime: Infinity, retry: 1, refetchOnWindowFocus: false },
    },
  });
}

export function App({ client }: { client: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/:project" element={<ProjectPage mode="tree" />} />
          <Route path="/:project/focus/:key" element={<ProjectPage mode="focus" />} />
          <Route path="/:project/item/:key" element={<ProjectPage mode="item" />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
