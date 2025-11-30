import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Card, CardHeader, CardBody, Button, Badge, ScoreBadge, DifficultyBadge, PageLoader } from '../components/common';
import { api } from '../api/client';
import './Dashboard.css';

const PROGRAMMING_LANGUAGES = [
  'Python', 'JavaScript', 'TypeScript', 'Java', 'C++', 'C#', 'Go', 'Rust',
  'Ruby', 'PHP', 'Swift', 'Kotlin', 'Scala', 'C', 'Shell'
];

export function Dashboard() {
  const [stats, setStats] = useState(null);
  const [topMatches, setTopMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState('');

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
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
  };

  const handleDiscoverIssues = async () => {
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
  };

  if (loading) {
    return (
      <Layout>
        <PageLoader message="Loading dashboard..." />
      </Layout>
    );
  }

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
          <StatsCard
            title="Total Issues"
            value={stats?.total || 0}
            delay={1}
          />
          <StatsCard
            title="Bookmarked"
            value={stats?.bookmarked || 0}
            delay={2}
          />
          <StatsCard
            title="Labeled"
            value={stats?.labeled || 0}
            delay={3}
          />
          <StatsCard
            title="Top Score"
            value={stats?.top_score ? `${Math.round(stats.top_score)}%` : 'N/A'}
            delay={4}
          />
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
              {topMatches.length === 0 ? (
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
                <Link to="/ml-training" className="quick-action-card">
                  <span className="quick-action-label">Train Model</span>
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
      </div>
    </Layout>
  );
}

function StatsCard({ title, value, delay }) {
  return (
    <Card hover className={`stats-card animate-slide-up stagger-${delay}`}>
      <div className="stats-card-content">
        <span className="stats-card-bullet">•</span>
        <div className="stats-card-info">
          <span className="stats-card-value">{value}</span>
          <span className="stats-card-title">{title}</span>
        </div>
      </div>
    </Card>
  );
}

function IssueRow({ issue }) {
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
}

function DifficultyBar({ label, count, total, variant }) {
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
}

export default Dashboard;

