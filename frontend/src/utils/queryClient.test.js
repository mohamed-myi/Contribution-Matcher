import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { waitFor } from '@testing-library/react';
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
      const now = Date.now();
      const cachedData = {
        timestamp: now,
        queries: [
          {
            queryKey: ['profile'],
            state: { data: { id: 1 }, dataUpdatedAt: now },
          },
        ],
      };
      localStorage.setItem('CONTRIBUTION_MATCHER_CACHE', JSON.stringify(cachedData));

      setupPersistentCache(queryClient);

      const cached = queryClient.getQueryData(['profile']);
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

      expect(localStorage.getItem('CONTRIBUTION_MATCHER_CACHE')).toBeFalsy();
    });

    it('saves cache on beforeunload', () => {
      setupPersistentCache(queryClient);
      
      // Set some query data that matches the filter criteria
      const now = Date.now();
      queryClient.setQueryData(['profile'], { id: 1 });
      // Manually update the query state to make it "success" and recent
      const cache = queryClient.getQueryCache();
      const query = cache.find({ queryKey: ['profile'] });
      if (query) {
        query.setState({
          ...query.state,
          status: 'success',
          data: { id: 1 },
          dataUpdatedAt: now,
        });
      }

      // Simulate beforeunload
      const event = new Event('beforeunload');
      window.dispatchEvent(event);

      // Check that cache was saved
      const saved = localStorage.getItem('CONTRIBUTION_MATCHER_CACHE');
      expect(saved).toBeTruthy();
      const parsed = JSON.parse(saved);
      expect(parsed.queries).toBeDefined();
      expect(parsed.queries.length).toBeGreaterThan(0);
    });
  });

  describe('warmCache', () => {
    it('prefetches profile when authenticated', async () => {
      api.getProfile.mockResolvedValue({ data: { id: 1 } });
      api.getIssueStats.mockResolvedValue({ data: { total: 100 } });

      // Mock requestIdleCallback if it doesn't exist
      const originalRequestIdleCallback = window.requestIdleCallback;
      if (!window.requestIdleCallback) {
        window.requestIdleCallback = (fn, options) => {
          // Execute immediately in test environment
          setTimeout(fn, 0);
        };
      }

      await warmCache(queryClient, api, true);

      // Wait for prefetch to complete (warmCache uses requestIdleCallback or setTimeout)
      await new Promise(resolve => setTimeout(resolve, 50));

      // Wait for the actual prefetch query to execute
      await waitFor(() => {
        expect(api.getProfile).toHaveBeenCalled();
      }, { timeout: 1000 });

      // Restore original if it existed
      if (originalRequestIdleCallback) {
        window.requestIdleCallback = originalRequestIdleCallback;
      }
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
      expect(localStorage.getItem('CONTRIBUTION_MATCHER_CACHE')).toBe('test');
      clearCache(queryClient);
      expect(localStorage.getItem('CONTRIBUTION_MATCHER_CACHE')).toBeFalsy();
    });
  });
});
