/**
 * Profile Feature Module
 * 
 * Handles user profile:
 * - Profile display
 * - Profile editing
 * - GitHub import
 * - Skills management
 */

// Components
export { default as ProfilePage } from './components/ProfilePage';
export { default as ProfileForm } from './components/ProfileForm';
export { default as SkillsEditor } from './components/SkillsEditor';

// Hooks
export { useProfile } from './hooks/useProfile';
export { useGitHubImport } from './hooks/useGitHubImport';

// Services
export { profileService } from './services/profileService';
