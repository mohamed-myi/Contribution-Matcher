import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient, api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
      setError(null);
    }
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

