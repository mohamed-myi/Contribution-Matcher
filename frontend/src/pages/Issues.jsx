import { useState, useEffect, useCallback, useMemo, memo, startTransition } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Card, CardBody, Button, Badge, DifficultyBadge, ScoreBadge, TechBadge, PageLoader, SkeletonCard, SkeletonList } from '../components/common';
import { api } from '../api/client';
import { useCancelableRequest } from '../hooks';
import { PROGRAMMING_LANGUAGES, PAGE_SIZE } from '../constants';
import './Issues.css';

// Helper to create initial filter state from URL params
const getInitialFilters = (searchParams) => ({
  difficulty: searchParams.get('difficulty') || '',
  technology: searchParams.get('technology') || '',
  language: searchParams.get('language') || '',
  bookmarked: searchParams.get('bookmarked') === 'true',
  dateRange: searchParams.get('dateRange') || '',
  minStars: searchParams.get('minStars') || '',
  issueType: searchParams.get('issueType') || '',
  scoreRange: searchParams.get('scoreRange') || '',
});

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
  const [exporting, setExporting] = useState(false);

  // Discovery state
  const [discoverLanguage, setDiscoverLanguage] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [discoverMessage, setDiscoverMessage] = useState(null);

  // Filter state - initialized once from URL, consolidated
  const initialFilters = useMemo(() => getInitialFilters(searchParams), [searchParams]);
  const [pendingFilters, setPendingFilters] = useState(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState(initialFilters);

  // Cancelable request handling
  const { getSignal, isAbortError } = useCancelableRequest();

  // Define fetchIssues BEFORE useEffect that uses it
  const fetchIssues = useCallback(async (currentOffset = 0, reset = false) => {
    try {
      if (reset) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }
      
      const signal = getSignal();
      
      let response;
      if (appliedFilters.bookmarked) {
        response = await api.getBookmarks({ signal });
        let bookmarkedIssues = response.data.issues || [];
        bookmarkedIssues = bookmarkedIssues.map(issue => ({ ...issue, is_bookmarked: true }));
        
        // Client-side filter for bookmarks
        bookmarkedIssues = applyClientFilters(bookmarkedIssues, appliedFilters);
        
        setIssues(bookmarkedIssues);
        setTotalCount(bookmarkedIssues.length);
        setHasMore(false);
      } else {
        const params = {
          offset: currentOffset,
          limit: PAGE_SIZE,
        };
        if (appliedFilters.difficulty) params.difficulty = appliedFilters.difficulty;
        if (appliedFilters.technology) params.technology = appliedFilters.technology;
        if (appliedFilters.language) params.language = appliedFilters.language;
        if (appliedFilters.dateRange) params.days_back = getDaysFromRange(appliedFilters.dateRange);
        if (appliedFilters.issueType) params.issue_type = appliedFilters.issueType;
        if (appliedFilters.minStars) params.min_stars = parseInt(appliedFilters.minStars, 10);
        if (appliedFilters.scoreRange) params.score_range = appliedFilters.scoreRange;
        
        response = await api.getIssues({ ...params, signal });
        let newIssues = response.data.issues || [];
        const total = response.data.total || 0;
        
        // All filters are now server-side, no client filtering needed
        
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
      if (isAbortError(err)) return;
      console.error('Failed to fetch issues:', err);
      setError('Failed to load issues');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [appliedFilters, getSignal, isAbortError]);

  // Fetch issues when applied filters change
  useEffect(() => {
    setOffset(0);
    setIssues([]);
    setHasMore(true);
    fetchIssues(0, true);
  }, [fetchIssues]);

  const loadMore = useCallback(() => {
    if (!loadingMore && hasMore) {
      fetchIssues(offset, false);
    }
  }, [loadingMore, hasMore, offset, fetchIssues]);

  const handleFilterChange = useCallback((key, value) => {
    setPendingFilters(prev => ({ ...prev, [key]: value }));
  }, []);

  // Use startTransition for non-urgent filter updates (keeps UI responsive)
  const applyFilters = useCallback(() => {
    startTransition(() => {
      setAppliedFilters(pendingFilters);
    });
    
    // Update URL params (synchronous - doesn't need transition)
    const params = new URLSearchParams();
    if (pendingFilters.difficulty) params.set('difficulty', pendingFilters.difficulty);
    if (pendingFilters.technology) params.set('technology', pendingFilters.technology);
    if (pendingFilters.language) params.set('language', pendingFilters.language);
    if (pendingFilters.bookmarked) params.set('bookmarked', 'true');
    if (pendingFilters.dateRange) params.set('dateRange', pendingFilters.dateRange);
    if (pendingFilters.minStars) params.set('minStars', pendingFilters.minStars);
    if (pendingFilters.issueType) params.set('issueType', pendingFilters.issueType);
    if (pendingFilters.scoreRange) params.set('scoreRange', pendingFilters.scoreRange);
    setSearchParams(params);
  }, [pendingFilters, setSearchParams]);

  const handleDiscover = useCallback(async () => {
    try {
      setDiscovering(true);
      setDiscoverMessage(null);
      
      const params = {};
      if (discoverLanguage) params.language = discoverLanguage;
      
      const response = await api.discoverIssues(params);
      const count = response.data?.discovered || response.data?.issues?.length || 0;
      
      setDiscoverMessage({ type: 'success', text: `Discovered ${count} new issues!` });
      
      // Refresh the issues list
      fetchIssues(0, true);
    } catch (err) {
      console.error('Failed to discover issues:', err);
      setDiscoverMessage({ type: 'error', text: 'Failed to discover issues. Try again.' });
    } finally {
      setDiscovering(false);
    }
  }, [discoverLanguage, fetchIssues]);

  // Optimistic bookmark update - no external state dependencies for stable callback
  const handleBookmark = useCallback(async (issueId, isBookmarked) => {
    const newBookmarkState = !isBookmarked;
    
    // Helper to update bookmark state in an issue
    const updateIssueBookmark = (issue, bookmarked) => 
      issue.id === issueId ? { ...issue, is_bookmarked: bookmarked } : issue;
    
    // Optimistic update - batch both state changes
    setIssues(prev => prev.map(issue => updateIssueBookmark(issue, newBookmarkState)));
    setSelectedIssue(prev => prev?.id === issueId ? { ...prev, is_bookmarked: newBookmarkState } : prev);
    
    try {
      if (isBookmarked) {
        await api.removeBookmark(issueId);
      } else {
        await api.bookmarkIssue(issueId);
      }
    } catch (err) {
      console.error('Failed to update bookmark:', err);
      // Rollback on error
      setIssues(prev => prev.map(issue => updateIssueBookmark(issue, isBookmarked)));
      setSelectedIssue(prev => prev?.id === issueId ? { ...prev, is_bookmarked: isBookmarked } : prev);
    }
  }, []); // No dependencies - uses functional updates only

  const clearFilters = useCallback(() => {
    const emptyFilters = {
      difficulty: '',
      technology: '',
      language: '',
      bookmarked: false,
      dateRange: '',
      minStars: '',
      issueType: '',
      scoreRange: '',
    };
    setPendingFilters(emptyFilters);
    startTransition(() => {
      setAppliedFilters(emptyFilters);
    });
    setSearchParams({});
  }, [setSearchParams]);

  const handleExport = useCallback(async (format) => {
    try {
      setExporting(true);
      await api.exportIssues(format, appliedFilters.bookmarked);
    } catch (err) {
      console.error('Failed to export issues:', err);
      setError('Failed to export issues');
    } finally {
      setExporting(false);
    }
  }, [appliedFilters.bookmarked]);

  const hasActiveFilters = useMemo(() => {
    return !!(appliedFilters.difficulty || appliedFilters.technology || appliedFilters.language || 
      appliedFilters.bookmarked || appliedFilters.dateRange || appliedFilters.minStars || 
      appliedFilters.issueType || appliedFilters.scoreRange);
  }, [appliedFilters]);

  const hasUnappliedChanges = useMemo(() => {
    return Object.keys(pendingFilters).some(key => pendingFilters[key] !== appliedFilters[key]);
  }, [pendingFilters, appliedFilters]);

  // Don't show full page loader - we'll use skeletons instead
  // if (loading && issues.length === 0) {
  //   return (
  //     <Layout>
  //       <PageLoader message="Loading issues..." />
  //     </Layout>
  //   );
  // }

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
              {exporting ? 'Exporting...' : 'Export CSV'}
            </Button>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => handleExport('json')}
              disabled={exporting || issues.length === 0}
            >
              {exporting ? 'Exporting...' : 'Export JSON'}
            </Button>
          </div>
        </header>

        {/* Discover Tile */}
        <DiscoverTile
          language={discoverLanguage}
          onLanguageChange={setDiscoverLanguage}
          onDiscover={handleDiscover}
          discovering={discovering}
          message={discoverMessage}
        />

        {error && (
          <div className="issues-error">
            <p>{error}</p>
            <Button variant="outline" size="sm" onClick={() => fetchIssues(0, true)}>
              Retry
            </Button>
          </div>
        )}

        {/* Main Layout: Sidebar + Content */}
        <div className="issues-layout">
          {/* Filter Sidebar */}
          <FilterSidebar
            filters={pendingFilters}
            onFilterChange={handleFilterChange}
            onApplyFilters={applyFilters}
            onClearFilters={clearFilters}
            hasActiveFilters={hasActiveFilters}
            hasUnappliedChanges={hasUnappliedChanges}
          />

          {/* Issues Content */}
          <div className="issues-content">
            {!loading && issues.length > 0 && (
              <div className="issues-count">
                Showing {issues.length} of {totalCount} issues
              </div>
            )}

            {loading && issues.length === 0 ? (
              <div className="issues-grid">
                <SkeletonList count={6} type="card" />
              </div>
            ) : (
              <IssuesGrid 
                issues={issues}
                loading={loading}
                onSelect={setSelectedIssue}
                onBookmark={handleBookmark}
              />
            )}

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
          </div>
        </div>

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
 * DiscoverTile - Top section for discovering new issues (memoized)
 */
const DiscoverTile = memo(function DiscoverTile({ language, onLanguageChange, onDiscover, discovering, message }) {
  const handleLanguageChange = useCallback((e) => {
    onLanguageChange(e.target.value);
  }, [onLanguageChange]);

  return (
    <Card className="discover-tile">
      <CardBody>
        <div className="discover-content">
          <div className="discover-info">
            <h3>Discover Issues</h3>
            <p>
              Search GitHub for new open source issues matching your criteria. 
              Issues with labels like "good first issue" and "help wanted" will be 
              fetched and added to your collection for scoring and filtering.
            </p>
            {message && (
              <div className={`discover-message discover-message-${message.type}`}>
                {message.text}
              </div>
            )}
          </div>
          <div className="discover-controls">
            <div className="discover-field">
              <label>Language</label>
              <select
                value={language}
                onChange={handleLanguageChange}
                disabled={discovering}
              >
                <option value="">All Languages</option>
                {PROGRAMMING_LANGUAGES.map(lang => (
                  <option key={lang} value={lang}>{lang}</option>
                ))}
              </select>
            </div>
            <Button
              variant="primary"
              onClick={onDiscover}
              loading={discovering}
              disabled={discovering}
            >
              {discovering ? 'Discovering...' : 'Discover Issues'}
            </Button>
          </div>
        </div>
      </CardBody>
    </Card>
  );
});

/**
 * FilterSidebar - Sticky sidebar with all filter options (memoized)
 */
const FilterSidebar = memo(function FilterSidebar({ filters, onFilterChange, onApplyFilters, onClearFilters, hasActiveFilters, hasUnappliedChanges }) {
  // Memoized change handlers to prevent re-creating functions
  const handleChange = useCallback((key) => (e) => {
    onFilterChange(key, e.target.value);
  }, [onFilterChange]);

  const handleBookmarkToggle = useCallback(() => {
    onFilterChange('bookmarked', !filters.bookmarked);
  }, [onFilterChange, filters.bookmarked]);

  return (
    <aside className="issues-sidebar">
      <div className="sidebar-header">
        <h3>Filters</h3>
        {hasActiveFilters && (
          <button className="sidebar-clear" onClick={onClearFilters}>
            Clear All
          </button>
        )}
      </div>

      <div className="sidebar-filters">
        {/* Difficulty */}
        <div className="sidebar-filter-group">
          <label>Difficulty</label>
          <select
            value={filters.difficulty}
            onChange={handleChange('difficulty')}
          >
            <option value="">All Difficulties</option>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>

        {/* Technology */}
        <div className="sidebar-filter-group">
          <label>Technology</label>
          <input
            type="text"
            placeholder="e.g., React, Docker"
            value={filters.technology}
            onChange={handleChange('technology')}
          />
        </div>

        {/* Language */}
        <div className="sidebar-filter-group">
          <label>Language</label>
          <select
            value={filters.language}
            onChange={handleChange('language')}
          >
            <option value="">All Languages</option>
            {PROGRAMMING_LANGUAGES.map(lang => (
              <option key={lang} value={lang}>{lang}</option>
            ))}
          </select>
        </div>

        {/* Date Range */}
        <div className="sidebar-filter-group">
          <label>Date Range</label>
          <select
            value={filters.dateRange}
            onChange={handleChange('dateRange')}
          >
            <option value="">All Time</option>
            <option value="week">Last Week</option>
            <option value="month">Last Month</option>
            <option value="3months">Last 3 Months</option>
          </select>
        </div>

        {/* Min Stars */}
        <div className="sidebar-filter-group">
          <label>Min Stars</label>
          <input
            type="number"
            placeholder="e.g., 100"
            min="0"
            value={filters.minStars}
            onChange={handleChange('minStars')}
          />
        </div>

        {/* Issue Type */}
        <div className="sidebar-filter-group">
          <label>Issue Type</label>
          <select
            value={filters.issueType}
            onChange={handleChange('issueType')}
          >
            <option value="">All Types</option>
            <option value="bug">Bug</option>
            <option value="feature">Feature</option>
            <option value="documentation">Documentation</option>
            <option value="enhancement">Enhancement</option>
          </select>
        </div>

        {/* Score Range */}
        <div className="sidebar-filter-group">
          <label>Score Range</label>
          <select
            value={filters.scoreRange}
            onChange={handleChange('scoreRange')}
          >
            <option value="">All Scores</option>
            <option value="high">High (80+)</option>
            <option value="medium">Medium (50-79)</option>
            <option value="low">Low (&lt;50)</option>
          </select>
        </div>

        {/* Bookmarked Toggle */}
        <div className="sidebar-filter-group">
          <label>Show Only</label>
          <Button
            variant={filters.bookmarked ? 'secondary' : 'outline'}
            size="sm"
            onClick={handleBookmarkToggle}
            className="sidebar-bookmark-btn"
          >
            {filters.bookmarked ? 'Bookmarked' : 'Bookmarked'}
          </Button>
        </div>
      </div>

      {/* Apply Filters Button */}
      <div className="sidebar-apply">
        <Button
          variant="primary"
          onClick={onApplyFilters}
          className="sidebar-apply-btn"
          disabled={!hasUnappliedChanges}
        >
          Apply Filters
        </Button>
      </div>
    </aside>
  );
});

/**
 * Helper: Apply client-side filters for bookmarks only
 * All other filters are now server-side for proper pagination
 */
function applyClientFilters(issues, filters) {
  let filtered = [...issues];

  // Only apply filters that aren't supported by the bookmarks endpoint
  if (filters.difficulty) {
    filtered = filtered.filter(issue => issue.difficulty === filters.difficulty);
  }
  
  if (filters.technology) {
    filtered = filtered.filter(issue => 
      issue.technologies?.some(t => 
        t.toLowerCase().includes(filters.technology.toLowerCase())
      )
    );
  }
  
  if (filters.language) {
    filtered = filtered.filter(issue => 
      issue.repo_languages && 
      Object.keys(issue.repo_languages).some(lang => 
        lang.toLowerCase() === filters.language.toLowerCase()
      )
    );
  }

  if (filters.minStars) {
    const minStars = parseInt(filters.minStars, 10);
    if (!isNaN(minStars)) {
      filtered = filtered.filter(issue => (issue.repo_stars || 0) >= minStars);
    }
  }

  if (filters.issueType) {
    filtered = filtered.filter(issue => issue.issue_type === filters.issueType);
  }

  if (filters.scoreRange) {
    filtered = filtered.filter(issue => {
      const score = issue.score || 0;
      switch (filters.scoreRange) {
        case 'high': return score >= 80;
        case 'medium': return score >= 50 && score < 80;
        case 'low': return score < 50;
        default: return true;
      }
    });
  }

  return filtered;
}

/**
 * Helper: Convert date range to days
 */
function getDaysFromRange(range) {
  switch (range) {
    case 'week': return 7;
    case 'month': return 30;
    case '3months': return 90;
    default: return null;
  }
}

/**
 * IssuesGrid - Renders issues with optimized rendering
 */
const IssuesGrid = memo(function IssuesGrid({ issues, loading, onSelect, onBookmark }) {
  // Skip animations for large lists (performance optimization)
  const skipAnimations = issues.length > 30;

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
      {issues.map((issue) => (
        <IssueCard 
          key={issue.id} 
          issue={issue}
          onSelect={onSelect}
          onBookmark={onBookmark}
          skipAnimation={skipAnimations}
        />
      ))}
    </div>
  );
});

/**
 * IssueCard - Memoized card component to prevent unnecessary re-renders
 */
const IssueCard = memo(function IssueCard({ issue, onSelect, onBookmark, skipAnimation }) {
  const handleClick = useCallback(() => {
    onSelect(issue);
  }, [onSelect, issue]);

  const handleBookmarkClick = useCallback((e) => {
    e.stopPropagation();
    onBookmark(issue.id, issue.is_bookmarked);
  }, [onBookmark, issue.id, issue.is_bookmarked]);

  return (
    <Card 
      hover 
      className={`issue-card${skipAnimation ? '' : ' animate-slide-up'}`}
      onClick={handleClick}
    >
      <div className="issue-card-header">
        <div className="issue-card-badges">
          <DifficultyBadge difficulty={issue.difficulty} size="sm" />
          <ScoreBadge score={issue.score || 0} size="sm" />
        </div>
        <Button 
          variant={issue.is_bookmarked ? 'secondary' : 'outline'}
          size="sm"
          onClick={handleBookmarkClick}
          aria-label={issue.is_bookmarked ? 'Remove bookmark' : 'Add bookmark'}
          className="issue-bookmark-btn"
        >
          {issue.is_bookmarked ? 'Bookmarked' : 'Bookmark'}
        </Button>
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
});

function IssueDetailModal({ issue, onClose, onBookmark }) {
  const [scoreBreakdown, setScoreBreakdown] = useState(null);
  const [notes, setNotes] = useState([]);
  const [loadingNotes, setLoadingNotes] = useState(true);
  const [newNote, setNewNote] = useState('');
  const [addingNote, setAddingNote] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState(issue.label || null);
  
  const { getSignal, isAbortError } = useCancelableRequest();

  // Lock body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

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
        setLoadingNotes(false);
      }
    };
    
    fetchData();
  }, [issue.id, getSignal, isAbortError]);

  const handleAddNote = async () => {
    if (!newNote.trim()) return;
    
    // Create optimistic note with temporary ID
    const optimisticNote = {
      id: `temp-${Date.now()}`,
      content: newNote.trim(),
      created_at: new Date().toISOString(),
      isPending: true,
    };
    
    // Optimistically add note to UI
    const noteContent = newNote.trim();
    setNotes(prev => [...prev, optimisticNote]);
    setNewNote('');
    
    try {
      setAddingNote(true);
      await api.addIssueNote(issue.id, noteContent);
      
      // Refresh notes to get the actual note with real ID
      const response = await api.getIssueNotes(issue.id);
      setNotes(response.data.notes || []);
    } catch (err) {
      console.error('Failed to add note:', err);
      // Rollback on error - remove the optimistic note
      setNotes(prev => prev.filter(n => n.id !== optimisticNote.id));
      setNewNote(noteContent); // Restore the note text so user can try again
    } finally {
      setAddingNote(false);
    }
  };

  const handleDeleteNote = async (noteId) => {
    // Optimistically remove note from UI
    const deletedNote = notes.find(n => n.id === noteId);
    setNotes(notes.filter(n => n.id !== noteId));
    
    try {
      await api.deleteIssueNote(issue.id, noteId);
    } catch (err) {
      console.error('Failed to delete note:', err);
      // Rollback on error - restore the note
      if (deletedNote) {
        setNotes(prev => [...prev, deletedNote].sort((a, b) => 
          new Date(a.created_at) - new Date(b.created_at)
        ));
      }
    }
  };

  const handleLabelIssue = async (label) => {
    const previousLabel = selectedLabel;
    const newLabel = selectedLabel === label ? null : label;
    
    // Optimistically update label
    setSelectedLabel(newLabel);
    
    try {
      if (newLabel) {
        await api.labelIssue(issue.id, newLabel);
      }
    } catch (err) {
      console.error('Failed to label issue:', err);
      // Rollback on error
      setSelectedLabel(previousLabel);
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
                    <div key={note.id} className={`note-item ${note.isPending ? 'note-pending' : ''}`}>
                      <p className="note-content">
                        {note.content}
                        {note.isPending && <span className="note-pending-indicator"> (Saving...)</span>}
                      </p>
                      <div className="note-footer">
                        <span className="note-date">
                          {new Date(note.created_at).toLocaleDateString()}
                        </span>
                        {!note.isPending && (
                          <button 
                            className="note-delete"
                            onClick={() => handleDeleteNote(note.id)}
                          >
                            Delete
                          </button>
                        )}
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
