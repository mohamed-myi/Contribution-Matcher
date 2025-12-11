import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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

    render(
      <MemoryRouter>
        <Issues />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(api.getIssues).toHaveBeenCalled();
    });
  });

  it('shows loading state initially', () => {
    api.getIssues.mockImplementation(() => new Promise(() => {}));

    render(
      <MemoryRouter>
        <Issues />
      </MemoryRouter>
    );

    // Should show loading or skeleton
    expect(screen.queryByText(/Loading/i)).toBeInTheDocument();
  });
});
