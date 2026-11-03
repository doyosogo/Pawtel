import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import type { ReactNode } from 'react';
// Test-only component is intentionally local to this render utility.
// eslint-disable-next-line react-refresh/only-export-components
function Location() {
  const location = useLocation();
  return (
    <output aria-label="Current location">
      {location.pathname + location.search}
    </output>
  );
}
export function renderPage(
  element: ReactNode,
  { path = '/', route = '*' } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={element} />
          <Route path="*" element={<Location />} />
        </Routes>
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
}
