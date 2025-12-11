import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FirstLoginPrompt } from './FirstLoginPrompt';
import { renderWithProviders } from '../test/test-utils';

const mockUser = {
  id: 1,
  github_username: 'testuser',
};

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  const mockNavigate = vi.fn();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('FirstLoginPrompt', () => {
  const mockSyncFromGitHub = vi.fn().mockResolvedValue({});
  const mockDismissFirstLoginPrompt = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not render when showFirstLoginPrompt is false', () => {
    renderWithProviders(<FirstLoginPrompt />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        showFirstLoginPrompt: false,
      },
    });
    expect(screen.queryByText('Welcome')).not.toBeInTheDocument();
  });

  it('renders when showFirstLoginPrompt is true', () => {
    renderWithProviders(<FirstLoginPrompt />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        showFirstLoginPrompt: true,
        syncFromGitHub: mockSyncFromGitHub,
        dismissFirstLoginPrompt: mockDismissFirstLoginPrompt,
      },
    });
    expect(screen.getByText(/Welcome, testuser!/)).toBeInTheDocument();
  });

  it('renders sync from GitHub option', () => {
    renderWithProviders(<FirstLoginPrompt />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        showFirstLoginPrompt: true,
        syncFromGitHub: mockSyncFromGitHub,
        dismissFirstLoginPrompt: mockDismissFirstLoginPrompt,
      },
    });
    expect(screen.getByText('Sync from GitHub')).toBeInTheDocument();
    expect(screen.getByText('Yes, Sync from GitHub')).toBeInTheDocument();
  });

  it('handles sync from GitHub click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<FirstLoginPrompt />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        showFirstLoginPrompt: true,
        syncFromGitHub: mockSyncFromGitHub,
        dismissFirstLoginPrompt: mockDismissFirstLoginPrompt,
      },
    });

    const syncButton = screen.getByText('Yes, Sync from GitHub');
    await user.click(syncButton);

    await waitFor(() => {
      expect(mockSyncFromGitHub).toHaveBeenCalled();
    });
  });

  it('shows loading state when syncing', async () => {
    // Create a sync function that doesn't resolve immediately
    const slowSync = vi.fn(() => new Promise(() => {})); // Never resolves
    const user = userEvent.setup();
    
    renderWithProviders(<FirstLoginPrompt />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        showFirstLoginPrompt: true,
        syncFromGitHub: slowSync,
        dismissFirstLoginPrompt: mockDismissFirstLoginPrompt,
      },
    });

    // Click sync button to trigger syncing state
    const syncButton = screen.getByText('Yes, Sync from GitHub');
    await user.click(syncButton);

    // Should show syncing text while syncing
    await waitFor(() => {
      expect(screen.getByText('Syncing...')).toBeInTheDocument();
    });
  });

  it('renders manual setup option', () => {
    renderWithProviders(<FirstLoginPrompt />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        showFirstLoginPrompt: true,
        syncFromGitHub: mockSyncFromGitHub,
        dismissFirstLoginPrompt: mockDismissFirstLoginPrompt,
      },
    });
    expect(screen.getByText('Manual Setup')).toBeInTheDocument();
    expect(screen.getByText('Set Up Manually')).toBeInTheDocument();
  });

  it('handles skip click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<FirstLoginPrompt />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        showFirstLoginPrompt: true,
        syncFromGitHub: mockSyncFromGitHub,
        dismissFirstLoginPrompt: mockDismissFirstLoginPrompt,
      },
    });

    const skipButton = screen.getByText('Skip for now');
    await user.click(skipButton);

    expect(mockDismissFirstLoginPrompt).toHaveBeenCalled();
  });

  it('displays error message when sync fails', async () => {
    const failingSync = vi.fn().mockRejectedValue(new Error('Sync failed'));
    const user = userEvent.setup();
    
    renderWithProviders(<FirstLoginPrompt />, {
      authState: {
        isAuthenticated: true,
        user: mockUser,
        showFirstLoginPrompt: true,
        syncFromGitHub: failingSync,
        dismissFirstLoginPrompt: mockDismissFirstLoginPrompt,
      },
    });

    const syncButton = screen.getByText('Yes, Sync from GitHub');
    await user.click(syncButton);

    await waitFor(() => {
      expect(screen.getByText(/Failed to sync from GitHub/)).toBeInTheDocument();
    });
  });
});
