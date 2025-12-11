import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Header } from './Header';
import { renderWithProviders } from '../../test/test-utils';

// Mock hooks
vi.mock('../../hooks', () => ({
  usePrefetchStats: () => vi.fn(),
  usePrefetchIssues: () => vi.fn(),
}));

vi.mock('../../App', () => ({
  lazyRoutes: {
    Dashboard: vi.fn(),
    Issues: vi.fn(),
    Profile: vi.fn(),
    MLTraining: vi.fn(),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

describe('Header', () => {
  const mockUser = {
    id: 1,
    github_username: 'testuser',
    avatar_url: 'https://example.com/avatar.png',
  };

  it('renders logo', () => {
    renderWithProviders(<Header />, {
      authState: { isAuthenticated: true, user: mockUser },
    });
    expect(screen.getByText('MYI')).toBeInTheDocument();
    expect(screen.getByText('IssueIndex')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    renderWithProviders(<Header />, {
      authState: { isAuthenticated: true, user: mockUser },
    });
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Issues')).toBeInTheDocument();
    expect(screen.getByText('Profile')).toBeInTheDocument();
    expect(screen.getByText('Algorithm Improvement')).toBeInTheDocument();
  });

  it('renders user info when authenticated', () => {
    renderWithProviders(<Header />, {
      authState: { isAuthenticated: true, user: mockUser },
    });
    expect(screen.getByText('testuser')).toBeInTheDocument();
    expect(screen.getByAltText('testuser')).toBeInTheDocument();
  });

  it('renders logout button when authenticated', () => {
    renderWithProviders(<Header />, {
      authState: { isAuthenticated: true, user: mockUser },
    });
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });

  it('handles logout click', async () => {
    const mockLogout = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<Header />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        logout: mockLogout,
      },
    });

    await user.click(screen.getByText('Logout'));
    expect(mockLogout).toHaveBeenCalled();
  });

  it('does not render user info when not authenticated', () => {
    renderWithProviders(<Header />, {
      authState: { isAuthenticated: false, user: null },
    });
    expect(screen.queryByText('testuser')).not.toBeInTheDocument();
    expect(screen.queryByText('Logout')).not.toBeInTheDocument();
  });
});
