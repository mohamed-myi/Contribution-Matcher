import { describe, it, expect, vi, beforeEach } from 'vitest';
import { waitFor } from '@testing-library/react';
import { MLTraining } from './MLTraining';
import { renderWithProviders } from '../test/test-utils';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getLabelStatus: vi.fn(),
    getUnlabeledIssues: vi.fn(),
    labelIssue: vi.fn(),
    trainModel: vi.fn(),
    getModelInfo: vi.fn(),
  },
}));

describe('MLTraining Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders ML training page', async () => {
    api.getLabelStatus.mockResolvedValue({
      data: { total_labeled: 10, good_count: 5, bad_count: 5 },
    });
    api.getUnlabeledIssues.mockResolvedValue({
      data: { issues: [] },
    });

    renderWithProviders(<MLTraining />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1 },
        loading: false,
      },
    });

    await waitFor(() => {
      expect(api.getLabelStatus).toHaveBeenCalled();
    });
  });
});
