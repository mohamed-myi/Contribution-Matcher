import { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { AuthLayout } from '../components/Layout';
import { PageLoader } from '../components/common';
import './AuthCallback.css';

export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState(null);
  const isProcessing = useRef(false);

  useEffect(() => {
    // Prevent double execution (React 18 Strict Mode runs effects twice)
    if (isProcessing.current) return;
    isProcessing.current = true;

    const authCode = searchParams.get('code');
    const token = searchParams.get('token');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError(errorParam === 'authentication_failed' 
        ? 'Authentication failed. Please try again.' 
        : errorParam);
      return;
    }

    // New secure flow: exchange auth code for JWT token
    if (authCode) {
      api.exchangeAuthCode(authCode)
        .then((response) => {
          const jwtToken = response.data.access_token;
          return login(jwtToken);
        })
        .then(() => {
          navigate('/dashboard', { replace: true });
        })
        .catch((err) => {
          console.error('Auth code exchange failed:', err);
          setError('Failed to complete authentication. Please try again.');
        });
      return;
    }

    // Legacy fallback: direct token in URL (when Redis unavailable)
    if (token) {
      login(token)
        .then(() => {
          navigate('/dashboard', { replace: true });
        })
        .catch((err) => {
          console.error('Login failed:', err);
          setError('Failed to complete authentication');
        });
      return;
    }

    setError('No authentication credentials received');
  }, [searchParams, login, navigate]);

  if (error) {
    return (
      <AuthLayout>
        <div className="auth-callback-error animate-slide-up">
          <div className="auth-callback-error-icon">X</div>
          <h2>Authentication Failed</h2>
          <p>{error}</p>
          <a href="/login" className="auth-callback-retry">
            Try Again
          </a>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <div className="auth-callback">
        <PageLoader message="Completing authentication..." />
      </div>
    </AuthLayout>
  );
}

export default AuthCallback;

