import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthCallback } from './AuthCallback';
import { renderWithProviders } from '../test/test-utils';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    exchangeAuthCode: vi.fn(),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('AuthCallback Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    render(
      <MemoryRouter>
        <AuthCallback />
      </MemoryRouter>
    );

    expect(screen.getByText('Completing authentication...')).toBeInTheDocument();
  });

  it('exchanges auth code and navigates to dashboard', async () => {
    api.exchangeAuthCode.mockResolvedValue({
      data: { access_token: 'jwt-token' },
    });

    render(
      <MemoryRouter initialEntries={['/auth/callback?code=test-code']}>
        <AuthCallback />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(api.exchangeAuthCode).toHaveBeenCalledWith('test-code');
    });
  });

  it('shows error when error param is present', () => {
    render(
      <MemoryRouter initialEntries={['/auth/callback?error=authentication_failed']}>
        <AuthCallback />
      </MemoryRouter>
    );

    expect(screen.getByText('Authentication Failed')).toBeInTheDocument();
    expect(screen.getByText('Authentication failed. Please try again.')).toBeInTheDocument();
  });

  it('shows error when no credentials received', async () => {
    render(
      <MemoryRouter initialEntries={['/auth/callback']}>
        <AuthCallback />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Authentication Failed')).toBeInTheDocument();
    });
  });

  it('handles exchange errors', async () => {
    api.exchangeAuthCode.mockRejectedValue(new Error('Exchange failed'));

    render(
      <MemoryRouter initialEntries={['/auth/callback?code=test-code']}>
        <AuthCallback />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Failed to complete authentication/)).toBeInTheDocument();
    });
  });
});
