import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Card, CardHeader, CardBody, Button, Badge, DifficultyBadge, TechBadge, PageLoader, SkeletonList } from '../components/common';
import { api } from '../api/client';
import './LabeledIssues.css';

export function LabeledIssues() {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all', 'good', 'bad'
  const [stats, setStats] = useState({ total: 0, good_count: 0, bad_count: 0 });
  const [updating, setUpdating] = useState(null); // issue id being updated

  const fetchLabeledIssues = useCallback(async () => {
    try {
      setLoading(true);
      const labelFilter = filter === 'all' ? null : filter;
      const response = await api.getLabeledIssues(100, 0, labelFilter);
      setIssues(response.data.issues || []);
      setStats({
        total: response.data.total,
        good_count: response.data.good_count,
        bad_count: response.data.bad_count,
      });
      setError(null);
    } catch (err) {
      console.error('Failed to fetch labeled issues:', err);
      setError('Failed to load labeled issues');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchLabeledIssues();
  }, [fetchLabeledIssues]);

  const handleChangeLabel = async (issueId, newLabel) => {
    try {
      setUpdating(issueId);
      await api.labelIssue(issueId, newLabel);
      // Update local state optimistically
      setIssues(prev => prev.map(issue => 
        issue.id === issueId ? { ...issue, label: newLabel } : issue
      ));
      // Update stats
      setStats(prev => {
        const wasGood = issues.find(i => i.id === issueId)?.label === 'good';
        const isNowGood = newLabel === 'good';
        if (wasGood && !isNowGood) {
          return { ...prev, good_count: prev.good_count - 1, bad_count: prev.bad_count + 1 };
        } else if (!wasGood && isNowGood) {
          return { ...prev, good_count: prev.good_count + 1, bad_count: prev.bad_count - 1 };
        }
        return prev;
      });
    } catch (err) {
      console.error('Failed to update label:', err);
      setError('Failed to update label');
    } finally {
      setUpdating(null);
    }
  };

  const handleRemoveLabel = async (issueId) => {
    try {
      setUpdating(issueId);
      await api.removeLabel(issueId);
      // Remove from list and update stats
      const removedIssue = issues.find(i => i.id === issueId);
      setIssues(prev => prev.filter(issue => issue.id !== issueId));
      setStats(prev => ({
        total: prev.total - 1,
        good_count: removedIssue?.label === 'good' ? prev.good_count - 1 : prev.good_count,
        bad_count: removedIssue?.label === 'bad' ? prev.bad_count - 1 : prev.bad_count,
      }));
    } catch (err) {
      console.error('Failed to remove label:', err);
      setError('Failed to remove label');
    } finally {
      setUpdating(null);
    }
  };

  return (
    <Layout>
      <div className="labeled-page animate-fade-in">
        <header className="labeled-header">
          <div className="labeled-header-top">
            <Link to="/algorithm-improvement" className="labeled-back-link">
              Back to Algorithm Improvement
            </Link>
          </div>
          <div className="labeled-header-content">
            <div>
              <h1>Labeled Issues</h1>
              <p>View and edit your labeled issues for algorithm training</p>
            </div>
            <div className="labeled-stats">
              <div className="labeled-stat">
                <span className="labeled-stat-value">{stats.total}</span>
                <span className="labeled-stat-label">Total</span>
              </div>
              <div className="labeled-stat labeled-stat-good">
                <span className="labeled-stat-value">{stats.good_count}</span>
                <span className="labeled-stat-label">Liked</span>
              </div>
              <div className="labeled-stat labeled-stat-bad">
                <span className="labeled-stat-value">{stats.bad_count}</span>
                <span className="labeled-stat-label">Disliked</span>
              </div>
            </div>
          </div>
        </header>

        {error && (
          <div className="labeled-error">
            <p>{error}</p>
            <Button variant="outline" size="sm" onClick={() => setError(null)}>
              Dismiss
            </Button>
          </div>
        )}

        {/* Filter Tabs */}
        <div className="labeled-filters">
          <button
            className={`labeled-filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({stats.total})
          </button>
          <button
            className={`labeled-filter-btn ${filter === 'good' ? 'active' : ''}`}
            onClick={() => setFilter('good')}
          >
            Liked ({stats.good_count})
          </button>
          <button
            className={`labeled-filter-btn ${filter === 'bad' ? 'active' : ''}`}
            onClick={() => setFilter('bad')}
          >
            Disliked ({stats.bad_count})
          </button>
        </div>

        {/* Issues List */}
        {loading ? (
          <SkeletonList count={5} type="card" />
        ) : issues.length === 0 ? (
          <Card className="labeled-empty">
            <CardBody>
              <div className="labeled-empty-content">
                <h3>No Labeled Issues</h3>
                <p>
                  {filter === 'all' 
                    ? "You haven't labeled any issues yet. Go to Algorithm Improvement to start labeling."
                    : `No issues labeled as "${filter === 'good' ? 'Liked' : 'Disliked'}".`
                  }
                </p>
                <Link to="/algorithm-improvement">
                  <Button variant="primary">Start Labeling</Button>
                </Link>
              </div>
            </CardBody>
          </Card>
        ) : (
          <div className="labeled-list">
            {issues.map((issue) => (
              <Card key={issue.id} className="labeled-issue-card animate-slide-up">
                <CardBody>
                  <div className="labeled-issue-row">
                    <div className="labeled-issue-info">
                      <div className="labeled-issue-header">
                        <DifficultyBadge difficulty={issue.difficulty} />
                        <span className="labeled-issue-repo">
                          {issue.repo_owner}/{issue.repo_name}
                        </span>
                        {issue.repo_stars && (
                          <span className="labeled-issue-stars">
                            {issue.repo_stars.toLocaleString()} stars
                          </span>
                        )}
                      </div>
                      <h3 className="labeled-issue-title">{issue.title}</h3>
                      {issue.description && (
                        <p className="labeled-issue-description">{issue.description}</p>
                      )}
                      {issue.technologies?.length > 0 && (
                        <div className="labeled-issue-techs">
                          {issue.technologies.slice(0, 5).map((tech) => (
                            <TechBadge key={tech} tech={tech} />
                          ))}
                          {issue.technologies.length > 5 && (
                            <Badge variant="outline" size="sm">+{issue.technologies.length - 5}</Badge>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="labeled-issue-actions">
                      <div className="labeled-issue-current-label">
                        <span className={`label-badge label-badge-${issue.label}`}>
                          {issue.label === 'good' ? 'Liked' : 'Disliked'}
                        </span>
                      </div>
                      
                      <div className="labeled-issue-buttons">
                        <button
                          className={`label-toggle-btn label-toggle-good ${issue.label === 'good' ? 'active' : ''}`}
                          onClick={() => handleChangeLabel(issue.id, 'good')}
                          disabled={updating === issue.id || issue.label === 'good'}
                          title="Mark as Liked"
                        >
                          Like
                        </button>
                        <button
                          className={`label-toggle-btn label-toggle-bad ${issue.label === 'bad' ? 'active' : ''}`}
                          onClick={() => handleChangeLabel(issue.id, 'bad')}
                          disabled={updating === issue.id || issue.label === 'bad'}
                          title="Mark as Disliked"
                        >
                          Dislike
                        </button>
                        <button
                          className="label-remove-btn"
                          onClick={() => handleRemoveLabel(issue.id)}
                          disabled={updating === issue.id}
                          title="Remove label"
                        >
                          Remove
                        </button>
                      </div>

                      <a
                        href={issue.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="labeled-issue-view-btn"
                      >
                        View on GitHub
                      </a>
                    </div>
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}

export default LabeledIssues;

