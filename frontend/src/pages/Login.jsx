import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { AuthLayout } from '../components/Layout';
import { Button, Card } from '../components/common';
import { api } from '../api/client';
import './Login.css';

export function Login() {
  const { isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();

  // Redirect if already authenticated
  useEffect(() => {
    if (!loading && isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, loading, navigate]);

  const handleGitHubLogin = () => {
    window.location.href = api.getLoginUrl();
  };

  if (loading) {
    return null;
  }

  return (
    <AuthLayout>
      <Card variant="glass" padding="lg" className="login-card animate-slide-up">
        <div className="login-header">
          <div className="login-logo">
            <span className="login-logo-icon">◈</span>
          </div>
          <h1 className="login-title">Contribution Matcher</h1>
          <p className="login-subtitle">
            Find open source issues that match your skills
          </p>
        </div>

        <div className="login-content">
          <div className="login-action">
            <Button 
              variant="primary" 
              size="lg" 
              fullWidth
              onClick={handleGitHubLogin}
              icon={<GitHubIcon />}
            >
              Continue with GitHub
            </Button>

            <p className="login-terms">
              By continuing, you agree to our Terms of Service and Privacy Policy
            </p>
          </div>

          <div className="login-branding">
            <span className="login-branding-text">Brought to you by</span>
            <span className="login-myi">MYI</span>
          </div>
        </div>
      </Card>
    </AuthLayout>
  );
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

export default Login;
