import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_URL = `${BASE_URL}/api`;

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle 401 Unauthorized
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('token');
      // Redirect to login if not already there
      if (window.location.pathname !== '/login' && !window.location.pathname.startsWith('/auth')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// API helper functions
export const api = {
  // Auth - returns full URL for redirect (uses API_URL which includes /api)
  getLoginUrl: () => `${API_URL}/auth/login`,
  getCurrentUser: () => apiClient.get('/auth/me'),
  logout: () => apiClient.post('/auth/logout'),
  deleteAccount: () => apiClient.delete('/auth/account'),

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

  // Profile
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
  getLabelStatus: () => apiClient.get('/ml/label-status'),
  getUnlabeledIssues: (limit = 50) => apiClient.get('/ml/unlabeled-issues', { params: { limit } }),
  trainModel: (options = {}) => apiClient.post('/ml/train', options),
  getModelInfo: () => apiClient.get('/ml/model-info'),
  evaluateModel: () => apiClient.post('/ml/evaluate'),

  // Jobs
  getJobs: () => apiClient.get('/jobs'),
  triggerJob: (jobId) => apiClient.post('/jobs/trigger', { job_id: jobId }),
  rescheduleJob: (jobId, cronExpression) => apiClient.post('/jobs/reschedule', { job_id: jobId, cron_expression: cronExpression }),
};

export default apiClient;
