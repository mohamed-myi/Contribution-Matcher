/**
 * Auth Service
 * 
 * Handles authentication API calls.
 */

import { apiClient } from '../../../shared/api/client';

const API_URL = import.meta.env.VITE_API_URL || '';

export const authService = {
  /**
   * Initiate GitHub OAuth login
   */
  initiateLogin() {
    // Store current location for redirect after login
    sessionStorage.setItem('auth_redirect', window.location.pathname);
    
    // Redirect to backend OAuth endpoint
    window.location.href = `${API_URL}/auth/github/login`;
  },

  /**
   * Handle OAuth callback
   */
  async handleCallback(code, state) {
    const response = await apiClient.get('/auth/github/callback', {
      params: { code, state },
    });
    
    // Store tokens
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
    }
    
    return response.data;
  },

  /**
   * Get current authenticated user
   */
  async getCurrentUser() {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  /**
   * Logout current user
   */
  async logout() {
    await apiClient.post('/auth/logout');
    localStorage.removeItem('access_token');
  },

  /**
   * Refresh access token
   */
  async refreshToken() {
    const response = await apiClient.post('/auth/refresh');
    
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
    }
    
    return response.data;
  },

  /**
   * Get stored access token
   */
  getAccessToken() {
    return localStorage.getItem('access_token');
  },
};
