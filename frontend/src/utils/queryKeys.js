/**
 * Query Key Factory
 * Centralized location for all React Query cache keys
 * Ensures consistency and makes cache invalidation easier
 */

export const queryKeys = {
  // Auth queries
  auth: {
    all: ['auth'],
    me: () => [...queryKeys.auth.all, 'me'],
  },
  
  // Profile queries
  profile: {
    all: ['profile'],
    detail: () => [...queryKeys.profile.all, 'detail'],
    github: (username) => [...queryKeys.profile.all, 'github', username],
  },
  
  // Issues queries
  issues: {
    all: ['issues'],
    list: (filters = {}) => [...queryKeys.issues.all, 'list', filters],
    detail: (id) => [...queryKeys.issues.all, 'detail', id],
    score: (id) => [...queryKeys.issues.all, 'score', id],
    stats: () => [...queryKeys.issues.all, 'stats'],
    topMatches: (limit = 5) => [...queryKeys.issues.all, 'topMatches', limit],
    unlabeled: (limit, includeOthers) => [...queryKeys.issues.all, 'unlabeled', limit, includeOthers],
    labeled: (limit, offset, label) => [...queryKeys.issues.all, 'labeled', limit, offset, label],
  },
  
  // Bookmarks queries
  bookmarks: {
    all: ['bookmarks'],
    list: () => [...queryKeys.bookmarks.all, 'list'],
  },
  
  // Notes queries
  notes: {
    all: ['notes'],
    byIssue: (issueId) => [...queryKeys.notes.all, 'issue', issueId],
  },
  
  // ML/Training queries
  ml: {
    all: ['ml'],
    labelStatus: () => [...queryKeys.ml.all, 'labelStatus'],
    modelInfo: () => [...queryKeys.ml.all, 'modelInfo'],
  },
  
  // Discovery queries
  discovery: {
    all: ['discovery'],
    issues: (params = {}) => [...queryKeys.discovery.all, 'issues', params],
  },
};

/**
 * Helper to invalidate all queries for a specific resource
 */
export const invalidationHelpers = {
  // Invalidate all issue-related queries
  invalidateIssues: (queryClient) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
  },
  
  // Invalidate specific issue and related queries
  invalidateIssue: (queryClient, issueId) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.detail(issueId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.score(issueId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.notes.byIssue(issueId) });
  },
  
  // Invalidate after labeling an issue
  invalidateAfterLabel: (queryClient, issueId) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.detail(issueId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.list() });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.unlabeled() });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.labeled() });
    queryClient.invalidateQueries({ queryKey: queryKeys.ml.labelStatus() });
  },
  
  // Invalidate after bookmark changes
  invalidateAfterBookmark: (queryClient, issueId) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.detail(issueId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.bookmarks.all });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.stats() });
  },
  
  // Invalidate after profile changes
  invalidateAfterProfileUpdate: (queryClient) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.profile.all });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.list() });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.topMatches() });
  },
  
  // Invalidate after ML training
  invalidateAfterTraining: (queryClient) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.ml.modelInfo() });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.list() });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.topMatches() });
  },
  
  // Invalidate after discovery
  invalidateAfterDiscovery: (queryClient) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.stats() });
  },
};

/**
 * Prefetch helpers for common patterns
 */
export const prefetchHelpers = {
  // Prefetch dashboard data
  prefetchDashboard: async (queryClient, api) => {
    await Promise.all([
      queryClient.prefetchQuery({
        queryKey: queryKeys.issues.stats(),
        queryFn: () => api.getIssueStats(),
        staleTime: 1000 * 60 * 2, // 2 minutes
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.issues.topMatches(5),
        queryFn: () => api.getTopMatches(5),
        staleTime: 1000 * 60 * 2,
      }),
    ]);
  },
  
  // Prefetch issues list
  prefetchIssues: async (queryClient, api, filters = {}) => {
    await queryClient.prefetchQuery({
      queryKey: queryKeys.issues.list(filters),
      queryFn: () => api.getIssues(filters),
      staleTime: 1000 * 60 * 5, // 5 minutes
    });
  },
  
  // Prefetch profile
  prefetchProfile: async (queryClient, api) => {
    await queryClient.prefetchQuery({
      queryKey: queryKeys.profile.detail(),
      queryFn: () => api.getProfile(),
      staleTime: 1000 * 60 * 10, // 10 minutes
    });
  },
};

export default queryKeys;

