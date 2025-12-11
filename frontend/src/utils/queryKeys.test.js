import { describe, it, expect } from 'vitest';
import { queryKeys } from './queryKeys';

describe('queryKeys', () => {
  describe('auth', () => {
    it('generates auth all key', () => {
      expect(queryKeys.auth.all).toEqual(['auth']);
    });

    it('generates auth me key', () => {
      expect(queryKeys.auth.me()).toEqual(['auth', 'me']);
    });
  });

  describe('issues', () => {
    it('generates all issues key', () => {
      expect(queryKeys.issues.all).toEqual(['issues']);
    });

    it('generates list key with filters', () => {
      const filters = { difficulty: 'beginner', language: 'python' };
      expect(queryKeys.issues.list(filters)).toEqual(['issues', 'list', filters]);
    });

    it('generates detail key with id', () => {
      expect(queryKeys.issues.detail(123)).toEqual(['issues', 'detail', 123]);
    });

    it('generates stats key', () => {
      expect(queryKeys.issues.stats()).toEqual(['issues', 'stats']);
    });

    it('generates topMatches key', () => {
      expect(queryKeys.issues.topMatches(5)).toEqual(['issues', 'topMatches', 5]);
    });
  });

  describe('profile', () => {
    it('generates profile all key', () => {
      expect(queryKeys.profile.all).toEqual(['profile']);
    });

    it('generates profile detail key', () => {
      expect(queryKeys.profile.detail()).toEqual(['profile', 'detail']);
    });

    it('generates github profile key', () => {
      expect(queryKeys.profile.github('testuser')).toEqual(['profile', 'github', 'testuser']);
    });
  });

  describe('bookmarks', () => {
    it('generates bookmarks all key', () => {
      expect(queryKeys.bookmarks.all).toEqual(['bookmarks']);
    });

    it('generates bookmarks list key', () => {
      expect(queryKeys.bookmarks.list()).toEqual(['bookmarks', 'list']);
    });
  });

  describe('ml', () => {
    it('generates ml all key', () => {
      expect(queryKeys.ml.all).toEqual(['ml']);
    });

    it('generates label status key', () => {
      expect(queryKeys.ml.labelStatus()).toEqual(['ml', 'labelStatus']);
    });

    it('generates model info key', () => {
      expect(queryKeys.ml.modelInfo()).toEqual(['ml', 'modelInfo']);
    });
  });
});
