/**
 * useLabeling Hook
 * 
 * Manages issue labeling for ML training.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { mlService } from '../services/mlService';

/**
 * Fetch unlabeled issues for labeling
 */
export function useUnlabeledIssues(options = {}) {
  return useQuery({
    queryKey: ['ml', 'unlabeled'],
    queryFn: () => mlService.getUnlabeledIssues(),
    staleTime: 1000 * 60 * 2, // 2 minutes
    ...options,
  });
}

/**
 * Fetch labeled issues
 */
export function useLabeledIssues(params = {}, options = {}) {
  return useQuery({
    queryKey: ['ml', 'labeled', params],
    queryFn: () => mlService.getLabeledIssues(params),
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

/**
 * Label an issue
 */
export function useLabelIssue(options = {}) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ issueId, label }) => mlService.labelIssue(issueId, label),
    onSuccess: () => {
      // Refresh unlabeled and labeled lists
      queryClient.invalidateQueries({ queryKey: ['ml', 'unlabeled'] });
      queryClient.invalidateQueries({ queryKey: ['ml', 'labeled'] });
      queryClient.invalidateQueries({ queryKey: ['ml', 'stats'] });
    },
    // Optimistic update
    onMutate: async ({ issueId }) => {
      await queryClient.cancelQueries({ queryKey: ['ml', 'unlabeled'] });
      
      const previousUnlabeled = queryClient.getQueryData(['ml', 'unlabeled']);
      
      // Remove from unlabeled list optimistically
      queryClient.setQueryData(['ml', 'unlabeled'], (old) => {
        if (!old?.issues) return old;
        return {
          ...old,
          issues: old.issues.filter(i => i.id !== issueId),
        };
      });
      
      return { previousUnlabeled };
    },
    onError: (err, variables, context) => {
      // Rollback on error
      if (context?.previousUnlabeled) {
        queryClient.setQueryData(['ml', 'unlabeled'], context.previousUnlabeled);
      }
    },
    ...options,
  });
}

/**
 * Bulk label issues
 */
export function useBulkLabel(options = {}) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (labels) => mlService.bulkLabelIssues(labels),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml'] });
    },
    ...options,
  });
}
