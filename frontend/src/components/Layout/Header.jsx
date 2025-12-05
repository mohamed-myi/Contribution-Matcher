import { useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button, PreloadLink } from '../common';
import { usePrefetchStats, usePrefetchIssues } from '../../hooks';
import { lazyRoutes } from '../../App';
import './Header.css';

export function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  
  // Prefetch hooks for navigation optimization
  const prefetchStats = usePrefetchStats();
  const prefetchIssues = usePrefetchIssues();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Prefetch data on link hover for faster navigation
  const handleDashboardHover = useCallback(() => {
    prefetchStats();
  }, [prefetchStats]);

  const handleIssuesHover = useCallback(() => {
    prefetchIssues({ limit: 20, offset: 0 });
  }, [prefetchIssues]);

  return (
    <header className="header">
      <div className="header-container">
        <PreloadLink 
          to="/dashboard" 
          className="header-logo" 
          preload={lazyRoutes.Dashboard}
          onMouseEnter={handleDashboardHover}
        >
          <span className="header-logo-icon">MYI</span>
          <span className="header-logo-text">IssueIndex</span>
        </PreloadLink>

        <nav className="header-nav">
          <PreloadLink 
            to="/dashboard" 
            className="header-nav-link"
            preload={lazyRoutes.Dashboard}
            onMouseEnter={handleDashboardHover}
          >
            Dashboard
          </PreloadLink>
          <PreloadLink 
            to="/issues" 
            className="header-nav-link"
            preload={lazyRoutes.Issues}
            onMouseEnter={handleIssuesHover}
          >
            Issues
          </PreloadLink>
          <PreloadLink 
            to="/profile" 
            className="header-nav-link"
            preload={lazyRoutes.Profile}
          >
            Profile
          </PreloadLink>
          <PreloadLink 
            to="/algorithm-improvement" 
            className="header-nav-link"
            preload={lazyRoutes.MLTraining}
          >
            Algorithm Improvement
          </PreloadLink>
        </nav>

        <div className="header-user">
          {user && (
            <>
              <div className="header-user-info">
                <img 
                  src={user.avatar_url || `https://github.com/${user.github_username}.png`} 
                  alt={user.github_username}
                  className="header-avatar"
                />
                <span className="header-username">{user.github_username}</span>
              </div>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                Logout
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export default Header;

