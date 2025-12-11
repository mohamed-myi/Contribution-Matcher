import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';
import AuthContext from './context/AuthContext';

// Mock BrowserRouter to use MemoryRouter for testing (avoids nesting)
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    BrowserRouter: ({ children, ...props }) => {
      // Get initial path and search from window.location or use '/'
      const pathname = typeof window !== 'undefined' && window.location ? window.location.pathname : '/';
      const search = typeof window !== 'undefined' && window.location ? window.location.search : '';
      const initialEntry = search ? `${pathname}${search}` : pathname;
      return <MemoryRouter initialEntries={[initialEntry]} {...props}>{children}</MemoryRouter>;
    },
  };
});

// Create a module-level variable to store test auth state
const testAuthState = { isAuthenticated: false, loading: false };

// Mock AuthProvider to use test auth state
vi.mock('./context/AuthContext', async () => {
  const actual = await vi.importActual('./context/AuthContext');
  const React = await import('react');
  return {
    ...actual,
    AuthProvider: ({ children }) => {
      // Read testAuthState fresh each render (no memoization)
      const mockAuthValue = {
        user: testAuthState.user || null,
        token: testAuthState.token || null,
        loading: testAuthState.loading !== undefined ? testAuthState.loading : false,
        error: testAuthState.error || null,
        isAuthenticated: testAuthState.isAuthenticated !== undefined 
          ? testAuthState.isAuthenticated 
          : !!testAuthState.user,
        login: testAuthState.login || vi.fn(),
        logout: testAuthState.logout || vi.fn(),
        fetchProfile: testAuthState.fetchProfile || vi.fn(),
        syncFromGitHub: testAuthState.syncFromGitHub || vi.fn(),
        profile: testAuthState.profile || null,
        profileLoading: testAuthState.profileLoading || false,
        showFirstLoginPrompt: testAuthState.showFirstLoginPrompt || false,
        dismissFirstLoginPrompt: testAuthState.dismissFirstLoginPrompt || vi.fn(),
      };
      return React.createElement(AuthContext.Provider, { value: mockAuthValue }, children);
    },
  };
});

// Mock lazy-loaded pages
vi.mock('./pages/Dashboard', () => ({
  Dashboard: () => <div>Dashboard Page</div>,
}));

vi.mock('./pages/Issues', () => ({
  Issues: () => <div>Issues Page</div>,
}));

vi.mock('./pages/Profile', () => ({
  Profile: () => <div>Profile Page</div>,
}));

vi.mock('./pages/MLTraining', () => ({
  MLTraining: () => <div>MLTraining Page</div>,
}));

vi.mock('./pages/LabeledIssues', () => ({
  LabeledIssues: () => <div>LabeledIssues Page</div>,
}));


describe('App Routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset test auth state
    Object.assign(testAuthState, { isAuthenticated: false, loading: false, user: null });
  });

  it('renders login page at /login', () => {
    Object.defineProperty(window, 'location', {
      value: { pathname: '/login' },
      writable: true,
    });
    
    Object.assign(testAuthState, { isAuthenticated: false, loading: false, user: null });
    render(<App />);

    expect(screen.getByText('IssueIndex')).toBeInTheDocument();
  });

  it('redirects unauthenticated users from protected routes', async () => {
    Object.defineProperty(window, 'location', {
      value: { pathname: '/dashboard' },
      writable: true,
    });
    
    Object.assign(testAuthState, { isAuthenticated: false, loading: false, user: null });
    render(<App />);

    // Should redirect to login
    await waitFor(() => {
      expect(screen.getByText('IssueIndex')).toBeInTheDocument();
    });
  });

  it('renders dashboard when authenticated', async () => {
    Object.defineProperty(window, 'location', {
      value: { pathname: '/dashboard' },
      writable: true,
    });
    
    Object.assign(testAuthState, { 
      isAuthenticated: true, 
      user: { id: 1, github_username: 'testuser' },
      loading: false 
    });
    render(<App />);

    // With authentication, should show dashboard
    await waitFor(() => {
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument();
    });
  });

  it('renders auth callback page', () => {
    Object.defineProperty(window, 'location', {
      value: { pathname: '/auth/callback', search: '?code=test-code' },
      writable: true,
    });
    
    Object.assign(testAuthState, { isAuthenticated: false, loading: false, user: null });
    render(<App />);

    expect(screen.getByText(/Completing authentication/i)).toBeInTheDocument();
  });

  it('redirects root to dashboard', async () => {
    Object.defineProperty(window, 'location', {
      value: { pathname: '/' },
      writable: true,
    });
    
    Object.assign(testAuthState, { 
      isAuthenticated: true, 
      user: { id: 1, github_username: 'testuser' },
      loading: false 
    });
    render(<App />);

    // Should redirect to dashboard
    await waitFor(() => {
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument();
    });
  });
});
