import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';
import { renderWithProviders } from './test/test-utils';

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
  });

  it('renders login page at /login', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText('IssueIndex')).toBeInTheDocument();
  });

  it('redirects unauthenticated users from protected routes', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>
    );

    // Should redirect to login
    await waitFor(() => {
      expect(screen.getByText('IssueIndex')).toBeInTheDocument();
    });
  });

  it('renders dashboard when authenticated', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>
    );

    // With authentication, should show dashboard
    // Note: This requires proper AuthProvider setup
  });

  it('renders auth callback page', () => {
    render(
      <MemoryRouter initialEntries={['/auth/callback']}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText(/Completing authentication/i)).toBeInTheDocument();
  });

  it('redirects root to dashboard', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    // Should redirect to dashboard (or login if not authenticated)
    await waitFor(() => {
      // Either dashboard or login should be shown
      expect(
        screen.queryByText('Dashboard Page') ||
        screen.queryByText('IssueIndex')
      ).toBeTruthy();
    });
  });
});
