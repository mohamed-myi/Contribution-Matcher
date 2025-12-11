import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  createQueryClient,
  setupPersistentCache,
  warmCache,
  clearCache,
} from './queryClient';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getProfile: vi.fn(),
    getIssueStats: vi.fn(),
  },
}));

describe('queryClient utilities', () => {
  let queryClient;

  beforeEach(() => {
    queryClient = createQueryClient();
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('createQueryClient', () => {
    it('creates QueryClient instance', () => {
      const client = createQueryClient();
      expect(client).toBeInstanceOf(QueryClient);
    });

    it('configures stale time', () => {
      const client = createQueryClient();
      const defaultOptions = client.getDefaultOptions();
      expect(defaultOptions.queries?.staleTime).toBe(120000); // 2 minutes
    });

    it('configures retry logic', () => {
      const client = createQueryClient();
      const defaultOptions = client.getDefaultOptions();
      expect(defaultOptions.queries?.retry).toBeDefined();
    });
  });

  describe('setupPersistentCache', () => {
    it('loads cache from localStorage', () => {
      const cachedData = {
        timestamp: Date.now(),
        queries: [
          {
            queryKey: ['profile', 'detail'],
            state: { data: { id: 1 }, dataUpdatedAt: Date.now() },
          },
        ],
      };
      localStorage.setItem('CONTRIBUTION_MATCHER_CACHE', JSON.stringify(cachedData));

      setupPersistentCache(queryClient);

      const cached = queryClient.getQueryData(['profile', 'detail']);
      expect(cached).toEqual({ id: 1 });
    });

    it('ignores expired cache', () => {
      const cachedData = {
        timestamp: Date.now() - (25 * 60 * 60 * 1000), // 25 hours ago
        queries: [
          {
            queryKey: ['profile', 'detail'],
            state: { data: { id: 1 } },
          },
        ],
      };
      localStorage.setItem('CONTRIBUTION_MATCHER_CACHE', JSON.stringify(cachedData));

      setupPersistentCache(queryClient);

      expect(localStorage.getItem('CONTRIBUTION_MATCHER_CACHE')).toBe(null);
    });

    it('saves cache on beforeunload', () => {
      setupPersistentCache(queryClient);
      
      // Set some query data
      queryClient.setQueryData(['profile', 'detail'], { id: 1 });

      // Simulate beforeunload
      const event = new Event('beforeunload');
      window.dispatchEvent(event);

      // Check that cache was saved
      const saved = localStorage.getItem('CONTRIBUTION_MATCHER_CACHE');
      expect(saved).toBeTruthy();
    });
  });

  describe('warmCache', () => {
    it('prefetches profile when authenticated', async () => {
      api.getProfile.mockResolvedValue({ data: { id: 1 } });
      api.getIssueStats.mockResolvedValue({ data: { total: 100 } });

      await warmCache(queryClient, api, true);

      // Wait for prefetch to complete
      await new Promise(resolve => setTimeout(resolve, 100));

      expect(api.getProfile).toHaveBeenCalled();
    });

    it('does not prefetch when not authenticated', async () => {
      await warmCache(queryClient, api, false);

      expect(api.getProfile).not.toHaveBeenCalled();
    });
  });

  describe('clearCache', () => {
    it('clears query client cache', () => {
      queryClient.setQueryData(['test'], { data: 'test' });
      expect(queryClient.getQueryData(['test'])).toEqual({ data: 'test' });

      clearCache(queryClient);

      expect(queryClient.getQueryData(['test'])).toBeUndefined();
    });

    it('clears localStorage cache', () => {
      localStorage.setItem('CONTRIBUTION_MATCHER_CACHE', 'test');
      clearCache(queryClient);
      expect(localStorage.getItem('CONTRIBUTION_MATCHER_CACHE')).toBe(null);
    });
  });
});
