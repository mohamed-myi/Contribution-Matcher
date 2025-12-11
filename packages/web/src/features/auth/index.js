/**
 * Auth Feature Module
 * 
 * Handles authentication:
 * - Login/logout
 * - OAuth callback
 * - User context
 * - Protected routes
 */

// Components
export { default as LoginPage } from './components/LoginPage';
export { default as AuthCallback } from './components/AuthCallback';
export { default as ProtectedRoute } from './components/ProtectedRoute';

// Context
export { AuthProvider, useAuth } from './context/AuthContext';

// Hooks
export { useCurrentUser } from './hooks/useCurrentUser';
export { useLogout } from './hooks/useLogout';

// Services
export { authService } from './services/authService';
