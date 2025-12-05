import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient, api } from '../api/client';

const AuthContext = createContext(null);

// Profile source constants
const PROFILE_SOURCE = {
  GITHUB: 'github',
  RESUME: 'resume',
  MANUAL: 'manual',
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Profile state for first-login handling
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [showFirstLoginPrompt, setShowFirstLoginPrompt] = useState(false);

  // Fetch profile
  const fetchProfile = useCallback(async () => {
    try {
      setProfileLoading(true);
      const response = await api.getProfile();
      setProfile(response.data);
      return response.data;
    } catch (err) {
      if (err.response?.status === 404) {
        // No profile exists
        setProfile(null);
        return null;
      }
      console.error('Failed to fetch profile:', err);
      return null;
    } finally {
      setProfileLoading(false);
    }
  }, []);

  // Sync profile from GitHub
  const syncFromGitHub = useCallback(async () => {
    if (!user?.github_username) return null;
    
    try {
      setProfileLoading(true);
      await api.createProfileFromGithub(user.github_username);
      const newProfile = await fetchProfile();
      return newProfile;
    } catch (err) {
      console.error('Failed to sync from GitHub:', err);
      throw err;
    } finally {
      setProfileLoading(false);
    }
  }, [user, fetchProfile]);

  // Fetch current user
  const fetchUser = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      const response = await apiClient.get('/auth/me');
      setUser(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch user:', err);
      // Token is invalid, clear it
      if (err.response?.status === 401) {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Check auth on mount and token change
  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // After user is loaded, check profile and handle auto-sync
  useEffect(() => {
    if (!user || loading) return;

    const checkProfileAndSync = async () => {
      const existingProfile = await fetchProfile();
      
      if (!existingProfile) {
        // No profile - show first login prompt
        setShowFirstLoginPrompt(true);
      } else if (existingProfile.profile_source === PROFILE_SOURCE.GITHUB) {
        // Profile from GitHub - auto-resync on login
        try {
          await syncFromGitHub();
        } catch (err) {
          console.error('Auto-resync failed:', err);
        }
      }
    };

    checkProfileAndSync();
  }, [user, loading, fetchProfile, syncFromGitHub]);

  // Login - save token and fetch user
  // Returns a promise that resolves with the user or rejects with an error
  const login = useCallback(async (newToken) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
    setLoading(true);
    
    try {
      const response = await apiClient.get('/auth/me', {
        headers: { Authorization: `Bearer ${newToken}` }
      });
      setUser(response.data);
      setError(null);
      return response.data; // Return user data so caller can await it
    } catch (err) {
      console.error('Failed to fetch user after login:', err);
      setError(err.message);
      // Re-throw so the caller knows login failed
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Logout - invalidate token on server and clear local state
  const logout = useCallback(async () => {
    try {
      // Call backend to invalidate token
      await api.logout();
    } catch (err) {
      // Ignore errors - we're logging out anyway
      console.error('Logout API call failed:', err);
    } finally {
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
      setProfile(null);
      setShowFirstLoginPrompt(false);
      setError(null);
    }
  }, []);

  // Dismiss first login prompt
  const dismissFirstLoginPrompt = useCallback(() => {
    setShowFirstLoginPrompt(false);
  }, []);

  const value = {
    user,
    token,
    loading,
    error,
    isAuthenticated: !!token && !!user,
    login,
    logout,
    refreshUser: fetchUser,
    // Profile related
    profile,
    profileLoading,
    fetchProfile,
    syncFromGitHub,
    showFirstLoginPrompt,
    dismissFirstLoginPrompt,
    PROFILE_SOURCE,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;

