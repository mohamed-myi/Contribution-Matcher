import { http, HttpResponse } from 'msw';

const API_URL = 'http://localhost:8000/api/v1';

// Mock data
export const mockUser = {
  id: 1,
  github_id: '12345',
  github_username: 'testuser',
  email: 'test@example.com',
  avatar_url: 'https://avatars.githubusercontent.com/u/12345',
};

export const mockProfile = {
  id: 1,
  user_id: 1,
  skills: ['python', 'javascript'],
  experience_level: 'intermediate',
  interests: ['web development'],
  preferred_languages: ['python', 'javascript'],
  time_availability_hours_per_week: 10,
};

export const mockIssues = [
  {
    id: 1,
    title: 'Test Issue',
    url: 'https://github.com/test/repo/issues/1',
    repo_owner: 'test',
    repo_name: 'repo',
    difficulty: 'beginner',
    issue_type: 'bug',
    labels: ['bug', 'good-first-issue'],
  },
];

export const handlers = [
  // Auth endpoints
  http.get(`${API_URL}/auth/me`, () => {
    return HttpResponse.json(mockUser);
  }),

  http.post(`${API_URL}/auth/logout`, () => {
    return HttpResponse.json({ status: 'logged_out' });
  }),

  http.post(`${API_URL}/auth/token`, () => {
    return HttpResponse.json({
      access_token: 'mock-token',
      token_type: 'bearer',
    });
  }),

  http.delete(`${API_URL}/auth/account`, () => {
    return HttpResponse.json({ status: 'account_deleted' });
  }),

  // Profile endpoints
  http.get(`${API_URL}/profile`, () => {
    return HttpResponse.json(mockProfile);
  }),

  http.post(`${API_URL}/profile/from-github`, () => {
    return HttpResponse.json(mockProfile);
  }),

  http.put(`${API_URL}/profile`, () => {
    return HttpResponse.json(mockProfile);
  }),

  // Issues endpoints
  http.get(`${API_URL}/issues`, () => {
    return HttpResponse.json(mockIssues);
  }),

  http.get(`${API_URL}/issues/:id`, ({ params }) => {
    return HttpResponse.json({
      ...mockIssues[0],
      id: parseInt(params.id),
    });
  }),

  http.post(`${API_URL}/issues/discover`, () => {
    return HttpResponse.json({ job_id: 'mock-job-id' });
  }),

  http.post(`${API_URL}/issues/:id/bookmark`, () => {
    return HttpResponse.json({ success: true });
  }),

  http.delete(`${API_URL}/issues/:id/bookmark`, () => {
    return HttpResponse.json({ success: true });
  }),

  http.get(`${API_URL}/issues/bookmarks`, () => {
    return HttpResponse.json(mockIssues);
  }),

  http.get(`${API_URL}/issues/stats`, () => {
    return HttpResponse.json({
      total: 100,
      bookmarked: 5,
      labeled: 10,
    });
  }),

  // Scoring endpoints
  http.post(`${API_URL}/scoring/score-all`, () => {
    return HttpResponse.json({ job_id: 'mock-scoring-job' });
  }),

  http.get(`${API_URL}/scoring/top-matches`, () => {
    return HttpResponse.json(mockIssues.slice(0, 10));
  }),

  http.get(`${API_URL}/scoring/:id`, () => {
    return HttpResponse.json({ score: 0.85 });
  }),

  // ML endpoints
  http.post(`${API_URL}/ml/label/:id`, () => {
    return HttpResponse.json({ success: true });
  }),

  http.delete(`${API_URL}/ml/label/:id`, () => {
    return HttpResponse.json({ success: true });
  }),

  http.get(`${API_URL}/ml/label-status`, () => {
    return HttpResponse.json({
      total_labeled: 10,
      good_count: 5,
      bad_count: 5,
    });
  }),

  http.get(`${API_URL}/ml/unlabeled-issues`, () => {
    return HttpResponse.json(mockIssues);
  }),

  http.get(`${API_URL}/ml/labeled-issues`, () => {
    return HttpResponse.json(mockIssues);
  }),

  http.post(`${API_URL}/ml/train`, () => {
    return HttpResponse.json({ job_id: 'mock-train-job' });
  }),

  http.get(`${API_URL}/ml/model-info`, () => {
    return HttpResponse.json({
      version: 'v2',
      accuracy: 0.85,
      trained_at: '2024-01-01T00:00:00Z',
    });
  }),

  http.post(`${API_URL}/ml/evaluate`, () => {
    return HttpResponse.json({
      accuracy: 0.85,
      precision: 0.80,
      recall: 0.90,
    });
  }),

  // Jobs endpoints
  http.get(`${API_URL}/jobs`, () => {
    return HttpResponse.json([]);
  }),

  http.post(`${API_URL}/jobs/trigger`, () => {
    return HttpResponse.json({ success: true });
  }),

  // Staleness endpoints
  http.post(`${API_URL}/issues/:id/verify-status`, () => {
    return HttpResponse.json({ verified: true });
  }),

  http.get(`${API_URL}/issues/staleness-stats`, () => {
    return HttpResponse.json({
      stale_count: 5,
      verified_count: 95,
    });
  }),
];
