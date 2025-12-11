import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../context/AuthContext';

/**
 * Custom render function that wraps components with all necessary providers
 * @param {React.ReactElement} ui - Component to render
 * @param {Object} options - Render options
 * @param {QueryClient} options.queryClient - Custom QueryClient instance
 * @param {Object} options.routerOptions - React Router options
 * @returns {Object} Render result with all testing utilities
 */
export function renderWithProviders(
  ui,
  {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    }),
    routerOptions = {},
    ...renderOptions
  } = {}
) {
  const Wrapper = ({ children }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter {...routerOptions}>
        <AuthProvider>{children}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );

  return render(ui, {
    wrapper: Wrapper,
    ...renderOptions,
  });
}

/**
 * Render with authentication
 */
export function renderWithAuth(ui, user = null, options = {}) {
  return renderWithProviders(ui, {
    authState: {
      isAuthenticated: !!user,
      user: user || {
        id: 1,
        github_username: 'testuser',
        email: 'test@example.com',
      },
      loading: false,
    },
    ...options,
  });
}

/**
 * Render without authentication
 */
export function renderWithoutAuth(ui, options = {}) {
  return renderWithProviders(ui, {
    authState: {
      isAuthenticated: false,
      user: null,
      loading: false,
    },
    ...options,
  });
}

// Re-export everything from @testing-library/react
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
