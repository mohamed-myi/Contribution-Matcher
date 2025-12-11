/**
 * Issues Feature Module
 * 
 * Handles issue management:
 * - Issue list with filters
 * - Issue details
 * - Bookmarks
 * - Scoring display
 */

// Components
export { default as IssuesPage } from './components/IssuesPage';
export { default as IssueList } from './components/IssueList';
export { default as IssueCard } from './components/IssueCard';
export { default as IssueFilters } from './components/IssueFilters';
export { default as BookmarksPage } from './components/BookmarksPage';

// Hooks
export { useIssues } from './hooks/useIssues';
export { useBookmarks } from './hooks/useBookmarks';
export { useIssueFilters } from './hooks/useIssueFilters';

// Services
export { issueService } from './services/issueService';
