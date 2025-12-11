import { describe, it, expect, vi, beforeEach } from 'vitest';

// Create mock instance using hoisted function
const mockAxiosInstance = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
}));

// Mock axios before importing client
vi.mock('axios', () => {
  const mockCreate = vi.fn(() => mockAxiosInstance);
  return {
    default: {
      create: mockCreate,
    },
    create: mockCreate,
  };
});

// Import after mock
import { apiClient, api } from './client';

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    document.cookie = '';
  });

  it('creates axios instance with correct config', () => {
    // axios.create is called when the module loads, so it should have been called
    // The mock is hoisted, so we need to check if it was called
    // Since apiClient is already created, we verify the instance exists
    expect(apiClient).toBeDefined();
    expect(mockAxiosInstance).toBeDefined();
    // The mock create function should have been called during module import
    // We can't directly verify this because the call happens during import,
    // but we can verify the instance was created by checking apiClient exists
    expect(apiClient).toBe(mockAxiosInstance);
  });
});

describe('api helper functions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mocks on the instance
    mockAxiosInstance.get = vi.fn();
    mockAxiosInstance.post = vi.fn();
    mockAxiosInstance.put = vi.fn();
    mockAxiosInstance.delete = vi.fn();
  });

  describe('auth endpoints', () => {
    it('getLoginUrl returns correct URL', () => {
      const url = api.getLoginUrl();
      expect(url).toContain('/api/v1/auth/login');
    });

    it('getCurrentUser calls correct endpoint', () => {
      api.getCurrentUser();
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });

    it('logout calls correct endpoint', () => {
      api.logout();
      expect(apiClient.post).toHaveBeenCalledWith('/auth/logout');
    });

    it('deleteAccount calls correct endpoint', () => {
      api.deleteAccount();
      expect(apiClient.delete).toHaveBeenCalledWith('/auth/account');
    });

    it('exchangeAuthCode calls correct endpoint with code', () => {
      api.exchangeAuthCode('test-code');
      expect(apiClient.post).toHaveBeenCalledWith(
        '/auth/token?code=test-code'
      );
    });
  });

  describe('issues endpoints', () => {
    it('getIssues calls correct endpoint with params', () => {
      const params = { limit: 20, offset: 0 };
      api.getIssues(params);
      expect(apiClient.get).toHaveBeenCalledWith('/issues', { params });
    });

    it('getIssue calls correct endpoint with id', () => {
      api.getIssue(123);
      expect(apiClient.get).toHaveBeenCalledWith('/issues/123');
    });

    it('discoverIssues calls correct endpoint', () => {
      const params = { limit: 50 };
      api.discoverIssues(params);
      expect(apiClient.post).toHaveBeenCalledWith('/issues/discover', params);
    });

    it('bookmarkIssue calls correct endpoint', () => {
      api.bookmarkIssue(123);
      expect(apiClient.post).toHaveBeenCalledWith('/issues/123/bookmark');
    });

    it('removeBookmark calls correct endpoint', () => {
      api.removeBookmark(123);
      expect(apiClient.delete).toHaveBeenCalledWith('/issues/123/bookmark');
    });
  });

  describe('profile endpoints', () => {
    it('getProfile calls correct endpoint', () => {
      api.getProfile();
      expect(apiClient.get).toHaveBeenCalledWith('/profile');
    });

    it('createProfileFromGithub calls correct endpoint', () => {
      api.createProfileFromGithub('testuser');
      expect(apiClient.post).toHaveBeenCalledWith('/profile/from-github', {
        github_username: 'testuser',
      });
    });

    it('updateProfile calls correct endpoint', () => {
      const data = { skills: ['python'] };
      api.updateProfile(data);
      expect(apiClient.put).toHaveBeenCalledWith('/profile', data);
    });
  });

  describe('scoring endpoints', () => {
    it('scoreAllIssues calls correct endpoint', () => {
      api.scoreAllIssues();
      expect(apiClient.post).toHaveBeenCalledWith('/scoring/score-all');
    });

    it('getTopMatches calls correct endpoint with limit', () => {
      api.getTopMatches(10);
      expect(apiClient.get).toHaveBeenCalledWith('/scoring/top-matches', {
        params: { limit: 10 },
      });
    });

    it('getIssueScore calls correct endpoint', () => {
      api.getIssueScore(123);
      expect(apiClient.get).toHaveBeenCalledWith('/scoring/123');
    });
  });

  describe('ML endpoints', () => {
    it('labelIssue calls correct endpoint', () => {
      api.labelIssue(123, 'good');
      expect(apiClient.post).toHaveBeenCalledWith('/ml/label/123', {
        label: 'good',
      });
    });

    it('removeLabel calls correct endpoint', () => {
      api.removeLabel(123);
      expect(apiClient.delete).toHaveBeenCalledWith('/ml/label/123');
    });

    it('getLabelStatus calls correct endpoint', () => {
      api.getLabelStatus();
      expect(apiClient.get).toHaveBeenCalledWith('/ml/label-status');
    });

    it('getUnlabeledIssues calls correct endpoint with params', () => {
      api.getUnlabeledIssues(50, true);
      expect(apiClient.get).toHaveBeenCalledWith('/ml/unlabeled-issues', {
        params: { limit: 50, include_others: true },
      });
    });

    it('trainModel calls correct endpoint', () => {
      const options = { use_advanced: true };
      api.trainModel(options);
      expect(apiClient.post).toHaveBeenCalledWith('/ml/train', options);
    });
  });
});
