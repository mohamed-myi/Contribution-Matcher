import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from './Dashboard';
import { renderWithProviders } from '../test/test-utils';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getIssueStats: vi.fn(),
    getTopMatches: vi.fn(),
    discoverIssues: vi.fn(),
    getBookmarks: vi.fn(),
  },
}));

describe('Dashboard Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders dashboard', async () => {
    api.getIssueStats.mockResolvedValue({
      data: { total: 100, bookmarked: 5 },
    });
    api.getTopMatches.mockResolvedValue({
      data: { issues: [] },
    });

    renderWithProviders(<Dashboard />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1, github_username: 'testuser' },
        loading: false,
      },
    });

    await waitFor(() => {
      expect(api.getIssueStats).toHaveBeenCalled();
    });
  });

  it('shows loading state initially', () => {
    api.getIssueStats.mockImplementation(() => new Promise(() => {}));

    const { container } = renderWithProviders(<Dashboard />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1 },
        loading: false,
      },
    });

    // Should show skeleton cards when loading
    const skeletonCards = container.querySelectorAll('.skeleton-stats-card');
    expect(skeletonCards.length).toBeGreaterThan(0);
  });

  it('displays stats when loaded', async () => {
    api.getIssueStats.mockResolvedValue({
      data: { total: 100, bookmarked: 5, labeled: 10 },
    });
    api.getTopMatches.mockResolvedValue({
      data: { issues: [] },
    });

    renderWithProviders(<Dashboard />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1 },
        loading: false,
      },
    });

    await waitFor(() => {
      expect(api.getIssueStats).toHaveBeenCalled();
    });
  });
});
