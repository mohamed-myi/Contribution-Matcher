/**
 * Custom React Query Hooks with Cache Management
 * Provides hooks that automatically handle invalidation and prefetching
 */

import { useQueryClient, useMutation } from '@tanstack/react-query';
import { api } from '../api/client';
import { queryKeys, invalidationHelpers } from '../utils/queryKeys';

/**
 * Hook for bookmark mutations with cache invalidation
 */
export function useBookmarkMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ issueId, isBookmarked }) => {
      return isBookmarked ? api.removeBookmark(issueId) : api.bookmarkIssue(issueId);
    },
    onSuccess: (_, { issueId }) => {
      // Invalidate related queries
      invalidationHelpers.invalidateAfterBookmark(queryClient, issueId);
    },
  });
}

/**
 * Hook for label mutations with cache invalidation
 */
export function useLabelMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ issueId, label }) => api.labelIssue(issueId, label),
    onSuccess: (_, { issueId }) => {
      // Invalidate related queries
      invalidationHelpers.invalidateAfterLabel(queryClient, issueId);
    },
  });
}

/**
 * Hook for note mutations with cache invalidation
 */
export function useNoteMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ issueId, content, noteId, action }) => {
      if (action === 'add') {
        return api.addIssueNote(issueId, content);
      } else if (action === 'delete') {
        return api.deleteIssueNote(issueId, noteId);
      }
    },
    onSuccess: (_, { issueId }) => {
      // Invalidate notes query for this issue
      queryClient.invalidateQueries({ queryKey: queryKeys.notes.byIssue(issueId) });
    },
  });
}

/**
 * Hook for profile mutations with cache invalidation
 */
export function useProfileMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data) => api.updateProfile(data),
    onSuccess: () => {
      // Invalidate profile and dependent queries
      invalidationHelpers.invalidateAfterProfileUpdate(queryClient);
    },
  });
}

/**
 * Hook for ML training with cache invalidation
 */
export function useMLTrainingMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (options) => api.trainModel(options),
    onSuccess: () => {
      // Invalidate ML model and issue scores
      invalidationHelpers.invalidateAfterTraining(queryClient);
    },
  });
}

/**
 * Hook for discovery with cache invalidation
 */
export function useDiscoveryMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (params) => api.discoverIssues(params),
    onSuccess: () => {
      // Invalidate all issue-related queries
      invalidationHelpers.invalidateAfterDiscovery(queryClient);
    },
  });
}

/**
 * Hook to manually invalidate all caches
 */
export function useClearCache() {
  const queryClient = useQueryClient();
  
  return () => {
    queryClient.clear();
    try {
      localStorage.removeItem('CONTRIBUTION_MATCHER_CACHE');
    } catch (error) {
      console.warn('Failed to clear cache:', error);
    }
  };
}

export default {
  useBookmarkMutation,
  useLabelMutation,
  useNoteMutation,
  useProfileMutation,
  useMLTrainingMutation,
  useDiscoveryMutation,
  useClearCache,
};

