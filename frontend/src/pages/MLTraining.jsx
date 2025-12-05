import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Card, CardHeader, CardBody, Button, Badge, DifficultyBadge, ScoreBadge, TechBadge, PageLoader, SkeletonCard, SkeletonProgressBar, SkeletonText } from '../components/common';
import { api } from '../api/client';
import './MLTraining.css';

export function MLTraining() {
  const [labelStatus, setLabelStatus] = useState(null);
  const [modelInfo, setModelInfo] = useState(null);
  const [unlabeledIssues, setUnlabeledIssues] = useState([]);
  const [currentIssue, setCurrentIssue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [labeling, setLabeling] = useState(false);
  const [error, setError] = useState(null);
  const [includeOthersIssues, setIncludeOthersIssues] = useState(false);
  const [discoverLanguage, setDiscoverLanguage] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [discoverMessage, setDiscoverMessage] = useState(null);
  const [trainingOptions, setTrainingOptions] = useState({
    use_advanced: true,
    use_stacking: false,
    use_tuning: false,
  });
  const [showExpanded, setShowExpanded] = useState(false);
  const [expandedData, setExpandedData] = useState({ scoreBreakdown: null, notes: [], loading: false });

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [statusRes, modelRes, issuesRes] = await Promise.all([
        api.getLabelStatus(),
        api.getModelInfo().catch(() => ({ data: null })),
        api.getUnlabeledIssues(50, includeOthersIssues),
      ]);
      setLabelStatus(statusRes.data);
      setModelInfo(modelRes.data);
      setUnlabeledIssues(issuesRes.data.issues || []);
      if (issuesRes.data.issues?.length > 0) {
        setCurrentIssue(issuesRes.data.issues[0]);
      } else {
        setCurrentIssue(null);
      }
      setError(null);
    } catch (err) {
      console.error('Failed to fetch ML data:', err);
      setError('Failed to load training data');
    } finally {
      setLoading(false);
    }
  }, [includeOthersIssues]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDiscover = useCallback(async () => {
    try {
      setDiscovering(true);
      setDiscoverMessage(null);
      
      const params = {};
      if (discoverLanguage) params.language = discoverLanguage;
      
      const response = await api.discoverIssues(params);
      const count = response.data?.discovered || response.data?.issues?.length || 0;
      
      setDiscoverMessage({ type: 'success', text: `Discovered ${count} new issues!` });
      
      // Refresh the unlabeled issues
      fetchData();
    } catch (err) {
      console.error('Failed to discover issues:', err);
      setDiscoverMessage({ type: 'error', text: 'Failed to discover issues. Try again.' });
    } finally {
      setDiscovering(false);
    }
  }, [discoverLanguage, fetchData]);

  const handleLabel = useCallback(async (label) => {
    if (!currentIssue || labeling) return;

    try {
      setLabeling(true);
      await api.labelIssue(currentIssue.id, label);
      
      // Update label status
      setLabelStatus((prev) => ({
        ...prev,
        labeled_count: (prev?.labeled_count || 0) + 1,
        [label === 'good' ? 'good_count' : 'bad_count']: 
          (prev?.[label === 'good' ? 'good_count' : 'bad_count'] || 0) + 1,
      }));

      // Move to next issue
      const currentIndex = unlabeledIssues.findIndex((i) => i.id === currentIssue.id);
      const nextIssue = unlabeledIssues[currentIndex + 1] || null;
      setCurrentIssue(nextIssue);
      
      // Remove labeled issue from list
      setUnlabeledIssues((prev) => prev.filter((i) => i.id !== currentIssue.id));
    } catch (err) {
      console.error('Failed to label issue:', err);
      setError('Failed to label issue');
    } finally {
      setLabeling(false);
    }
  }, [currentIssue, unlabeledIssues, labeling]);

  // Stable callback - uses functional updates to avoid dependency on currentIssue
  const handleBookmark = useCallback(async () => {
    // Get current issue from state at call time
    let issueId = null;
    let wasBookmarked = false;
    
    setCurrentIssue(prev => {
      if (!prev) return prev;
      issueId = prev.id;
      wasBookmarked = prev.is_bookmarked;
      return { ...prev, is_bookmarked: !prev.is_bookmarked };
    });
    
    // If no issue, bail
    if (issueId === null) return;
    
    // Update unlabeled issues list
    setUnlabeledIssues(prev => prev.map(issue => 
      issue.id === issueId ? { ...issue, is_bookmarked: !wasBookmarked } : issue
    ));
    
    try {
      if (wasBookmarked) {
        await api.removeBookmark(issueId);
      } else {
        await api.bookmarkIssue(issueId);
      }
    } catch (err) {
      console.error('Failed to update bookmark:', err);
      // Revert on error
      setCurrentIssue(prev => prev?.id === issueId ? { ...prev, is_bookmarked: wasBookmarked } : prev);
      setUnlabeledIssues(prev => prev.map(issue => 
        issue.id === issueId ? { ...issue, is_bookmarked: wasBookmarked } : issue
      ));
    }
  }, []); // No dependencies - fully stable callback

  // Reset expanded state when issue changes
  useEffect(() => {
    setShowExpanded(false);
    setExpandedData({ scoreBreakdown: null, notes: [], loading: false });
  }, [currentIssue?.id]);

  // Handle View More toggle
  const handleViewMore = useCallback(async () => {
    if (showExpanded) {
      setShowExpanded(false);
      return;
    }
    
    setShowExpanded(true);
    setExpandedData(prev => ({ ...prev, loading: true }));
    
    try {
      const [scoreRes, notesRes] = await Promise.all([
        api.getIssueScore(currentIssue.id).catch(() => null),
        api.getIssueNotes(currentIssue.id).catch(() => ({ data: { notes: [] } })),
      ]);
      
      setExpandedData({
        scoreBreakdown: scoreRes?.data || null,
        notes: notesRes?.data?.notes || [],
        loading: false,
      });
    } catch (err) {
      console.error('Failed to fetch expanded data:', err);
      setExpandedData(prev => ({ ...prev, loading: false }));
    }
  }, [showExpanded, currentIssue?.id]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      
      if (e.key === 'ArrowLeft' || e.key === 'b') {
        handleLabel('bad');
      } else if (e.key === 'ArrowRight' || e.key === 'g') {
        handleLabel('good');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleLabel]);

  const handleTrain = async () => {
    try {
      setTraining(true);
      await api.trainModel(trainingOptions);
      // Refresh model info
      const modelRes = await api.getModelInfo();
      setModelInfo(modelRes.data);
    } catch (err) {
      console.error('Failed to train model:', err);
      setError('Failed to train model');
    } finally {
      setTraining(false);
    }
  };

  const labeledCount = labelStatus?.labeled_count || 0;
  const requiredLabels = 200;
  const canTrain = labeledCount >= requiredLabels;
  const progress = Math.min((labeledCount / requiredLabels) * 100, 100);

  return (
    <Layout>
      <div className="ml-page animate-fade-in">
        <header className="ml-header">
          <div>
            <h1>Algorithm Improvement</h1>
            <p>Train a personalized model to improve issue matching</p>
          </div>
        </header>

        {error && (
          <div className="ml-error">
            <p>{error}</p>
            <Button variant="outline" size="sm" onClick={() => setError(null)}>
              Dismiss
            </Button>
          </div>
        )}

        {/* Discover Section */}
        <Card className="ml-discover-card">
          <CardBody>
            <div className="ml-discover-content">
              <div className="ml-discover-info">
                <h3>Build Your Training Dataset</h3>
                <p>
                  To train a personalized algorithm, you need to label at least 200 issues. 
                  Start by discovering issues from GitHub, then label them as "Like" or "Dislike" 
                  based on your preferences. The more diverse your training data, the better 
                  your algorithm will perform.
                </p>
                {discoverMessage && (
                  <div className={`ml-discover-message ml-discover-message-${discoverMessage.type}`}>
                    {discoverMessage.text}
                  </div>
                )}
              </div>
              <div className="ml-discover-controls">
                <div className="ml-discover-field">
                  <label>Language</label>
                  <select
                    value={discoverLanguage}
                    onChange={(e) => setDiscoverLanguage(e.target.value)}
                    disabled={discovering}
                  >
                    <option value="">All Languages</option>
                    {['JavaScript', 'Python', 'TypeScript', 'Java', 'Go', 'Rust', 'C++', 'C#', 'PHP', 'Ruby'].map(lang => (
                      <option key={lang} value={lang}>{lang}</option>
                    ))}
                  </select>
                </div>
                <Button
                  variant="primary"
                  onClick={handleDiscover}
                  loading={discovering}
                  disabled={discovering}
                >
                  {discovering ? 'Discovering...' : 'Discover Issues'}
                </Button>
              </div>
            </div>
            <div className="ml-discover-option">
              <label className="ml-discover-checkbox">
                <input
                  type="checkbox"
                  checked={includeOthersIssues}
                  onChange={(e) => setIncludeOthersIssues(e.target.checked)}
                />
                <span>Include issues found by other users</span>
              </label>
              <span className="ml-discover-hint">
                Enable this to label issues discovered by other users in the system
              </span>
            </div>
          </CardBody>
        </Card>

        <div className="ml-grid">
          {/* Labeling Interface */}
          <Card className="ml-labeling-card animate-slide-up stagger-1">
            <CardHeader>
              <h3>Quick Labeling</h3>
              <span className="ml-keyboard-hint">
                Use arrow keys or G/B
              </span>
            </CardHeader>
            <CardBody>
              {loading ? (
                <div className="labeling-interface">
                  <SkeletonCard />
                </div>
              ) : currentIssue ? (
                <div className="labeling-interface">
                  {/* Issue Header */}
                  <div className="labeling-issue">
                    <div className="labeling-issue-header">
                      <DifficultyBadge difficulty={currentIssue.difficulty} />
                      <ScoreBadge score={currentIssue.score || 0} />
                      <span className="labeling-issue-repo">
                        {currentIssue.repo_owner}/{currentIssue.repo_name}
                      </span>
                      {currentIssue.repo_stars && (
                        <span className="labeling-issue-stars">{currentIssue.repo_stars.toLocaleString()} stars</span>
                      )}
                    </div>
                    <h4 className="labeling-issue-title">{currentIssue.title}</h4>
                    
                    {/* Description - truncated or full based on expanded state */}
                    <p className="labeling-issue-description">
                      {showExpanded 
                        ? (currentIssue.description || 'No description available')
                        : (currentIssue.description?.slice(0, 300) + (currentIssue.description?.length > 300 ? '...' : ''))
                      }
                    </p>

                    {/* Technologies */}
                    {currentIssue.technologies?.length > 0 && (
                      <div className="labeling-issue-techs">
                        {(showExpanded ? currentIssue.technologies : currentIssue.technologies.slice(0, 5)).map((tech) => (
                          <TechBadge key={tech} tech={tech} />
                        ))}
                        {!showExpanded && currentIssue.technologies.length > 5 && (
                          <Badge variant="default" size="sm">+{currentIssue.technologies.length - 5}</Badge>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Expanded Details Section */}
                  {showExpanded && (
                    <div className="labeling-expanded">
                      {expandedData.loading ? (
                        <div className="labeling-expanded-loading">Loading details...</div>
                      ) : (
                        <>
                          {/* Score Breakdown */}
                          {expandedData.scoreBreakdown && (
                            <div className="labeling-expanded-section">
                              <h5>Score Breakdown</h5>
                              <div className="score-breakdown-inline">
                                {Object.entries(expandedData.scoreBreakdown.breakdown || {}).map(([key, value]) => (
                                  <div key={key} className="score-item-inline">
                                    <span className="score-item-label">{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                                    <div className="score-item-bar-inline">
                                      <div className="score-item-fill-inline" style={{ width: `${value}%` }} />
                                    </div>
                                    <span className="score-item-value">{Math.round(value)}%</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Notes */}
                          {expandedData.notes.length > 0 && (
                            <div className="labeling-expanded-section">
                              <h5>Notes</h5>
                              <div className="labeling-notes-list">
                                {expandedData.notes.map((note) => (
                                  <div key={note.id} className="labeling-note-item">
                                    <p>{note.content}</p>
                                    <span className="labeling-note-date">{new Date(note.created_at).toLocaleDateString()}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}

                  {/* Action Buttons - Always at bottom */}
                  <div className="labeling-actions-wrapper">
                    <div className="action-buttons-row">
                      <Button 
                        variant={currentIssue.is_bookmarked ? 'secondary' : 'outline'}
                        onClick={handleBookmark}
                        className="action-btn-equal"
                      >
                        {currentIssue.is_bookmarked ? 'Bookmarked' : 'Bookmark'}
                      </Button>
                      <Button 
                        variant={showExpanded ? 'secondary' : 'outline'}
                        onClick={handleViewMore}
                        className="action-btn-equal"
                      >
                        {showExpanded ? 'Show Less' : 'View More'}
                      </Button>
                      <Button 
                        variant="primary"
                        onClick={() => window.open(currentIssue.url || `https://github.com/${currentIssue.repo_owner}/${currentIssue.repo_name}/issues/${currentIssue.issue_number}`, '_blank')}
                        className="action-btn-equal"
                      >
                        Open in GitHub
                      </Button>
                    </div>

                    <div className="labeling-actions">
                      <Button 
                        variant="danger" 
                        size="lg"
                        onClick={() => handleLabel('bad')}
                        loading={labeling}
                        className="labeling-btn labeling-btn-bad"
                      >
                        Dislike
                      </Button>
                      <Button 
                        variant="success" 
                        size="lg"
                        onClick={() => handleLabel('good')}
                        loading={labeling}
                        className="labeling-btn labeling-btn-good"
                      >
                        Like
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="labeling-empty">
                  <span className="labeling-empty-icon">Done</span>
                  <p>All issues labeled!</p>
                  <Button variant="outline" onClick={fetchData}>
                    Refresh
                  </Button>
                </div>
              )}
            </CardBody>
          </Card>

          {/* Progress & Training */}
          <div className="ml-sidebar">
            {/* Label Progress */}
            <Card className="ml-progress-card animate-slide-up stagger-2">
              <CardHeader>
                <h3>Label Progress</h3>
              </CardHeader>
              <CardBody>
                {loading ? (
                  <div className="label-progress">
                    <SkeletonProgressBar />
                    <SkeletonText lines={2} />
                  </div>
                ) : (
                  <div className="label-progress">
                    <div className="label-progress-bar">
                      <div 
                        className="label-progress-fill"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <div className="label-progress-text">
                      <span className="label-progress-count">
                        {labeledCount} / {requiredLabels}
                      </span>
                      <span className="label-progress-percent">
                        {Math.round(progress)}%
                      </span>
                    </div>
                    <div className="label-stats">
                      <div className="label-stat">
                        <span className="label-stat-value label-stat-good">
                          {labelStatus?.good_count || 0}
                        </span>
                        <span className="label-stat-label">Liked</span>
                      </div>
                      <div className="label-stat">
                        <span className="label-stat-value label-stat-bad">
                          {labelStatus?.bad_count || 0}
                        </span>
                        <span className="label-stat-label">Disliked</span>
                      </div>
                    </div>
                    <div className="label-progress-note">
                      Aim for 50/50 ratio.
                    </div>
                    {labeledCount > 0 && (
                      <Link to="/algorithm-improvement/labeled" className="view-labeled-link">
                        View and Edit Labeled Issues
                      </Link>
                    )}
                  </div>
                )}
              </CardBody>
            </Card>

            {/* Training Panel */}
            <Card className="ml-training-card animate-slide-up stagger-3">
              <CardHeader>
                <h3>Train Algorithm</h3>
              </CardHeader>
              <CardBody>
                <div className="training-options">
                  <label className="training-option">
                    <input
                      type="checkbox"
                      checked={trainingOptions.use_advanced}
                      onChange={(e) => setTrainingOptions({ ...trainingOptions, use_advanced: e.target.checked })}
                    />
                    <span>Advanced Features</span>
                  </label>
                  <label className="training-option">
                    <input
                      type="checkbox"
                      checked={trainingOptions.use_stacking}
                      onChange={(e) => setTrainingOptions({ ...trainingOptions, use_stacking: e.target.checked })}
                    />
                    <span>Algorithm Stacking</span>
                  </label>
                  <label className="training-option">
                    <input
                      type="checkbox"
                      checked={trainingOptions.use_tuning}
                      onChange={(e) => setTrainingOptions({ ...trainingOptions, use_tuning: e.target.checked })}
                    />
                    <span>Hyperparameter Tuning</span>
                  </label>
                </div>

                <Button 
                  variant="primary" 
                  fullWidth
                  onClick={handleTrain}
                  loading={training}
                  disabled={!canTrain}
                >
                  {canTrain ? 'Train Algorithm' : `Need ${requiredLabels - labeledCount} more labels`}
                </Button>
              </CardBody>
            </Card>

            {/* Algorithm Info */}
            {modelInfo && (
              <Card className="ml-model-card animate-slide-up stagger-4">
                <CardHeader>
                  <h3>Current Algorithm</h3>
                  <Badge variant="success" size="sm">Active</Badge>
                </CardHeader>
                <CardBody>
                  <div className="model-metrics">
                    <div className="model-metric">
                      <span className="model-metric-label">Accuracy</span>
                      <span className="model-metric-value">
                        {(modelInfo.metrics?.accuracy * 100 || 0).toFixed(1)}%
                      </span>
                    </div>
                    <div className="model-metric">
                      <span className="model-metric-label">Precision</span>
                      <span className="model-metric-value">
                        {(modelInfo.metrics?.precision * 100 || 0).toFixed(1)}%
                      </span>
                    </div>
                    <div className="model-metric">
                      <span className="model-metric-label">Recall</span>
                      <span className="model-metric-value">
                        {(modelInfo.metrics?.recall * 100 || 0).toFixed(1)}%
                      </span>
                    </div>
                    <div className="model-metric">
                      <span className="model-metric-label">F1 Score</span>
                      <span className="model-metric-value">
                        {(modelInfo.metrics?.f1 * 100 || 0).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="model-info-footer">
                    <span>Trained: {modelInfo.trained_at ? new Date(modelInfo.trained_at).toLocaleDateString() : 'N/A'}</span>
                    <span>Samples: {modelInfo.training_samples || 0}</span>
                  </div>
                </CardBody>
              </Card>
            )}
          </div>
        </div>
      </div>

    </Layout>
  );
}

export default MLTraining;

