/**
 * React Query hooks for API data fetching.
 * 
 * Benefits:
 * - Automatic request deduplication (same query = single request)
 * - Background refetching (stale-while-revalidate)
 * - Caching with configurable TTL
 * - Loading/error states built-in
 * - Automatic retry on failure
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

// Query key factories for consistent cache keys
/**
 * Stable query key generators for React Query caches.
 * Use these helpers to avoid key drift across components.
 */
export const queryKeys = {
  // Issues
  issues: {
    all: ['issues'],
    list: (filters) => ['issues', 'list', filters],
    detail: (id) => ['issues', 'detail', id],
    stats: () => ['issues', 'stats'],
    bookmarks: () => ['issues', 'bookmarks'],
  },
  // Profile
  profile: {
    current: () => ['profile'],
  },
  // Scoring
  scoring: {
    topMatches: (limit) => ['scoring', 'top-matches', limit],
  },
  // ML
  ml: {
    labelStatus: () => ['ml', 'label-status'],
    unlabeled: (limit, includeOthers) => ['ml', 'unlabeled', { limit, includeOthers }],
    modelInfo: () => ['ml', 'model-info'],
  },
};

// Stale time configurations (in ms)
const STALE_TIMES = {
  stats: 5 * 60 * 1000,      // 5 minutes - stats don't change often
  issues: 2 * 60 * 1000,     // 2 minutes - issues list
  profile: 10 * 60 * 1000,   // 10 minutes - profile rarely changes
  topMatches: 5 * 60 * 1000, // 5 minutes - scores are cached
};

// ============================================================================
// Issue Queries
// ============================================================================

/**
 * Fetch issue statistics with caching.
 */
export function useIssueStats() {
  return useQuery({
    queryKey: queryKeys.issues.stats(),
    queryFn: async () => {
      const response = await api.getIssueStats();
      return response.data;
    },
    staleTime: STALE_TIMES.stats,
  });
}

/**
 * Fetch paginated issues with filters.
 */
export function useIssues(filters = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: queryKeys.issues.list(filters),
    queryFn: async () => {
      const response = await api.getIssues(filters);
      return response.data;
    },
    staleTime: STALE_TIMES.issues,
    enabled,
  });
}

/**
 * Fetch single issue details.
 */
export function useIssue(id, { enabled = true } = {}) {
  return useQuery({
    queryKey: queryKeys.issues.detail(id),
    queryFn: async () => {
      const response = await api.getIssue(id);
      return response.data;
    },
    enabled: enabled && !!id,
  });
}

/**
 * Fetch bookmarked issues.
 */
export function useBookmarks() {
  return useQuery({
    queryKey: queryKeys.issues.bookmarks(),
    queryFn: async () => {
      const response = await api.getBookmarks();
      return response.data;
    },
    staleTime: STALE_TIMES.issues,
  });
}

// ============================================================================
// Profile Queries
// ============================================================================

/**
 * Fetch current user's profile.
 */
export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile.current(),
    queryFn: async () => {
      const response = await api.getProfile();
      return response.data;
    },
    staleTime: STALE_TIMES.profile,
  });
}

// ============================================================================
// Scoring Queries
// ============================================================================

/**
 * Fetch top matched issues.
 */
export function useTopMatches(limit = 10) {
  return useQuery({
    queryKey: queryKeys.scoring.topMatches(limit),
    queryFn: async () => {
      const response = await api.getTopMatches(limit);
      return response.data;
    },
    staleTime: STALE_TIMES.topMatches,
  });
}

// ============================================================================
// ML Queries
// ============================================================================

/**
 * Fetch label status for ML training.
 */
export function useLabelStatus() {
  return useQuery({
    queryKey: queryKeys.ml.labelStatus(),
    queryFn: async () => {
      const response = await api.getLabelStatus();
      return response.data;
    },
  });
}

/**
 * Fetch unlabeled issues for ML training.
 */
export function useUnlabeledIssues(limit = 50, includeOthers = false) {
  return useQuery({
    queryKey: queryKeys.ml.unlabeled(limit, includeOthers),
    queryFn: async () => {
      const response = await api.getUnlabeledIssues(limit, includeOthers);
      return response.data;
    },
  });
}

/**
 * Fetch ML model info.
 */
export function useModelInfo() {
  return useQuery({
    queryKey: queryKeys.ml.modelInfo(),
    queryFn: async () => {
      const response = await api.getModelInfo();
      return response.data;
    },
  });
}

// ============================================================================
// Mutations with Cache Invalidation
// ============================================================================

/**
 * Bookmark mutation with optimistic update.
 */
export function useBookmarkMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ issueId, isBookmarked }) => {
      if (isBookmarked) {
        await api.removeBookmark(issueId);
      } else {
        await api.bookmarkIssue(issueId);
      }
      return { issueId, isBookmarked: !isBookmarked };
    },
    // Optimistic update
    onMutate: async ({ issueId, isBookmarked }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.issues.all });
      
      // Snapshot previous value
      const previousBookmarks = queryClient.getQueryData(queryKeys.issues.bookmarks());
      
      return { previousBookmarks };
    },
    onError: (err, variables, context) => {
      // Rollback on error
      if (context?.previousBookmarks) {
        queryClient.setQueryData(queryKeys.issues.bookmarks(), context.previousBookmarks);
      }
    },
    onSettled: () => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.bookmarks() });
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.stats() });
    },
  });
}

/**
 * Label issue mutation for ML training.
 */
export function useLabelMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ issueId, label }) => {
      await api.labelIssue(issueId, label);
      return { issueId, label };
    },
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: queryKeys.ml.labelStatus() });
      queryClient.invalidateQueries({ queryKey: queryKeys.ml.unlabeled(50, false) });
      queryClient.invalidateQueries({ queryKey: queryKeys.ml.unlabeled(50, true) });
    },
  });
}

/**
 * Profile update mutation.
 */
export function useProfileMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (profileData) => {
      const response = await api.updateProfile(profileData);
      return response.data;
    },
    onSuccess: (data) => {
      // Update cache with new profile
      queryClient.setQueryData(queryKeys.profile.current(), data);
      // Invalidate scores since profile changed
      queryClient.invalidateQueries({ queryKey: queryKeys.scoring.topMatches(10) });
    },
  });
}

/**
 * Discover issues mutation.
 */
export function useDiscoverMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (params) => {
      const response = await api.discoverIssues(params);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate issues list and stats
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
    },
  });
}

// ============================================================================
// Prefetching Utilities
// ============================================================================

/**
 * Prefetch issues for a specific page.
 * Call on hover/focus of navigation links.
 */
export function usePrefetchIssues() {
  const queryClient = useQueryClient();
  
  return (filters = {}) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.issues.list(filters),
      queryFn: async () => {
        const response = await api.getIssues(filters);
        return response.data;
      },
      staleTime: STALE_TIMES.issues,
    });
  };
}

/**
 * Prefetch stats for dashboard.
 */
export function usePrefetchStats() {
  const queryClient = useQueryClient();
  
  return () => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.issues.stats(),
      queryFn: async () => {
        const response = await api.getIssueStats();
        return response.data;
      },
      staleTime: STALE_TIMES.stats,
    });
  };
}

