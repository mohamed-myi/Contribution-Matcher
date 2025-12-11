/**
 * Custom hooks for the Contribution Matcher frontend.
 */

export { useDebounce, useDebouncedCallback } from './useDebounce';
export { useCancelableRequest, useFetch } from './useCancelableRequest';
export { useVirtualization } from './useVirtualization';

// React Query hooks for API data fetching
export {
  // Query keys for cache management
  queryKeys,
  // Issue queries
  useIssueStats,
  useIssues,
  useIssue,
  useBookmarks,
  // Profile queries
  useProfile,
  // Scoring queries
  useTopMatches,
  // ML queries
  useLabelStatus,
  useUnlabeledIssues,
  useModelInfo,
  // Mutations
  useBookmarkMutation,
  useLabelMutation,
  useProfileMutation,
  useDiscoverMutation,
  // Prefetching
  usePrefetchIssues,
  usePrefetchStats,
} from './useApiQueries';
