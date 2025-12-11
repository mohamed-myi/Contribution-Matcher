import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { LabeledIssues } from './LabeledIssues';
import { renderWithProviders } from '../test/test-utils';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getLabeledIssues: vi.fn(),
    removeLabel: vi.fn(),
  },
}));

describe('LabeledIssues Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders labeled issues page', async () => {
    api.getLabeledIssues.mockResolvedValue({
      data: { issues: [], total: 0 },
    });

    renderWithProviders(<LabeledIssues />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1 },
        loading: false,
      },
    });

    await waitFor(() => {
      expect(api.getLabeledIssues).toHaveBeenCalled();
    });
  });
});
