import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { Issues } from './Issues';
import { renderWithProviders } from '../test/test-utils';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getIssues: vi.fn(),
    getBookmarks: vi.fn(),
    discoverIssues: vi.fn(),
    bookmarkIssue: vi.fn(),
    removeBookmark: vi.fn(),
    exportIssues: vi.fn(),
  },
}));

describe('Issues Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders issues page', async () => {
    api.getIssues.mockResolvedValue({
      data: { issues: [], total: 0 },
    });

    renderWithProviders(<Issues />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1, github_username: 'testuser' },
        loading: false,
      },
    });

    await waitFor(() => {
      expect(api.getIssues).toHaveBeenCalled();
    });
  });

  it('shows loading state initially', () => {
    api.getIssues.mockImplementation(() => new Promise(() => {}));

    const { container } = renderWithProviders(<Issues />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1, github_username: 'testuser' },
        loading: false,
      },
    });

    // Should show loading or skeleton
    const skeletonElements = container.querySelectorAll('.skeleton');
    expect(skeletonElements.length).toBeGreaterThan(0);
  });
});
