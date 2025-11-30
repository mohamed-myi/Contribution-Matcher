import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { AuthLayout } from '../components/Layout';
import { PageLoader } from '../components/common';
import './AuthCallback.css';

export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState(null);

  useEffect(() => {
    const token = searchParams.get('token');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError(errorParam);
      return;
    }

    if (token) {
      login(token)
        .then(() => {
          navigate('/dashboard', { replace: true });
        })
        .catch((err) => {
          console.error('Login failed:', err);
          setError('Failed to complete authentication');
        });
    } else {
      setError('No authentication token received');
    }
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

