/**
 * ML Service
 * 
 * Handles ML-related API calls.
 */

import { apiClient } from '../../../shared/api/client';

export const mlService = {
  /**
   * Get unlabeled issues for training
   */
  async getUnlabeledIssues(limit = 20) {
    const response = await apiClient.get(`/ml/unlabeled?limit=${limit}`);
    return response.data;
  },

  /**
   * Get labeled issues
   */
  async getLabeledIssues(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.label) queryParams.append('label', params.label);
    if (params.offset !== undefined) queryParams.append('offset', params.offset);
    if (params.limit) queryParams.append('limit', params.limit);
    
    const response = await apiClient.get(`/ml/labeled?${queryParams.toString()}`);
    return response.data;
  },

  /**
   * Label a single issue
   */
  async labelIssue(issueId, label) {
    const response = await apiClient.post(`/ml/label/${issueId}`, { label });
    return response.data;
  },

  /**
   * Bulk label issues
   */
  async bulkLabelIssues(labels) {
    const response = await apiClient.post('/ml/label/bulk', { labels });
    return response.data;
  },

  /**
   * Get labeling statistics
   */
  async getLabelingStats() {
    const response = await apiClient.get('/ml/stats');
    return response.data;
  },

  /**
   * Get model status
   */
  async getModelStatus() {
    const response = await apiClient.get('/ml/model/status');
    return response.data;
  },

  /**
   * Train model
   */
  async trainModel(config = {}) {
    const response = await apiClient.post('/ml/model/train', config);
    return response.data;
  },
};
