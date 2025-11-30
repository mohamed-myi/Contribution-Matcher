import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Card, CardBody, Button, Badge, DifficultyBadge, ScoreBadge, TechBadge, PageLoader } from '../components/common';
import { api } from '../api/client';
import { useDebounce, useDebouncedCallback, useCancelableRequest } from '../hooks';
import { PROGRAMMING_LANGUAGES, PAGE_SIZE, DEBOUNCE, VIRTUALIZATION } from '../constants';
import './Issues.css';

export function Issues() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [filters, setFilters] = useState({
    difficulty: searchParams.get('difficulty') || '',
    technology: searchParams.get('technology') || '',
    language: searchParams.get('language') || '',
    bookmarked: searchParams.get('bookmarked') === 'true',
  });
  const [exporting, setExporting] = useState(false);

  // Cancelable request handling
  const { getSignal, isAbortError } = useCancelableRequest();

  // Debounce the technology filter input
  const debouncedTechnology = useDebounce(filters.technology, DEBOUNCE.FILTER);

  // Memoized filters for API call (uses debounced technology)
  const apiFilters = useMemo(() => ({
    ...filters,
    technology: debouncedTechnology,
  }), [filters.difficulty, filters.language, filters.bookmarked, debouncedTechnology]);

  // Fetch issues when debounced filters change
  useEffect(() => {
    setOffset(0);
    setIssues([]);
    setHasMore(true);
    fetchIssues(0, true);
  }, [apiFilters]);

  const fetchIssues = useCallback(async (currentOffset = 0, reset = false) => {
    try {
      if (reset) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }
      
      // Get abort signal for this request
      const signal = getSignal();
      
      let response;
      if (apiFilters.bookmarked) {
        response = await api.getBookmarks({ signal });
        let bookmarkedIssues = response.data.issues || [];
        bookmarkedIssues = bookmarkedIssues.map(issue => ({ ...issue, is_bookmarked: true }));
        
        // Client-side filter for bookmarks
        if (apiFilters.difficulty) {
          bookmarkedIssues = bookmarkedIssues.filter(
            issue => issue.difficulty === apiFilters.difficulty
          );
        }
        if (apiFilters.technology) {
          bookmarkedIssues = bookmarkedIssues.filter(
            issue => issue.technologies?.some(t => 
              t.toLowerCase().includes(apiFilters.technology.toLowerCase())
            )
          );
        }
        if (apiFilters.language) {
          bookmarkedIssues = bookmarkedIssues.filter(
            issue => issue.repo_languages && 
              Object.keys(issue.repo_languages).some(lang => 
                lang.toLowerCase() === apiFilters.language.toLowerCase()
              )
          );
        }
        setIssues(bookmarkedIssues);
        setTotalCount(bookmarkedIssues.length);
        setHasMore(false);
      } else {
        const params = {
          offset: currentOffset,
          limit: PAGE_SIZE,
        };
        if (apiFilters.difficulty) params.difficulty = apiFilters.difficulty;
        if (apiFilters.technology) params.technology = apiFilters.technology;
        if (apiFilters.language) params.language = apiFilters.language;
        
        response = await api.getIssues({ ...params, signal });
        const newIssues = response.data.issues || [];
        const total = response.data.total || 0;
        
        if (reset) {
          setIssues(newIssues);
        } else {
          setIssues(prev => [...prev, ...newIssues]);
        }
        
        setTotalCount(total);
        setHasMore(currentOffset + newIssues.length < total);
        setOffset(currentOffset + newIssues.length);
      }
      setError(null);
    } catch (err) {
      // Ignore abort errors
      if (isAbortError(err)) {
        return;
      }
      console.error('Failed to fetch issues:', err);
      setError('Failed to load issues');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [apiFilters, getSignal, isAbortError]);

  const loadMore = useCallback(() => {
    if (!loadingMore && hasMore) {
      fetchIssues(offset, false);
    }
  }, [loadingMore, hasMore, offset, fetchIssues]);

  // Debounced URL update
  const updateUrlParams = useDebouncedCallback((newFilters) => {
    const params = new URLSearchParams();
    if (newFilters.difficulty) params.set('difficulty', newFilters.difficulty);
    if (newFilters.technology) params.set('technology', newFilters.technology);
    if (newFilters.language) params.set('language', newFilters.language);
    if (newFilters.bookmarked) params.set('bookmarked', 'true');
    setSearchParams(params);
  }, DEBOUNCE.FILTER);

  const handleFilterChange = useCallback((key, value) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    updateUrlParams(newFilters);
  }, [filters, updateUrlParams]);

  const handleBookmark = useCallback(async (issueId, isBookmarked) => {
    const newBookmarkState = !isBookmarked;
    
    // Optimistic update
    setIssues(prev => prev.map(issue => 
      issue.id === issueId 
        ? { ...issue, is_bookmarked: newBookmarkState }
        : issue
    ));
    
    if (selectedIssue?.id === issueId) {
      setSelectedIssue(prev => ({ ...prev, is_bookmarked: newBookmarkState }));
    }
    
    try {
      if (isBookmarked) {
        await api.removeBookmark(issueId);
      } else {
        await api.bookmarkIssue(issueId);
      }
    } catch (err) {
      console.error('Failed to update bookmark:', err);
      // Revert on error
      setIssues(prev => prev.map(issue => 
        issue.id === issueId 
          ? { ...issue, is_bookmarked: isBookmarked }
          : issue
      ));
      if (selectedIssue?.id === issueId) {
        setSelectedIssue(prev => ({ ...prev, is_bookmarked: isBookmarked }));
      }
    }
  }, [selectedIssue]);

  const clearFilters = useCallback(() => {
    setFilters({ difficulty: '', technology: '', language: '', bookmarked: false });
    setSearchParams({});
  }, [setSearchParams]);

  const handleExport = useCallback(async (format) => {
    try {
      setExporting(true);
      await api.exportIssues(format, filters.bookmarked);
    } catch (err) {
      console.error('Failed to export issues:', err);
      setError('Failed to export issues');
    } finally {
      setExporting(false);
    }
  }, [filters.bookmarked]);

  const hasActiveFilters = filters.difficulty || filters.technology || filters.language || filters.bookmarked;

  if (loading && issues.length === 0) {
    return (
      <Layout>
        <PageLoader message="Loading issues..." />
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="issues-page animate-fade-in">
        <header className="issues-header">
          <div>
            <h1>Issues</h1>
            <p>Browse and filter open source issues</p>
          </div>
          <div className="issues-header-actions">
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => handleExport('csv')}
              disabled={exporting || issues.length === 0}
            >
              Export CSV
            </Button>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => handleExport('json')}
              disabled={exporting || issues.length === 0}
            >
              Export JSON
            </Button>
          </div>
        </header>

        {/* Filters */}
        <Card className="issues-filters">
          <CardBody>
            <div className="filters-row">
              <div className="filter-group">
                <label>Difficulty</label>
                <select 
                  value={filters.difficulty}
                  onChange={(e) => handleFilterChange('difficulty', e.target.value)}
                >
                  <option value="">All Difficulties</option>
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>

              <div className="filter-group">
                <label>Technology</label>
                <input 
                  type="text"
                  placeholder="e.g., React, Docker"
                  value={filters.technology}
                  onChange={(e) => handleFilterChange('technology', e.target.value)}
                />
              </div>

              <div className="filter-group">
                <label>Language</label>
                <select 
                  value={filters.language}
                  onChange={(e) => handleFilterChange('language', e.target.value)}
                >
                  <option value="">All Languages</option>
                  {PROGRAMMING_LANGUAGES.map(lang => (
                    <option key={lang} value={lang}>{lang}</option>
                  ))}
                </select>
              </div>

              <div className="filter-group filter-checkbox">
                <label>
                  <input 
                    type="checkbox"
                    checked={filters.bookmarked}
                    onChange={(e) => handleFilterChange('bookmarked', e.target.checked)}
                  />
                  <span>Bookmarked Only</span>
                </label>
              </div>

              {hasActiveFilters && (
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  Clear Filters
                </Button>
              )}
            </div>
          </CardBody>
        </Card>

        {error && (
          <div className="issues-error">
            <p>{error}</p>
            <Button variant="outline" size="sm" onClick={() => fetchIssues(0, true)}>
              Retry
            </Button>
          </div>
        )}

        {/* Issues Count */}
        {!loading && issues.length > 0 && (
          <div className="issues-count">
            Showing {issues.length} of {totalCount} issues
          </div>
        )}

        {/* Issues Grid - Uses CSS Grid for responsive layout */}
        <IssuesGrid 
          issues={issues}
          loading={loading}
          onSelect={setSelectedIssue}
          onBookmark={handleBookmark}
        />

        {/* Load More Button */}
        {hasMore && !loading && issues.length > 0 && (
          <div className="issues-load-more">
            <Button 
              variant="outline" 
              onClick={loadMore}
              loading={loadingMore}
              disabled={loadingMore}
            >
              {loadingMore ? 'Loading...' : 'Load More Issues'}
            </Button>
          </div>
        )}

        {/* Issue Detail Modal */}
        {selectedIssue && (
          <IssueDetailModal 
            issue={selectedIssue}
            onClose={() => setSelectedIssue(null)}
            onBookmark={() => handleBookmark(selectedIssue.id, selectedIssue.is_bookmarked)}
          />
        )}
      </div>
    </Layout>
  );
}

/**
 * IssuesGrid - Renders the issues with optimized rendering
 */
function IssuesGrid({ issues, loading, onSelect, onBookmark }) {
  if (issues.length === 0 && !loading) {
    return (
      <div className="issues-empty">
        <p>No issues found</p>
        <p>Try adjusting your filters or discover new issues</p>
      </div>
    );
  }

  return (
    <div className="issues-grid">
      {issues.map((issue, index) => (
        <IssueCard 
          key={issue.id} 
          issue={issue}
          onSelect={() => onSelect(issue)}
          onBookmark={() => onBookmark(issue.id, issue.is_bookmarked)}
          delay={index % 5}
        />
      ))}
    </div>
  );
}

function IssueCard({ issue, onSelect, onBookmark, delay }) {
  return (
    <Card 
      hover 
      className={`issue-card animate-slide-up stagger-${delay + 1}`}
      onClick={onSelect}
    >
      <div className="issue-card-header">
        <div className="issue-card-badges">
          <DifficultyBadge difficulty={issue.difficulty} size="sm" />
          <ScoreBadge score={issue.score || 0} size="sm" />
        </div>
        <button 
          className={`issue-bookmark-btn ${issue.is_bookmarked ? 'bookmarked' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            onBookmark();
          }}
          aria-label={issue.is_bookmarked ? 'Remove bookmark' : 'Add bookmark'}
        >
          {issue.is_bookmarked ? '[*]' : '[ ]'}
        </button>
      </div>

      <h3 className="issue-card-title">{issue.title}</h3>
      
      <div className="issue-card-repo">
        <span>{issue.repo_owner}/{issue.repo_name}</span>
        {issue.repo_stars && (
          <span className="issue-card-stars">{issue.repo_stars.toLocaleString()} stars</span>
        )}
      </div>

      {issue.description && (
        <p className="issue-card-description">
          {issue.description.slice(0, 150)}
          {issue.description.length > 150 ? '...' : ''}
        </p>
      )}

      {issue.technologies && issue.technologies.length > 0 && (
        <div className="issue-card-techs">
          {issue.technologies.slice(0, 4).map((tech) => (
            <TechBadge key={tech} tech={tech} />
          ))}
          {issue.technologies.length > 4 && (
            <Badge variant="default" size="sm">+{issue.technologies.length - 4}</Badge>
          )}
        </div>
      )}
    </Card>
  );
}

function IssueDetailModal({ issue, onClose, onBookmark }) {
  const [scoreBreakdown, setScoreBreakdown] = useState(null);
  const [loadingScore, setLoadingScore] = useState(true);
  const [notes, setNotes] = useState([]);
  const [loadingNotes, setLoadingNotes] = useState(true);
  const [newNote, setNewNote] = useState('');
  const [addingNote, setAddingNote] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState(issue.label || null);
  
  const { getSignal, isAbortError } = useCancelableRequest();

  useEffect(() => {
    const signal = getSignal();
    
    const fetchData = async () => {
      try {
        const [scoreRes, notesRes] = await Promise.all([
          api.getIssueScore(issue.id, { signal }).catch(() => null),
          api.getIssueNotes(issue.id, { signal }).catch(() => ({ data: { notes: [] } })),
        ]);
        
        if (scoreRes) setScoreBreakdown(scoreRes.data);
        setNotes(notesRes.data.notes || []);
      } catch (err) {
        if (!isAbortError(err)) {
          console.error('Failed to fetch issue details:', err);
        }
      } finally {
        setLoadingScore(false);
        setLoadingNotes(false);
      }
    };
    
    fetchData();
  }, [issue.id, getSignal, isAbortError]);

  const handleAddNote = async () => {
    if (!newNote.trim()) return;
    
    try {
      setAddingNote(true);
      await api.addIssueNote(issue.id, newNote);
      setNewNote('');
      
      // Refetch notes
      const response = await api.getIssueNotes(issue.id);
      setNotes(response.data.notes || []);
    } catch (err) {
      console.error('Failed to add note:', err);
    } finally {
      setAddingNote(false);
    }
  };

  const handleDeleteNote = async (noteId) => {
    try {
      await api.deleteIssueNote(issue.id, noteId);
      setNotes(notes.filter(n => n.id !== noteId));
    } catch (err) {
      console.error('Failed to delete note:', err);
    }
  };

  const handleLabelIssue = async (label) => {
    // Toggle: if same label clicked again, unselect it
    const newLabel = selectedLabel === label ? null : label;
    setSelectedLabel(newLabel);
    
    try {
      if (newLabel) {
        await api.labelIssue(issue.id, newLabel);
      }
      // If unselecting, we could call an unlabel API if it exists
    } catch (err) {
      console.error('Failed to label issue:', err);
      // Revert on error
      setSelectedLabel(selectedLabel);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content animate-slide-up" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>×</button>
        
        <div className="issue-detail">
          <div className="issue-detail-header">
            <div className="issue-detail-badges">
              <DifficultyBadge difficulty={issue.difficulty} />
              <ScoreBadge score={issue.score || 0} />
            </div>
            <h2>{issue.title}</h2>
            <div className="issue-detail-repo">
              <a 
                href={issue.url || `https://github.com/${issue.repo_owner}/${issue.repo_name}/issues/${issue.issue_number}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {issue.repo_owner}/{issue.repo_name} #{issue.issue_number}
              </a>
              {issue.repo_stars && (
                <span>{issue.repo_stars.toLocaleString()} stars</span>
              )}
            </div>
          </div>

          <div className="issue-detail-body">
            <section>
              <h4>Description</h4>
              <p>{issue.description || 'No description available'}</p>
            </section>

            {issue.technologies && issue.technologies.length > 0 && (
              <section>
                <h4>Technologies</h4>
                <div className="issue-detail-techs">
                  {issue.technologies.map((tech) => (
                    <TechBadge key={tech} tech={tech} />
                  ))}
                </div>
              </section>
            )}

            {scoreBreakdown && (
              <section>
                <h4>Score Breakdown</h4>
                <div className="score-breakdown">
                  {Object.entries(scoreBreakdown.breakdown || {}).map(([key, value]) => (
                    <div key={key} className="score-item">
                      <span className="score-item-label">{formatScoreLabel(key)}</span>
                      <div className="score-item-bar">
                        <div 
                          className="score-item-fill"
                          style={{ width: `${value}%` }}
                        />
                      </div>
                      <span className="score-item-value">{Math.round(value)}%</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Notes Section */}
            <section className="notes-section">
              <h4>Notes</h4>
              <div className="notes-add">
                <textarea
                  placeholder="Add a note about this issue..."
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  rows={2}
                />
                <Button 
                  variant="primary" 
                  size="sm"
                  onClick={handleAddNote}
                  disabled={!newNote.trim() || addingNote}
                >
                  {addingNote ? 'Adding...' : 'Add Note'}
                </Button>
              </div>
              
              {loadingNotes ? (
                <p className="notes-loading">Loading notes...</p>
              ) : notes.length === 0 ? (
                <p className="notes-empty">No notes yet</p>
              ) : (
                <div className="notes-list">
                  {notes.map((note) => (
                    <div key={note.id} className="note-item">
                      <p className="note-content">{note.content}</p>
                      <div className="note-footer">
                        <span className="note-date">
                          {new Date(note.created_at).toLocaleDateString()}
                        </span>
                        <button 
                          className="note-delete"
                          onClick={() => handleDeleteNote(note.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="issue-detail-actions">
            <div className="action-buttons-row">
              <Button 
                variant={issue.is_bookmarked ? 'secondary' : 'outline'}
                onClick={onBookmark}
                className="action-btn-equal"
              >
                {issue.is_bookmarked ? 'Bookmarked' : 'Bookmark'}
              </Button>
              <Button 
                variant="primary"
                onClick={() => window.open(issue.url || `https://github.com/${issue.repo_owner}/${issue.repo_name}/issues/${issue.issue_number}`, '_blank')}
                className="action-btn-equal"
              >
                Open in GitHub
              </Button>
            </div>
            
            <div className="preference-buttons">
              <Button 
                variant="outline"
                onClick={() => handleLabelIssue('bad')}
                className={`label-btn ${selectedLabel === 'bad' ? 'label-btn-active' : ''}`}
              >
                Dislike
              </Button>
              <Button 
                variant="outline"
                onClick={() => handleLabelIssue('good')}
                className={`label-btn ${selectedLabel === 'good' ? 'label-btn-active' : ''}`}
              >
                Like
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatScoreLabel(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

export default Issues;
