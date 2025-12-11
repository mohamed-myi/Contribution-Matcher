import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { queryKeys, useIssueStats, useIssues, useProfile } from './useApiQueries';
import { api } from '../api/client';

// Mock API client
vi.mock('../api/client', () => ({
  api: {
    getIssueStats: vi.fn(),
    getIssues: vi.fn(),
    getProfile: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('queryKeys', () => {
  it('generates correct issue stats key', () => {
    expect(queryKeys.issues.stats()).toEqual(['issues', 'stats']);
  });

  it('generates correct issue list key with filters', () => {
    const filters = { difficulty: 'beginner' };
    expect(queryKeys.issues.list(filters)).toEqual(['issues', 'list', filters]);
  });

  it('generates correct issue detail key', () => {
    expect(queryKeys.issues.detail(123)).toEqual(['issues', 'detail', 123]);
  });

  it('generates correct profile key', () => {
    expect(queryKeys.profile.current()).toEqual(['profile']);
  });

  it('generates correct top matches key', () => {
    expect(queryKeys.scoring.topMatches(10)).toEqual(['scoring', 'top-matches', 10]);
  });
});

describe('useIssueStats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches issue stats', async () => {
    const mockStats = { total: 100, bookmarked: 5 };
    api.getIssueStats.mockResolvedValue({ data: mockStats });

    const { result } = renderHook(() => useIssueStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockStats);
    expect(api.getIssueStats).toHaveBeenCalledTimes(1);
  });

  it('handles errors', async () => {
    const error = new Error('Failed to fetch');
    api.getIssueStats.mockRejectedValue(error);

    const { result } = renderHook(() => useIssueStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBe(error);
  });
});

describe('useIssues', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches issues with filters', async () => {
    const mockIssues = [{ id: 1, title: 'Test Issue' }];
    api.getIssues.mockResolvedValue({ data: mockIssues });

    const filters = { difficulty: 'beginner' };
    const { result } = renderHook(() => useIssues(filters), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockIssues);
    expect(api.getIssues).toHaveBeenCalledWith(filters);
  });

  it('does not fetch when enabled is false', () => {
    const { result } = renderHook(() => useIssues({}, { enabled: false }), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(api.getIssues).not.toHaveBeenCalled();
  });
});

describe('useProfile', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches profile', async () => {
    const mockProfile = { id: 1, skills: ['python'] };
    api.getProfile.mockResolvedValue({ data: mockProfile });

    const { result } = renderHook(() => useProfile(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockProfile);
    expect(api.getProfile).toHaveBeenCalledTimes(1);
  });
});
