import { describe, it, expect, vi, beforeEach } from 'vitest';
import { waitFor } from '@testing-library/react';
import { Profile } from './Profile';
import { renderWithProviders } from '../test/test-utils';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    createProfileFromGithub: vi.fn(),
    createProfileFromResume: vi.fn(),
  },
}));

describe('Profile Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders profile page', async () => {
    api.getProfile.mockResolvedValue({
      data: {
        id: 1,
        skills: ['python'],
        experience_level: 'intermediate',
      },
    });

    renderWithProviders(<Profile />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1, github_username: 'testuser' },
        loading: false,
      },
    });

    await waitFor(() => {
      expect(api.getProfile).toHaveBeenCalled();
    });
  });

  it('shows loading state initially', () => {
    api.getProfile.mockImplementation(() => new Promise(() => {}));

    const { container } = renderWithProviders(<Profile />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1 },
        loading: false,
      },
    });

    // Should show skeleton profile when loading
    const skeletonProfiles = container.querySelectorAll('.skeleton-profile');
    expect(skeletonProfiles.length).toBeGreaterThan(0);
  });

  it('handles 404 when no profile exists', async () => {
    const error = { response: { status: 404 } };
    api.getProfile.mockRejectedValue(error);

    renderWithProviders(<Profile />, {
      authState: {
        isAuthenticated: true,
        user: { id: 1 },
        loading: false,
      },
    });

    await waitFor(() => {
      expect(api.getProfile).toHaveBeenCalled();
    });
  });
});
