import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { PageLoader } from './components/common';
import { FirstLoginPrompt } from './components/FirstLoginPrompt';
import { preloadRoutes } from './utils/routePreloader';
import { createQueryClient, setupPersistentCache, warmCache } from './utils/queryClient';
import { api } from './api/client';
import './styles/global.css';

// Eager-loaded pages (critical auth path)
import { Login, AuthCallback } from './pages';

// Lazy-loaded pages (behind authentication)
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const Issues = lazy(() => import('./pages/Issues').then(m => ({ default: m.Issues })));
const Profile = lazy(() => import('./pages/Profile').then(m => ({ default: m.Profile })));
const MLTraining = lazy(() => import('./pages/MLTraining').then(m => ({ default: m.MLTraining })));
const LabeledIssues = lazy(() => import('./pages/LabeledIssues').then(m => ({ default: m.LabeledIssues })));

// Export lazy components for preloading
export const lazyRoutes = {
  Dashboard,
  Issues,
  Profile,
  MLTraining,
  LabeledIssues,
};

// Create React Query client with enhanced configuration
const queryClient = createQueryClient();

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <PageLoader message="Checking authentication..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Suspense boundary for lazy-loaded pages
  return (
    <Suspense fallback={<PageLoader message="Loading page..." />}>
      {children}
    </Suspense>
  );
}

function PublicRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <PageLoader message="Loading..." />;
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

function AppRoutes() {
  const { isAuthenticated } = useAuth();
  
  // Preload critical routes after authentication
  useEffect(() => {
    if (isAuthenticated) {
      // Preload Dashboard and Issues (most accessed) after idle
      if ('requestIdleCallback' in window) {
        requestIdleCallback(() => {
          preloadRoutes([Dashboard, Issues]);
        }, { timeout: 2000 });
      } else {
        setTimeout(() => {
          preloadRoutes([Dashboard, Issues]);
        }, 2000);
      }
    }
  }, [isAuthenticated]);
  
  return (
    <Routes>
      {/* Public Routes */}
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        } 
      />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Protected Routes */}
      <Route 
        path="/dashboard" 
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/issues" 
        element={
          <ProtectedRoute>
            <Issues />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/issues/:id" 
        element={
          <ProtectedRoute>
            <Issues />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/profile" 
        element={
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/algorithm-improvement" 
        element={
          <ProtectedRoute>
            <MLTraining />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/algorithm-improvement/labeled" 
        element={
          <ProtectedRoute>
            <LabeledIssues />
          </ProtectedRoute>
        } 
      />
      {/* Default Redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  // Setup persistent cache on mount
  useEffect(() => {
    setupPersistentCache(queryClient);
  }, []);
  
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <CacheWarmer />
          <FirstLoginPrompt />
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

// Component to warm cache after authentication
function CacheWarmer() {
  const { isAuthenticated } = useAuth();
  
  useEffect(() => {
    if (isAuthenticated) {
      warmCache(queryClient, api, isAuthenticated);
    }
  }, [isAuthenticated]);
  
  return null;
}

export default App;
