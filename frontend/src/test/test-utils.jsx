import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../context/AuthContext';
import AuthContext from '../context/AuthContext';
import { vi } from 'vitest';

/**
 * Mock AuthProvider that uses provided auth state
 */
function MockAuthProvider({ children, authState = {} }) {
  const mockAuthValue = {
    user: authState.user || null,
    token: authState.token || null,
    loading: authState.loading !== undefined ? authState.loading : false,
    error: authState.error || null,
    isAuthenticated: authState.isAuthenticated !== undefined 
      ? authState.isAuthenticated 
      : !!authState.user,
    login: authState.login || vi.fn(),
    logout: authState.logout || vi.fn(),
    fetchProfile: authState.fetchProfile || vi.fn(),
    syncFromGitHub: authState.syncFromGitHub || vi.fn(),
    profile: authState.profile || null,
    profileLoading: authState.profileLoading || false,
    showFirstLoginPrompt: authState.showFirstLoginPrompt || false,
    dismissFirstLoginPrompt: authState.dismissFirstLoginPrompt || vi.fn(),
  };

  return (
    <AuthContext.Provider value={mockAuthValue}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Custom render function that wraps components with all necessary providers
 * @param {React.ReactElement} ui - Component to render
 * @param {Object} options - Render options
 * @param {QueryClient} options.queryClient - Custom QueryClient instance
 * @param {Object} options.routerOptions - React Router options
 * @param {Object} options.authState - Mock auth state (user, isAuthenticated, loading, etc.)
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
    authState,
    ...renderOptions
  } = {}
) {
  const Wrapper = ({ children }) => {
    if (authState) {
      // Use mock auth provider
      return (
        <QueryClientProvider client={queryClient}>
          <BrowserRouter {...routerOptions}>
            <MockAuthProvider authState={authState}>
              {children}
            </MockAuthProvider>
          </BrowserRouter>
        </QueryClientProvider>
      );
    }
    
    // Use real auth provider
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter {...routerOptions}>
          <AuthProvider>{children}</AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    );
  };

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
