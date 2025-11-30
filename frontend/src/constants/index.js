/**
 * Shared constants for the Contribution Matcher frontend.
 * 
 * Centralized to prevent duplication across components.
 */

// Programming languages supported for filtering
export const PROGRAMMING_LANGUAGES = [
  'Python',
  'JavaScript',
  'TypeScript',
  'Java',
  'C++',
  'C#',
  'Go',
  'Rust',
  'Ruby',
  'PHP',
  'Swift',
  'Kotlin',
  'Scala',
  'C',
  'Shell',
  'HTML',
  'CSS',
  'Dart',
  'R',
  'Lua',
  'Perl',
  'Haskell',
  'Elixir',
  'Clojure',
];

// Difficulty levels
export const DIFFICULTY_LEVELS = [
  { value: 'beginner', label: 'Beginner', color: 'var(--color-success)' },
  { value: 'intermediate', label: 'Intermediate', color: 'var(--color-warning)' },
  { value: 'advanced', label: 'Advanced', color: 'var(--color-danger)' },
];

// Experience levels for profiles
export const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'Beginner', description: '< 1 year' },
  { value: 'intermediate', label: 'Intermediate', description: '1-3 years' },
  { value: 'advanced', label: 'Advanced', description: '3+ years' },
];

// Issue types
export const ISSUE_TYPES = [
  { value: 'bug', label: 'Bug Fix' },
  { value: 'feature', label: 'Feature' },
  { value: 'docs', label: 'Documentation' },
  { value: 'test', label: 'Testing' },
  { value: 'refactor', label: 'Refactoring' },
];

// Pagination
export const PAGE_SIZE = 20;
export const INITIAL_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

// Debounce delays (ms)
export const DEBOUNCE = {
  SEARCH: 300,
  FILTER: 300,
  RESIZE: 150,
  SCROLL: 100,
};

// API timeouts (ms)
export const TIMEOUT = {
  DEFAULT: 30000,
  DISCOVERY: 120000,
  EXPORT: 60000,
};

// Local storage keys
export const STORAGE_KEYS = {
  AUTH_TOKEN: 'auth_token',
  THEME: 'theme',
  FILTERS: 'issue_filters',
  LAST_VIEW: 'last_view',
};

// Score thresholds
export const SCORE_THRESHOLDS = {
  HIGH: 75,
  MEDIUM: 50,
  LOW: 25,
};

// Score colors
export const getScoreColor = (score) => {
  if (score >= SCORE_THRESHOLDS.HIGH) return 'var(--color-success)';
  if (score >= SCORE_THRESHOLDS.MEDIUM) return 'var(--color-warning)';
  return 'var(--color-danger)';
};

// Export formats
export const EXPORT_FORMATS = [
  { value: 'csv', label: 'CSV', extension: '.csv' },
  { value: 'json', label: 'JSON', extension: '.json' },
];

// Virtualization thresholds
export const VIRTUALIZATION = {
  ITEM_HEIGHT: 200, // Approximate height of an issue card
  OVERSCAN: 5,       // Extra items to render for smooth scrolling
  MIN_ITEMS_FOR_VIRTUAL: 50, // Only virtualize if more than this many items
};

