import { useState, useEffect, useCallback } from 'react';
import { Layout } from '../components/Layout';
import { Card, CardHeader, CardBody, Button, Badge, DifficultyBadge, PageLoader } from '../components/common';
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
  const [trainingOptions, setTrainingOptions] = useState({
    use_advanced: true,
    use_stacking: false,
    use_tuning: false,
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statusRes, modelRes, issuesRes] = await Promise.all([
        api.getLabelStatus(),
        api.getModelInfo().catch(() => ({ data: null })),
        api.getUnlabeledIssues(50),
      ]);
      setLabelStatus(statusRes.data);
      setModelInfo(modelRes.data);
      setUnlabeledIssues(issuesRes.data.issues || []);
      if (issuesRes.data.issues?.length > 0) {
        setCurrentIssue(issuesRes.data.issues[0]);
      }
      setError(null);
    } catch (err) {
      console.error('Failed to fetch ML data:', err);
      setError('Failed to load ML training data');
    } finally {
      setLoading(false);
    }
  };

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

  if (loading) {
    return (
      <Layout>
        <PageLoader message="Loading ML training..." />
      </Layout>
    );
  }

  const labeledCount = labelStatus?.labeled_count || 0;
  const requiredLabels = 200;
  const canTrain = labeledCount >= requiredLabels;
  const progress = Math.min((labeledCount / requiredLabels) * 100, 100);

  return (
    <Layout>
      <div className="ml-page animate-fade-in">
        <header className="ml-header">
          <div>
            <h1>ML Training</h1>
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
              {currentIssue ? (
                <div className="labeling-interface">
                  <div className="labeling-issue">
                    <div className="labeling-issue-header">
                      <DifficultyBadge difficulty={currentIssue.difficulty} />
                      <span className="labeling-issue-repo">
                        {currentIssue.repo_owner}/{currentIssue.repo_name}
                      </span>
                    </div>
                    <h4 className="labeling-issue-title">{currentIssue.title}</h4>
                    <p className="labeling-issue-description">
                      {currentIssue.description?.slice(0, 300)}
                      {currentIssue.description?.length > 300 ? '...' : ''}
                    </p>
                    {currentIssue.technologies?.length > 0 && (
                      <div className="labeling-issue-techs">
                        {currentIssue.technologies.slice(0, 5).map((tech) => (
                          <Badge key={tech} variant="tech" size="sm">{tech}</Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="labeling-actions">
                    <Button 
                      variant="danger" 
                      size="lg"
                      onClick={() => handleLabel('bad')}
                      loading={labeling}
                      className="labeling-btn labeling-btn-bad"
                    >
                      nuts
                    </Button>
                    <Button 
                      variant="success" 
                      size="lg"
                      onClick={() => handleLabel('good')}
                      loading={labeling}
                      className="labeling-btn labeling-btn-good"
                    >
                      deez
                    </Button>
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
                      <span className="label-stat-label">Good</span>
                    </div>
                    <div className="label-stat">
                      <span className="label-stat-value label-stat-bad">
                        {labelStatus?.bad_count || 0}
                      </span>
                      <span className="label-stat-label">Bad</span>
                    </div>
                  </div>
                </div>
              </CardBody>
            </Card>

            {/* Training Panel */}
            <Card className="ml-training-card animate-slide-up stagger-3">
              <CardHeader>
                <h3>Train Model</h3>
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
                    <span>Model Stacking</span>
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
                  {canTrain ? 'Train Model' : `Need ${requiredLabels - labeledCount} more labels`}
                </Button>
              </CardBody>
            </Card>

            {/* Model Info */}
            {modelInfo && (
              <Card className="ml-model-card animate-slide-up stagger-4">
                <CardHeader>
                  <h3>Current Model</h3>
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

