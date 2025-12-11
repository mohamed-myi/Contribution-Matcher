import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import { apiClient, api } from '../api/client';

// Mock API client
vi.mock('../api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
  api: {
    getProfile: vi.fn().mockResolvedValue({ data: null }),
    createProfileFromGithub: vi.fn().mockResolvedValue({ data: {} }),
    logout: vi.fn().mockResolvedValue({}),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>{children}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = '';
    // Clear mocks but keep the function structure
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('useAuth hook', () => {
    it('throws error when used outside AuthProvider', () => {
      expect(() => {
        renderHook(() => useAuth());
      }).toThrow('useAuth must be used within an AuthProvider');
    });

    it('returns auth context when used inside AuthProvider', () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      expect(result.current).toBeDefined();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBe(null);
    });
  });

  describe('initial state', () => {
    it('starts with loading true', async () => {
      // Clear any existing auth state
      localStorage.clear();
      document.cookie = '';
      // Set a token so fetchUser will actually run (not skip immediately)
      localStorage.setItem('token', 'test-token');
      apiClient.get.mockRejectedValueOnce(new Error('Not authenticated'));
      api.getProfile.mockResolvedValueOnce({ data: null });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Initially loading should be true
      expect(result.current.loading).toBe(true);

      // Wait for fetchUser to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
    });

    it('fetches user on mount if token exists', async () => {
      const mockUser = { id: 1, github_username: 'testuser' };
      
      // CRITICAL: Set token BEFORE setting up mocks and rendering hook
      // useState(() => localStorage.getItem('token')) reads synchronously on mount
      localStorage.setItem('token', 'test-token');
      
      // Verify token is actually in localStorage
      expect(localStorage.getItem('token')).toBe('test-token');
      
      // Set up mocks - use mockResolvedValue for multiple potential calls
      apiClient.get.mockResolvedValue({ data: mockUser });
      api.getProfile.mockResolvedValue({ data: null });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Give it a moment for the effect to run
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // Verify apiClient.get was called (should be called on mount when token exists)
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');

      // Wait for fetchUser to complete and user to be set
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      }, { timeout: 3000 });
    });

    it('fetches user on mount if cookie exists', async () => {
      document.cookie = 'csrf_token=test-token';
      const mockUser = { id: 1, github_username: 'testuser' };
      apiClient.get.mockResolvedValue({ data: mockUser });
      api.getProfile.mockResolvedValue({ data: null });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      });
    });
  });

  describe('login', () => {
    it('saves token and fetches user', async () => {
      localStorage.clear();
      document.cookie = '';
      const mockUser = { id: 1, github_username: 'testuser' };
      
      // Mock the initial fetch (no auth) - will be called on mount
      apiClient.get.mockRejectedValueOnce(new Error('Not authenticated'));
      api.getProfile.mockResolvedValueOnce({ data: null });
      
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for initial load to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Mock the login fetch
      apiClient.get.mockResolvedValueOnce({ data: mockUser });

      await act(async () => {
        await result.current.login('new-token');
      });

      await waitFor(() => {
        expect(localStorage.getItem('token')).toBe('new-token');
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      });
    });

    it('handles login errors', async () => {
      const error = new Error('Login failed');
      apiClient.get.mockRejectedValue(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      await act(async () => {
        await expect(result.current.login('token')).rejects.toThrow('Login failed');
      });

      expect(result.current.error).toBe('Login failed');
    });
  });

  describe('logout', () => {
    it('clears user and token', async () => {
      const mockUser = { id: 1, github_username: 'testuser' };
      // Set up mocks BEFORE setting token and rendering
      apiClient.get.mockResolvedValue({ data: mockUser });
      api.getProfile.mockResolvedValue({ data: null });
      api.logout.mockResolvedValue({});
      
      localStorage.setItem('token', 'test-token');

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for loading to complete first
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      }, { timeout: 3000 });

      // Then wait for user to be loaded and profile check to complete
      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      }, { timeout: 3000 });

      await act(async () => {
        await result.current.logout();
      });

      expect(localStorage.getItem('token')).toBe(null);
      expect(result.current.user).toBe(null);
      expect(result.current.isAuthenticated).toBe(false);
      expect(api.logout).toHaveBeenCalled();
    });
  });

  describe('fetchProfile', () => {
    it('fetches profile successfully', async () => {
      const mockProfile = { id: 1, skills: ['python'] };
      api.getProfile.mockResolvedValueOnce({ data: mockProfile });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      let profile;
      await act(async () => {
        profile = await result.current.fetchProfile();
      });

      expect(profile).toEqual(mockProfile);
      expect(result.current.profile).toEqual(mockProfile);
    });

    it('handles 404 (no profile)', async () => {
      const error = { response: { status: 404 } };
      api.getProfile.mockRejectedValueOnce(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      let profile;
      await act(async () => {
        profile = await result.current.fetchProfile();
      });

      expect(profile).toBe(null);
      expect(result.current.profile).toBe(null);
    });
  });

  describe('syncFromGitHub', () => {
    it('syncs profile from GitHub', async () => {
      const mockUser = { id: 1, github_username: 'testuser' };
      const mockProfile = { id: 1, skills: ['python'] };
      
      // Set token so user will be fetched
      localStorage.setItem('token', 'test-token');
      
      // Set up mocks - use mockResolvedValue for initial calls
      apiClient.get.mockResolvedValue({ data: mockUser });
      api.getProfile.mockResolvedValue({ data: null });
      
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for loading to complete first
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      }, { timeout: 3000 });

      // Wait for user to be loaded and profile check to complete
      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      }, { timeout: 3000 });

      // Mock sync operations (these should be Once since they're called explicitly)
      api.createProfileFromGithub.mockResolvedValueOnce({});
      api.getProfile.mockResolvedValueOnce({ data: mockProfile });

      let syncedProfile;
      await act(async () => {
        syncedProfile = await result.current.syncFromGitHub();
      });

      expect(api.createProfileFromGithub).toHaveBeenCalledWith('testuser');
      expect(syncedProfile).toEqual(mockProfile);
    });

    it('returns null if no user', async () => {
      apiClient.get.mockRejectedValueOnce(new Error('Not authenticated'));
      
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      let syncedProfile;
      await act(async () => {
        syncedProfile = await result.current.syncFromGitHub();
      });

      expect(syncedProfile).toBe(null);
      expect(api.createProfileFromGithub).not.toHaveBeenCalled();
    });
  });

  describe('isAuthenticated', () => {
    it('returns false when user is null', async () => {
      apiClient.get.mockRejectedValueOnce(new Error('Not authenticated'));
      api.getProfile.mockResolvedValueOnce({ data: null });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(false);
    });

    it('returns true when user exists', async () => {
      const mockUser = { id: 1, github_username: 'testuser' };
      
      // Set token so user will be fetched
      localStorage.setItem('token', 'test-token');
      
      // Set up mocks BEFORE rendering
      apiClient.get.mockResolvedValue({ data: mockUser });
      api.getProfile.mockResolvedValue({ data: null });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for loading to complete first
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      }, { timeout: 3000 });

      // Wait for user to be loaded and profile check to complete
      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      }, { timeout: 3000 });

      expect(result.current.isAuthenticated).toBe(true);
    });
  });
});
