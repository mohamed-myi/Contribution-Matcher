/**
 * First login prompt - asks user if they want to sync profile from GitHub.
 * Shown when a user logs in for the first time (no profile exists).
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from './common';
import './FirstLoginPrompt.css';

export function FirstLoginPrompt() {
  const navigate = useNavigate();
  const { 
    user, 
    showFirstLoginPrompt, 
    dismissFirstLoginPrompt, 
    syncFromGitHub,
    profileLoading 
  } = useAuth();
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);

  if (!showFirstLoginPrompt) return null;

  const handleSyncFromGitHub = async () => {
    try {
      setSyncing(true);
      setError(null);
      await syncFromGitHub();
      dismissFirstLoginPrompt();
      // Optionally navigate to dashboard or stay on current page
    } catch (err) {
      setError('Failed to sync from GitHub. You can try again from the Profile page.');
    } finally {
      setSyncing(false);
    }
  };

  const handleSkip = () => {
    dismissFirstLoginPrompt();
    navigate('/profile');
  };

  const handleManualSetup = () => {
    dismissFirstLoginPrompt();
    navigate('/profile');
  };

  return (
    <div className="first-login-overlay">
      <div className="first-login-modal">
        <div className="first-login-header">
          <h2>Welcome, {user?.github_username}!</h2>
          <p>Set up your developer profile to get personalized issue recommendations.</p>
        </div>

        <div className="first-login-body">
          <div className="first-login-option first-login-option-primary">
            <h3>Sync from GitHub</h3>
            <p>
              We can automatically extract your skills and interests from your 
              GitHub repositories. This is the quickest way to get started.
            </p>
            <Button 
              variant="primary" 
              onClick={handleSyncFromGitHub}
              loading={syncing || profileLoading}
              disabled={syncing || profileLoading}
            >
              {syncing ? 'Syncing...' : 'Yes, Sync from GitHub'}
            </Button>
          </div>

          {error && (
            <div className="first-login-error">
              {error}
            </div>
          )}

          <div className="first-login-divider">
            <span>or</span>
          </div>

          <div className="first-login-alternatives">
            <div className="first-login-alt-option">
              <h4>Manual Setup</h4>
              <p>Add your skills, interests, and preferences manually.</p>
              <Button variant="outline" onClick={handleManualSetup}>
                Set Up Manually
              </Button>
            </div>

            <div className="first-login-alt-option">
              <h4>Upload Resume</h4>
              <p>Extract skills from your PDF resume.</p>
              <Button variant="outline" onClick={handleManualSetup}>
                Go to Profile
              </Button>
            </div>
          </div>
        </div>

        <div className="first-login-footer">
          <button className="first-login-skip" onClick={handleSkip}>
            Skip for now
          </button>
          <p className="first-login-note">
            You can always change your profile settings later from the Profile page.
          </p>
        </div>
      </div>
    </div>
  );
}

export default FirstLoginPrompt;

