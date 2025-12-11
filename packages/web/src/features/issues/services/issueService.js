/**
 * Issue Service
 * 
 * Handles issue-related API calls.
 */

import { apiClient } from '../../../shared/api/client';

export const issueService = {
  /**
   * Get issues with filters
   */
  async getIssues(filters = {}) {
    const params = new URLSearchParams();
    
    if (filters.difficulty) params.append('difficulty', filters.difficulty);
    if (filters.issue_type) params.append('issue_type', filters.issue_type);
    if (filters.technology) params.append('technology', filters.technology);
    if (filters.language) params.append('language', filters.language);
    if (filters.min_stars) params.append('min_stars', filters.min_stars);
    if (filters.days_back) params.append('days_back', filters.days_back);
    if (filters.order_by) params.append('order_by', filters.order_by);
    if (filters.offset !== undefined) params.append('offset', filters.offset);
    if (filters.limit) params.append('limit', filters.limit);
    
    const response = await apiClient.get(`/issues?${params.toString()}`);
    return response.data;
  },

  /**
   * Get a single issue
   */
  async getIssue(issueId) {
    const response = await apiClient.get(`/issues/${issueId}`);
    return response.data;
  },

  /**
   * Toggle bookmark for an issue
   */
  async toggleBookmark(issueId) {
    const response = await apiClient.post(`/issues/${issueId}/bookmark`);
    return response.data;
  },

  /**
   * Get bookmarked issues
   */
  async getBookmarks(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.offset !== undefined) queryParams.append('offset', params.offset);
    if (params.limit) queryParams.append('limit', params.limit);
    
    const response = await apiClient.get(`/issues/bookmarks?${queryParams.toString()}`);
    return response.data;
  },

  /**
   * Get issue statistics
   */
  async getStatistics() {
    const response = await apiClient.get('/issues/statistics');
    return response.data;
  },
};
