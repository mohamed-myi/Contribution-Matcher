/**
 * React Query Client Configuration
 * Centralized configuration for all caching behavior
 */

import { QueryClient } from '@tanstack/react-query';

/**
 * Create a configured QueryClient instance
 */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Stale-while-revalidate: Data is fresh for 2 minutes
        staleTime: 1000 * 60 * 2, // 2 minutes
        
        // Keep unused data in cache for 30 minutes
        gcTime: 1000 * 60 * 30, // 30 minutes (formerly cacheTime)
        
        // Retry failed requests
        retry: (failureCount, error) => {
          // Don't retry on 404 or auth errors
          if (error?.response?.status === 404 || error?.response?.status === 401) {
            return false;
          }
          // Retry up to 2 times for other errors
          return failureCount < 2;
        },
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
        
        // Refetch behavior
        refetchOnWindowFocus: true, // Refetch when user returns to tab
        refetchOnMount: true, // Refetch on component mount if stale
        refetchOnReconnect: true, // Refetch when internet reconnects
        
        // Network mode
        networkMode: 'online', // Only fetch when online
        
        // Structural sharing for performance
        structuralSharing: true,
      },
      mutations: {
        // Retry mutations once on failure
        retry: 1,
        retryDelay: 1000,
        
        // Network mode
        networkMode: 'online',
      },
    },
  });
}

/**
 * Setup persistent cache using localStorage
 * Lightweight implementation without external dependencies
 */
export function setupPersistentCache(queryClient) {
  // Only enable in browser environment
  if (typeof window === 'undefined') {
    return null;
  }
  
  try {
    // Load persisted cache on startup
    const cachedData = localStorage.getItem('CONTRIBUTION_MATCHER_CACHE');
    if (cachedData) {
      const parsed = JSON.parse(cachedData);
      // Check if cache is still valid (24 hours)
      if (parsed.timestamp && Date.now() - parsed.timestamp < 1000 * 60 * 60 * 24) {
        // Hydrate cache
        if (parsed.queries) {
          parsed.queries.forEach((query) => {
            queryClient.setQueryData(query.queryKey, query.state.data);
          });
        }
      } else {
        // Clear old cache
        localStorage.removeItem('CONTRIBUTION_MATCHER_CACHE');
      }
    }
    
    // Save cache on window unload
    const saveCache = () => {
      try {
        const cache = queryClient.getQueryCache();
        const queries = cache.getAll()
          .filter((query) => {
            // Only persist successful queries with recent data
            return (
              query.state.status === 'success' &&
              query.state.data &&
              query.state.dataUpdatedAt > Date.now() - (1000 * 60 * 30) && // Less than 30 minutes old
              ['profile', 'issues', 'ml'].includes(query.queryKey[0])
            );
          })
          .map((query) => ({
            queryKey: query.queryKey,
            state: {
              data: query.state.data,
              dataUpdatedAt: query.state.dataUpdatedAt,
            },
          }));
        
        localStorage.setItem('CONTRIBUTION_MATCHER_CACHE', JSON.stringify({
          timestamp: Date.now(),
          queries,
        }));
      } catch (error) {
        // Ignore quota exceeded errors
        console.warn('Failed to save cache:', error);
      }
    };
    
    window.addEventListener('beforeunload', saveCache);
    
    return { saveCache };
  } catch (error) {
    console.warn('Failed to setup persistent cache:', error);
    return null;
  }
}

/**
 * Cache warming - preload critical data
 */
export async function warmCache(queryClient, api, isAuthenticated) {
  if (!isAuthenticated) {
    return;
  }
  
  // Use requestIdleCallback for non-blocking cache warming
  const warmUp = async () => {
    try {
      // Prefetch profile (used on every page)
      await queryClient.prefetchQuery({
        queryKey: ['profile', 'detail'],
        queryFn: () => api.getProfile(),
        staleTime: 1000 * 60 * 10,
      });
      
      // Prefetch stats (shown on dashboard)
      await queryClient.prefetchQuery({
        queryKey: ['issues', 'stats'],
        queryFn: () => api.getIssueStats(),
        staleTime: 1000 * 60 * 2,
      });
    } catch (error) {
      // Silently fail - cache warming is optional
      console.warn('Cache warming failed:', error);
    }
  };
  
  if ('requestIdleCallback' in window) {
    requestIdleCallback(warmUp, { timeout: 2000 });
  } else {
    setTimeout(warmUp, 2000);
  }
}

/**
 * Clear all cached data (for logout or errors)
 */
export function clearCache(queryClient) {
  queryClient.clear();
  
  // Also clear localStorage
  try {
    localStorage.removeItem('CONTRIBUTION_MATCHER_CACHE');
  } catch (error) {
    console.warn('Failed to clear cache:', error);
  }
}

export default {
  createQueryClient,
  setupPersistentCache,
  warmCache,
  clearCache,
};

