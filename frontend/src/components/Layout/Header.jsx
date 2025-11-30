import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { Button } from '../common';
import './Header.css';

export function Header() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="header">
      <div className="header-container">
        <Link to="/dashboard" className="header-logo">
          <span className="header-logo-icon">◈</span>
          <span className="header-logo-text">Contribution Matcher</span>
        </Link>

        <nav className="header-nav">
          <Link to="/dashboard" className="header-nav-link">Dashboard</Link>
          <Link to="/issues" className="header-nav-link">Issues</Link>
          <Link to="/profile" className="header-nav-link">Profile</Link>
          <Link to="/ml-training" className="header-nav-link">ML Training</Link>
        </nav>

        <div className="header-user">
          <button 
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? (
              <svg className="theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="5"/>
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
              </svg>
            ) : (
              <svg className="theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            )}
          </button>
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

