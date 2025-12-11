import { useState, useEffect, useCallback, memo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Card, CardHeader, CardBody, Button, Badge, ScoreBadge, DifficultyBadge, PageLoader, SkeletonStatsCard, SkeletonRow, SkeletonList } from '../components/common';
import { api } from '../api/client';
import './Dashboard.css';

const PROGRAMMING_LANGUAGES = [
  'Python', 'JavaScript', 'TypeScript', 'Java', 'C++', 'C#', 'Go', 'Rust',
  'Ruby', 'PHP', 'Swift', 'Kotlin', 'Scala', 'C', 'Shell'
];

export function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [topMatches, setTopMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState('');
  
  // Bookmarks modal state
  const [showBookmarksModal, setShowBookmarksModal] = useState(false);
  const [bookmarkedIssues, setBookmarkedIssues] = useState([]);
  const [loadingBookmarks, setLoadingBookmarks] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsRes, matchesRes] = await Promise.all([
        api.getIssueStats(),
        api.getTopMatches(5),
      ]);
      setStats(statsRes.data);
      setTopMatches(matchesRes.data.issues || []);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const handleDiscoverIssues = useCallback(async () => {
    try {
      setDiscovering(true);
      // Don't pass labels - let backend choose based on user's experience level
      const params = { limit: 50 };
      if (selectedLanguage) {
        params.language = selectedLanguage;
      }
      await api.discoverIssues(params);
      // Refresh data after discovery
      await fetchDashboardData();
    } catch (err) {
      console.error('Failed to discover issues:', err);
      setError('Failed to discover new issues');
    } finally {
      setDiscovering(false);
    }
  }, [selectedLanguage, fetchDashboardData]);

  const handleOpenBookmarks = useCallback(async () => {
    // Only open modal if there are bookmarks
    if (!stats?.bookmarked || stats.bookmarked === 0) {
      return;
    }
    
    setShowBookmarksModal(true);
    setLoadingBookmarks(true);
    
    try {
      const response = await api.getBookmarks();
      setBookmarkedIssues(response.data.issues || []);
    } catch (err) {
      console.error('Failed to fetch bookmarks:', err);
    } finally {
      setLoadingBookmarks(false);
    }
  }, [stats?.bookmarked]);

  const handleCloseBookmarksModal = useCallback(() => {
    setShowBookmarksModal(false);
  }, []);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (showBookmarksModal) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [showBookmarksModal]);

  return (
    <Layout>
      <div className="dashboard animate-fade-in">
        <header className="dashboard-header">
          <div>
            <h1>Dashboard</h1>
            <p>Your contribution matching overview</p>
          </div>
          <div className="dashboard-actions">
            <select 
              className="language-select"
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              disabled={loading}
            >
              <option value="">All Languages</option>
              {PROGRAMMING_LANGUAGES.map(lang => (
                <option key={lang} value={lang}>{lang}</option>
              ))}
            </select>
            <Button 
              variant="primary" 
              onClick={handleDiscoverIssues}
              loading={discovering}
              disabled={loading}
            >
              Discover Issues
            </Button>
          </div>
        </header>

        {error && (
          <div className="dashboard-error">
            <p>{error}</p>
            <Button variant="outline" size="sm" onClick={fetchDashboardData}>
              Retry
            </Button>
          </div>
        )}

        {/* Stats Grid */}
        <div className="dashboard-stats">
          {loading ? (
            <>
              <SkeletonStatsCard />
              <SkeletonStatsCard />
              <SkeletonStatsCard />
              <SkeletonStatsCard />
            </>
          ) : (
            <>
              <StatsCard
                title="Total Issues"
                value={stats?.total || 0}
                delay={1}
                onClick={() => navigate('/issues')}
                variant="clickable"
              />
              <StatsCard
                title="Bookmarked"
                value={stats?.bookmarked || 0}
                delay={2}
                onClick={handleOpenBookmarks}
                variant={stats?.bookmarked > 0 ? "clickable" : "empty"}
                emptyMessage="No bookmarks"
              />
              <StatsCard
                title="Labeled"
                value={stats?.labeled || 0}
                delay={3}
                onClick={() => navigate('/algorithm-improvement/labeled')}
                variant="clickable"
              />
              <StatsCard
                title="Top Score"
                value={stats?.top_score ? `${Math.round(stats.top_score)}%` : 'N/A'}
                delay={4}
                variant="static"
              />
            </>
          )}
        </div>

        {/* Main Content Grid */}
        <div className="dashboard-grid">
          {/* Top Matches */}
          <Card className="dashboard-card animate-slide-up stagger-1">
            <CardHeader>
              <h3>Top Matches</h3>
              <Link to="/issues" className="dashboard-card-link">View All</Link>
            </CardHeader>
            <CardBody>
              {loading ? (
                <SkeletonList count={5} type="row" />
              ) : topMatches.length === 0 ? (
                <div className="dashboard-empty">
                  <p>No matched issues yet</p>
                  <Button variant="outline" size="sm" onClick={handleDiscoverIssues}>
                    Discover Issues
                  </Button>
                </div>
              ) : (
                <div className="dashboard-issues-list">
                  {topMatches.map((issue) => (
                    <IssueRow key={issue.id} issue={issue} />
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          {/* Quick Actions */}
          <Card className="dashboard-card animate-slide-up stagger-2">
            <CardHeader>
              <h3>Quick Actions</h3>
            </CardHeader>
            <CardBody>
              <div className="dashboard-quick-actions">
                <Link to="/issues" className="quick-action-card">
                  <span className="quick-action-label">Browse Issues</span>
                </Link>
                <Link to="/profile" className="quick-action-card">
                  <span className="quick-action-label">Edit Profile</span>
                </Link>
                <Link to="/algorithm-improvement" className="quick-action-card">
                  <span className="quick-action-label">Improve Algorithm</span>
                </Link>
                <Link to="/issues?bookmarked=true" className="quick-action-card">
                  <span className="quick-action-label">Bookmarks</span>
                </Link>
              </div>
            </CardBody>
          </Card>

          {/* Difficulty Breakdown */}
          <Card className="dashboard-card animate-slide-up stagger-3">
            <CardHeader>
              <h3>By Difficulty</h3>
            </CardHeader>
            <CardBody>
              <div className="dashboard-difficulty">
                <DifficultyBar 
                  label="Beginner" 
                  count={stats?.by_difficulty?.beginner || 0}
                  total={stats?.total || 1}
                  variant="beginner"
                />
                <DifficultyBar 
                  label="Intermediate" 
                  count={stats?.by_difficulty?.intermediate || 0}
                  total={stats?.total || 1}
                  variant="intermediate"
                />
                <DifficultyBar 
                  label="Advanced" 
                  count={stats?.by_difficulty?.advanced || 0}
                  total={stats?.total || 1}
                  variant="advanced"
                />
              </div>
            </CardBody>
          </Card>
        </div>

        {/* Bookmarks Modal */}
        {showBookmarksModal && (
          <BookmarksModal
            isOpen={showBookmarksModal}
            onClose={handleCloseBookmarksModal}
            issues={bookmarkedIssues}
            loading={loadingBookmarks}
          />
        )}
      </div>
    </Layout>
  );
}

// Bookmarks Modal Component
const BookmarksModal = memo(function BookmarksModal({ isOpen, onClose, issues, loading }) {
  if (!isOpen) return null;

  return (
    <div className="bookmarks-modal-overlay" onClick={onClose}>
      <div className="bookmarks-modal" onClick={(e) => e.stopPropagation()}>
        <div className="bookmarks-modal-header">
          <h2>Bookmarked Issues</h2>
          <button className="bookmarks-modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        
        <div className="bookmarks-modal-content">
          {loading ? (
            <div className="bookmarks-modal-loading">
              <span>Loading bookmarks...</span>
            </div>
          ) : issues.length === 0 ? (
            <div className="bookmarks-modal-empty">
              <p>You have no bookmarked issues.</p>
            </div>
          ) : (
            <div className="bookmarks-modal-list">
              {issues.map((issue) => (
                <div key={issue.id} className="bookmarks-modal-item">
                  <div className="bookmarks-item-info">
                    <div className="bookmarks-item-header">
                      <DifficultyBadge difficulty={issue.difficulty} size="sm" />
                      <span className="bookmarks-item-stars">
                        {issue.repo_stars?.toLocaleString() || 0} stars
                      </span>
                    </div>
                    <h4 className="bookmarks-item-title">{issue.title}</h4>
                    <p className="bookmarks-item-description">
                      {issue.description 
                        ? (issue.description.length > 150 
                            ? issue.description.substring(0, 150) + '...' 
                            : issue.description)
                        : 'No description available'}
                    </p>
                  </div>
                  <div className="bookmarks-item-actions">
                    <a
                      href={issue.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="bookmarks-item-btn bookmarks-item-github-btn"
                    >
                      Open in GitHub
                    </a>
                    <Link 
                      to={`/issues/${issue.id}`} 
                      className="bookmarks-item-btn bookmarks-item-view-btn"
                      onClick={onClose}
                    >
                      View Issue
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

const StatsCard = memo(function StatsCard({ title, value, delay, onClick, variant = "static", emptyMessage }) {
  const isClickable = variant === "clickable" || (variant === "empty" && value > 0);
  const isStatic = variant === "static";
  const isEmpty = variant === "empty" && value === 0;
  
  const cardClasses = [
    'stats-card',
    `animate-slide-up`,
    `stagger-${delay}`,
    isClickable ? 'stats-card-clickable' : '',
    isStatic ? 'stats-card-static' : '',
    isEmpty ? 'stats-card-empty' : '',
  ].filter(Boolean).join(' ');

  const handleClick = () => {
    if (isClickable && onClick) {
      onClick();
    }
  };

  return (
    <Card 
      hover={isClickable} 
      className={cardClasses}
      onClick={handleClick}
    >
      <div className="stats-card-content">
        <span className="stats-card-bullet">•</span>
        <div className="stats-card-info">
          <span className="stats-card-value">{value}</span>
          <span className="stats-card-title">{title}</span>
          {isEmpty && emptyMessage && (
            <span className="stats-card-empty-message">{emptyMessage}</span>
          )}
        </div>
      </div>
    </Card>
  );
});

const IssueRow = memo(function IssueRow({ issue }) {
  return (
    <Link to={`/issues/${issue.id}`} className="issue-row">
      <div className="issue-row-main">
        <h4 className="issue-row-title">{issue.title}</h4>
        <span className="issue-row-repo">{issue.repo_owner}/{issue.repo_name}</span>
      </div>
      <div className="issue-row-meta">
        <DifficultyBadge difficulty={issue.difficulty} size="sm" />
        <ScoreBadge score={issue.score || 0} size="sm" />
      </div>
    </Link>
  );
});

const DifficultyBar = memo(function DifficultyBar({ label, count, total, variant }) {
  const percentage = total > 0 ? (count / total) * 100 : 0;
  
  return (
    <div className="difficulty-bar">
      <div className="difficulty-bar-header">
        <span className="difficulty-bar-label">{label}</span>
        <span className="difficulty-bar-count">{count}</span>
      </div>
      <div className="difficulty-bar-track">
        <div 
          className={`difficulty-bar-fill difficulty-bar-${variant}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
});

export default Dashboard;

