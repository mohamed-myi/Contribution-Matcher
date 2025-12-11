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
      // Mock localStorage to return a token
      const mockLocalStorage = {
        getItem: vi.fn((key) => key === 'token' ? 'test-token' : null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      };
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
        writable: true,
      });
      
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
      
      // Set up mocks first
      apiClient.get.mockResolvedValue({ data: mockUser });
      api.getProfile.mockResolvedValue({ data: null });
      
      // Set token - use Object.defineProperty to ensure it persists
      // This works around potential test environment localStorage issues
      Object.defineProperty(window, 'localStorage', {
        value: {
          getItem: vi.fn((key) => key === 'token' ? 'test-token' : null),
          setItem: vi.fn(),
          removeItem: vi.fn(),
          clear: vi.fn(),
        },
        writable: true,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // The effect should run immediately on mount if token exists
      // Give React a tick to run effects
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 0));
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
      const mockUser = { id: 1, github_username: 'testuser' };
      const storedTokens = {};
      
      // Mock localStorage
      const mockLocalStorage = {
        getItem: vi.fn((key) => storedTokens[key] || null),
        setItem: vi.fn((key, value) => { storedTokens[key] = value; }),
        removeItem: vi.fn((key) => { delete storedTokens[key]; }),
        clear: vi.fn(() => { Object.keys(storedTokens).forEach(k => delete storedTokens[k]); }),
      };
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
        writable: true,
      });
      
      // Mock the initial fetch (no auth) - will be called on mount
      // Since there's no token initially, fetchUser will skip, so no call needed
      api.getProfile.mockResolvedValue({ data: null });
      
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for initial load to complete (should be fast since no token)
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Mock the login fetch - login() calls apiClient.get('/auth/me')
      apiClient.get.mockResolvedValueOnce({ data: mockUser });

      await act(async () => {
        await result.current.login('new-token');
      });

      await waitFor(() => {
        expect(mockLocalStorage.getItem('token')).toBe('new-token');
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
      const storedTokens = { token: 'test-token' };
      
      // Mock localStorage
      const mockLocalStorage = {
        getItem: vi.fn((key) => storedTokens[key] || null),
        setItem: vi.fn((key, value) => { storedTokens[key] = value; }),
        removeItem: vi.fn((key) => { delete storedTokens[key]; }),
        clear: vi.fn(() => { Object.keys(storedTokens).forEach(k => delete storedTokens[k]); }),
      };
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
        writable: true,
      });
      
      // Set up mocks BEFORE rendering
      apiClient.get.mockResolvedValue({ data: mockUser });
      api.getProfile.mockResolvedValue({ data: null });
      api.logout.mockResolvedValue({});

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

      expect(mockLocalStorage.getItem('token')).toBe(null);
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
      
      // Mock localStorage
      const mockLocalStorage = {
        getItem: vi.fn((key) => key === 'token' ? 'test-token' : null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      };
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
        writable: true,
      });
      
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
      
      // Mock localStorage
      const mockLocalStorage = {
        getItem: vi.fn((key) => key === 'token' ? 'test-token' : null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      };
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
        writable: true,
      });
      
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
