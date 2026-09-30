// Renders the real routes in a memory router, with a probe that shows the
// current location and a Back button, for route-level tests.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';

import { AppRoutes, createQueryClient } from '../App.tsx';

function Probe() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="location">{`${location.pathname}${location.search}`}</output>
      <button
        type="button"
        onClick={() => {
          void navigate(-1);
        }}
      >
        Test back
      </button>
    </>
  );
}

// A test that drives refetches passes its own query client.
export function renderApp(path: string, client: QueryClient = createQueryClient()) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
