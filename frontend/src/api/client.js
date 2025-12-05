import axios from 'axios';

// Base API URLs derived from environment (falls back to local dev).
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_URL = `${BASE_URL}/api`;

// API Configuration
const API_CONFIG = {
  timeout: 30000, // 30 seconds
  retryAttempts: 2,
  retryDelay: 1000, // 1 second
  retryableStatuses: [408, 429, 500, 502, 503, 504],
};

/**
 * Axios instance configured for the backend API with auth header injection,
 * sane timeouts, and gzip support.
 */
export const apiClient = axios.create({
  baseURL: API_URL,
  timeout: API_CONFIG.timeout,
  headers: {
    'Content-Type': 'application/json',
    'Accept-Encoding': 'gzip, deflate', // Accept compressed responses
  },
});

// Simple retry logic
/**
 * Retry helper for transient HTTP errors.
 */
const retryRequest = async (error, retryCount = 0) => {
  const config = error.config;
  
  // Don't retry if max attempts reached or not retryable
  if (
    retryCount >= API_CONFIG.retryAttempts ||
    !config ||
    config._retry ||
    !API_CONFIG.retryableStatuses.includes(error.response?.status)
  ) {
    return Promise.reject(error);
  }
  
  // Mark as retry to prevent infinite loops
  config._retry = true;
  config._retryCount = retryCount + 1;
  
  // Wait before retrying
  await new Promise(resolve => setTimeout(resolve, API_CONFIG.retryDelay * (retryCount + 1)));
  
  return apiClient(config);
};

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling and retry
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Handle 401 Unauthorized
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      if (window.location.pathname !== '/login' && !window.location.pathname.startsWith('/auth')) {
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }
    
    // Retry on transient errors
    const retryCount = error.config?._retryCount || 0;
    if (API_CONFIG.retryableStatuses.includes(error.response?.status)) {
      return retryRequest(error, retryCount);
    }
    
    return Promise.reject(error);
  }
);

// API helper functions
/**
 * Typed API surface used across the frontend. All methods return axios promises.
 */
export const api = {
  // Auth - returns full URL for redirect (uses API_URL which includes /api)
  getLoginUrl: () => `${API_URL}/auth/login`,
  getCurrentUser: () => apiClient.get('/auth/me'),
  logout: () => apiClient.post('/auth/logout'),
  deleteAccount: () => apiClient.delete('/auth/account'),
  
  // Exchange auth code for JWT token (secure token exchange pattern)
  // This is called after OAuth callback to get the actual JWT
  exchangeAuthCode: (code) => apiClient.post(`/auth/token?code=${encodeURIComponent(code)}`),

  // Issues
  discoverIssues: (params) => apiClient.post('/issues/discover', params),
  getIssues: (params) => apiClient.get('/issues', { params }),
  getIssue: (id) => apiClient.get(`/issues/${id}`),
  bookmarkIssue: (id) => apiClient.post(`/issues/${id}/bookmark`),
  removeBookmark: (id) => apiClient.delete(`/issues/${id}/bookmark`),
  getBookmarks: () => apiClient.get('/issues/bookmarks'),
  getIssueStats: () => apiClient.get('/issues/stats'),
  getIssueNotes: (issueId) => apiClient.get(`/issues/${issueId}/notes`),
  addIssueNote: (issueId, content) => apiClient.post(`/issues/${issueId}/notes`, { content }),
  deleteIssueNote: (issueId, noteId) => apiClient.delete(`/issues/${issueId}/notes/${noteId}`),
  exportIssues: async (format = 'csv', bookmarksOnly = false) => {
    const response = await apiClient.get('/issues/export', {
      params: { format, bookmarks_only: bookmarksOnly },
      responseType: 'blob',
    });
    
    // Create download link
    const blob = new Blob([response.data], { 
      type: format === 'json' ? 'application/json' : 'text/csv' 
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `issues.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },


  getProfile: () => apiClient.get('/profile'),
  createProfileFromGithub: (username) => apiClient.post('/profile/from-github', { github_username: username }),
  createProfileFromResume: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/profile/from-resume', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  updateProfile: (data) => apiClient.put('/profile', data),

  // Scoring
  scoreAllIssues: () => apiClient.post('/scoring/score-all'),
  getTopMatches: (limit = 10) => apiClient.get('/scoring/top-matches', { params: { limit } }),
  getIssueScore: (id) => apiClient.get(`/scoring/${id}`),

  // ML
  labelIssue: (id, label) => apiClient.post(`/ml/label/${id}`, { label }),
  removeLabel: (id) => apiClient.delete(`/ml/label/${id}`),
  getLabelStatus: () => apiClient.get('/ml/label-status'),
  getUnlabeledIssues: (limit = 50, includeOthers = false) => apiClient.get('/ml/unlabeled-issues', { params: { limit, include_others: includeOthers } }),
  getLabeledIssues: (limit = 50, offset = 0, labelFilter = null) => 
    apiClient.get('/ml/labeled-issues', { params: { limit, offset, label_filter: labelFilter } }),
  trainModel: (options = {}) => apiClient.post('/ml/train', options),
  getModelInfo: () => apiClient.get('/ml/model-info'),
  evaluateModel: () => apiClient.post('/ml/evaluate'),

  // Jobs
  getJobs: () => apiClient.get('/jobs'),
  triggerJob: (jobId) => apiClient.post('/jobs/trigger', { job_id: jobId }),
  rescheduleJob: (jobId, cronExpression) => apiClient.post('/jobs/reschedule', { job_id: jobId, cron_expression: cronExpression }),

  // Staleness & Verification
  verifyIssueStatus: (issueId) => apiClient.post(`/issues/${issueId}/verify-status`),
  bulkVerifyIssues: (limit = 50, minAgeDays = 7) => 
    apiClient.post('/issues/verify-bulk', null, { params: { limit, min_age_days: minAgeDays } }),
  getStalenessStats: () => apiClient.get('/issues/staleness-stats'),
};

export default apiClient;
