// Renders the real routes in a memory router, with a probe that shows the
// current location and a Back button, for route-level tests.
import { QueryClientProvider } from '@tanstack/react-query';
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

export function renderApp(path: string) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
