import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { AuthCallback } from './AuthCallback';
import { renderWithProviders } from '../test/test-utils';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    exchangeAuthCode: vi.fn(),
  },
}));

// Remove the navigate mock as renderWithProviders handles routing

describe('AuthCallback Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', async () => {
    // Mock login to delay execution so we can see loading state
    const mockLogin = vi.fn(() => new Promise(() => {})); // Never resolves
    
    renderWithProviders(
      <AuthCallback />,
      {
        routerOptions: {
          initialEntries: ['/auth/callback?code=test-code'],
        },
        authState: {
          isAuthenticated: false,
          loading: false,
          user: null,
          login: mockLogin,
        },
      }
    );

    // The component should show loading while processing (before exchange completes)
    expect(screen.getByText('Completing authentication...')).toBeInTheDocument();
  });

  it('exchanges auth code and navigates to dashboard', async () => {
    api.exchangeAuthCode.mockResolvedValue({
      data: { access_token: 'jwt-token' },
    });
    
    const mockLogin = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <AuthCallback />,
      {
        routerOptions: {
          initialEntries: ['/auth/callback?code=test-code'],
        },
        authState: {
          isAuthenticated: false,
          loading: false,
          user: null,
          login: mockLogin,
        },
      }
    );

    await waitFor(() => {
      expect(api.exchangeAuthCode).toHaveBeenCalledWith('test-code');
    }, { timeout: 2000 });
  });

  it('shows error when error param is present', () => {
    renderWithProviders(
      <AuthCallback />,
      {
        routerOptions: {
          initialEntries: ['/auth/callback?error=authentication_failed'],
        },
        authState: {
          isAuthenticated: false,
          loading: false,
          user: null,
        },
      }
    );

    expect(screen.getByText('Authentication Failed')).toBeInTheDocument();
    expect(screen.getByText('Authentication failed. Please try again.')).toBeInTheDocument();
  });

  it('shows error when no credentials received', async () => {
    renderWithProviders(
      <AuthCallback />,
      {
        routerOptions: {
          initialEntries: ['/auth/callback'],
        },
        authState: {
          isAuthenticated: false,
          loading: false,
          user: null,
        },
      }
    );

    await waitFor(() => {
      expect(screen.getByText('Authentication Failed')).toBeInTheDocument();
    });
  });

  it('handles exchange errors', async () => {
    api.exchangeAuthCode.mockRejectedValue(new Error('Exchange failed'));

    renderWithProviders(
      <AuthCallback />,
      {
        routerOptions: {
          initialEntries: ['/auth/callback?code=test-code'],
        },
        authState: {
          isAuthenticated: false,
          loading: false,
          user: null,
        },
      }
    );

    await waitFor(() => {
      expect(screen.getByText(/Failed to complete authentication/)).toBeInTheDocument();
    }, { timeout: 2000 });
  });
});
