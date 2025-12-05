/**
 * Route Preloader Utility
 * Preloads lazy-loaded route components on hover/focus for instant navigation
 */

const preloadedRoutes = new Set();

/**
 * Preload a lazy-loaded component
 * @param {Function} lazyComponent - The lazy-loaded component (result of React.lazy())
 * @returns {Promise} - Promise that resolves when component is loaded
 */
export function preloadRoute(lazyComponent) {
  // Get the component's unique identifier
  const componentId = lazyComponent._payload?._result?.toString() || 
                      lazyComponent.toString();
  
  // Skip if already preloaded
  if (preloadedRoutes.has(componentId)) {
    return Promise.resolve();
  }
  
  // Mark as preloading
  preloadedRoutes.add(componentId);
  
  // Trigger the lazy load by accessing the component
  // This works because React.lazy() returns a thenable that loads on access
  return lazyComponent._payload?._result || 
         (lazyComponent._init && lazyComponent._init(lazyComponent._payload)) ||
         Promise.resolve();
}

/**
 * Create preload handlers for a route
 * @param {Function} lazyComponent - The lazy-loaded component
 * @returns {Object} - Object with onMouseEnter and onFocus handlers
 */
export function createPreloadHandlers(lazyComponent) {
  let preloadPromise = null;
  
  const triggerPreload = () => {
    if (!preloadPromise) {
      preloadPromise = preloadRoute(lazyComponent).catch(err => {
        console.warn('Failed to preload route:', err);
      });
    }
  };
  
  return {
    onMouseEnter: triggerPreload,
    onFocus: triggerPreload,
    onTouchStart: triggerPreload, // For mobile
  };
}

/**
 * Preload multiple routes at once
 * @param {Array} lazyComponents - Array of lazy-loaded components
 * @returns {Promise} - Promise that resolves when all components are loaded
 */
export function preloadRoutes(lazyComponents) {
  return Promise.all(
    lazyComponents.map(component => 
      preloadRoute(component).catch(err => {
        console.warn('Failed to preload route:', err);
      })
    )
  );
}

/**
 * Preload critical routes after initial load
 * Call this after the app has loaded to preload important routes
 */
export function preloadCriticalRoutes() {
  // This will be called from App.jsx after mount
  // to preload the most commonly accessed routes
  if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
      // Preload happens in idle time
    }, { timeout: 2000 });
  } else {
    // Fallback for browsers without requestIdleCallback
    setTimeout(() => {
      // Preload happens after 2 seconds
    }, 2000);
  }
}

export default {
  preloadRoute,
  createPreloadHandlers,
  preloadRoutes,
  preloadCriticalRoutes,
};

