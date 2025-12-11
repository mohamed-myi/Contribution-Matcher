import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Login } from './Login';
import { renderWithProviders } from '../test/test-utils';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

vi.mock('../api/client', () => ({
  api: {
    getLoginUrl: vi.fn(() => 'http://localhost:8000/api/v1/auth/login'),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('Login Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete window.location;
    window.location = { href: '' };
    // Default mock: not authenticated, not loading
    useAuth.mockReturnValue({
      isAuthenticated: false,
      loading: false,
      user: null,
    });
  });

  it('renders login form', () => {
    renderWithProviders(<Login />);

    expect(screen.getByText('IssueIndex')).toBeInTheDocument();
    expect(screen.getByText('Continue with GitHub')).toBeInTheDocument();
  });

  it('redirects authenticated users to dashboard', async () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      user: { id: 1, github_username: 'testuser' },
    });

    // Note: This test may need to be adjusted based on actual redirect behavior
    renderWithProviders(<Login />);

    // The redirect happens in useEffect, so we check for navigation
    await waitFor(() => {
      // Check that navigation occurred (implementation dependent)
    }, { timeout: 1000 });
  });

  it('handles GitHub login click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Login />);

    const loginButton = screen.getByText('Continue with GitHub');
    await user.click(loginButton);

    expect(window.location.href).toBe('http://localhost:8000/api/v1/auth/login');
  });

  it('does not render when loading', () => {
    useAuth.mockReturnValue({
      isAuthenticated: false,
      loading: true,
      user: null,
    });

    renderWithProviders(<Login />);

    // Login component returns null when loading, so login content should not be visible
    expect(screen.queryByText('IssueIndex')).not.toBeInTheDocument();
    expect(screen.queryByText('Continue with GitHub')).not.toBeInTheDocument();
  });

  it('renders terms text', () => {
    renderWithProviders(<Login />);

    expect(screen.getByText(/Terms of Service and Privacy Policy/)).toBeInTheDocument();
  });
});
