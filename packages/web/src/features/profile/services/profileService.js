/**
 * Profile Service
 * 
 * Handles profile-related API calls.
 */

import { apiClient } from '../../../shared/api/client';

export const profileService = {
  /**
   * Get current user's profile
   */
  async getProfile() {
    const response = await apiClient.get('/profile');
    return response.data;
  },

  /**
   * Update profile
   */
  async updateProfile(profileData) {
    const response = await apiClient.put('/profile', profileData);
    return response.data;
  },

  /**
   * Import profile from GitHub
   */
  async importFromGitHub() {
    const response = await apiClient.post('/profile/import/github');
    return response.data;
  },

  /**
   * Get profile statistics
   */
  async getStats() {
    const response = await apiClient.get('/profile/stats');
    return response.data;
  },
};
