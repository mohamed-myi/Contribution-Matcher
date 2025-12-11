/**
 * useIssues Hook
 * 
 * Fetches and manages issues with pagination and filtering.
 */

import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { issueService } from '../services/issueService';

/**
 * Fetch issues with pagination
 */
export function useIssues(filters = {}, options = {}) {
  return useQuery({
    queryKey: ['issues', filters],
    queryFn: () => issueService.getIssues(filters),
    staleTime: 1000 * 60 * 5, // 5 minutes
    ...options,
  });
}

/**
 * Fetch issues with infinite scroll
 */
export function useInfiniteIssues(filters = {}, options = {}) {
  return useInfiniteQuery({
    queryKey: ['issues', 'infinite', filters],
    queryFn: ({ pageParam = 0 }) => 
      issueService.getIssues({ ...filters, offset: pageParam }),
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage.has_more) return undefined;
      return allPages.length * (filters.limit || 20);
    },
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

/**
 * Fetch a single issue by ID
 */
export function useIssue(issueId, options = {}) {
  return useQuery({
    queryKey: ['issues', issueId],
    queryFn: () => issueService.getIssue(issueId),
    enabled: !!issueId,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

/**
 * Fetch issue statistics
 */
export function useIssueStats(options = {}) {
  return useQuery({
    queryKey: ['issues', 'stats'],
    queryFn: () => issueService.getStatistics(),
    staleTime: 1000 * 60 * 10, // 10 minutes
    ...options,
  });
}
