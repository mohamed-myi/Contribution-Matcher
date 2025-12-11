import '@testing-library/jest-dom';
import { beforeAll, afterEach, afterAll, vi } from 'vitest';
import { server } from './mocks/server';

// Setup MSW server
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));

// Reset handlers after each test
afterEach(() => server.resetHandlers());

// Clean up after all tests
afterAll(() => server.close());

// Mock window.matchMedia (used by some UI libraries)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock window.requestIdleCallback (used in App.jsx)
if (!window.requestIdleCallback) {
  window.requestIdleCallback = vi.fn((callback, options) => {
    const timeout = options?.timeout || 0;
    return setTimeout(() => {
      callback({
        didTimeout: false,
        timeRemaining: () => 5,
      });
    }, timeout);
  });
  
  window.cancelIdleCallback = vi.fn((id) => {
    clearTimeout(id);
  });
}

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
global.localStorage = localStorageMock;

// Mock document.cookie
Object.defineProperty(document, 'cookie', {
  writable: true,
  value: '',
});
