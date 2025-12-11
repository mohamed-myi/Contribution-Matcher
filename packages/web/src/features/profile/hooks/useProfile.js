/**
 * useProfile Hook
 * 
 * Manages user profile state.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { profileService } from '../services/profileService';

/**
 * Fetch current user's profile
 */
export function useProfile(options = {}) {
  return useQuery({
    queryKey: ['profile'],
    queryFn: () => profileService.getProfile(),
    staleTime: 1000 * 60 * 5, // 5 minutes
    ...options,
  });
}

/**
 * Update profile mutation
 */
export function useUpdateProfile(options = {}) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (profileData) => profileService.updateProfile(profileData),
    onSuccess: (data) => {
      // Update cache
      queryClient.setQueryData(['profile'], data);
      
      // Invalidate issues since scores may change
      queryClient.invalidateQueries({ queryKey: ['issues'] });
    },
    ...options,
  });
}

/**
 * Import profile from GitHub
 */
export function useGitHubImport(options = {}) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () => profileService.importFromGitHub(),
    onSuccess: (data) => {
      queryClient.setQueryData(['profile'], data);
      queryClient.invalidateQueries({ queryKey: ['issues'] });
    },
    ...options,
  });
}
