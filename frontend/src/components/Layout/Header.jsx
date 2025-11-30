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
            {theme === 'dark' ? 'Light' : 'Dark'}
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

