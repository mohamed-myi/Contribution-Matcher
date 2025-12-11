import { useRef, useEffect, useCallback, useState } from 'react';

/**
 * useCancelableRequest - Provides AbortController management for fetch requests.
 * 
 * Automatically cancels in-flight requests when:
 * - Component unmounts
 * - A new request is made before the previous completes
 * 
 * @returns {Object} { getSignal, cancel, cancelAll }
 * 
 * @example
 * const { getSignal, cancel } = useCancelableRequest();
 * 
 * const fetchData = async () => {
 *   try {
 *     const response = await fetch('/api/data', { signal: getSignal() });
 *     const data = await response.json();
 *   } catch (err) {
 *     if (err.name === 'AbortError') {
 *       console.log('Request cancelled');
 *       return;
 *     }
 *     throw err;
 *   }
 * };
 * 
 * // To cancel:
 * cancel();
 */
export function useCancelableRequest() {
  const controllerRef = useRef(null);
  const controllersRef = useRef(new Map());
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Cancel all pending requests
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
      controllersRef.current.forEach((controller) => {
        controller.abort();
      });
      controllersRef.current.clear();
    };
  }, []);

  /**
   * Get a new AbortSignal, canceling any previous request.
   * Use for single-request-at-a-time patterns.
   */
  const getSignal = useCallback(() => {
    // Cancel previous request
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    
    // Create new controller
    controllerRef.current = new AbortController();
    return controllerRef.current.signal;
  }, []);

  /**
   * Get a named AbortSignal for parallel request management.
   */
  const getNamedSignal = useCallback((name) => {
    // Cancel previous request with same name
    const existing = controllersRef.current.get(name);
    if (existing) {
      existing.abort();
    }
    
    // Create new controller
    const controller = new AbortController();
    controllersRef.current.set(name, controller);
    return controller.signal;
  }, []);

  /**
   * Cancel the current request.
   */
  const cancel = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
  }, []);

  /**
   * Cancel a named request.
   */
  const cancelNamed = useCallback((name) => {
    const controller = controllersRef.current.get(name);
    if (controller) {
      controller.abort();
      controllersRef.current.delete(name);
    }
  }, []);

  /**
   * Cancel all requests.
   */
  const cancelAll = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    controllersRef.current.forEach((controller) => {
      controller.abort();
    });
    controllersRef.current.clear();
  }, []);

  /**
   * Check if error is an abort error.
   */
  const isAbortError = useCallback((error) => {
    return error?.name === 'AbortError';
  }, []);

  return {
    getSignal,
    getNamedSignal,
    cancel,
    cancelNamed,
    cancelAll,
    isAbortError,
  };
}

/**
 * useFetch - A wrapper around useCancelableRequest for simpler data fetching.
 * 
 * @param {Function} fetchFn - Async function that receives { signal } and returns data
 * @param {Array} deps - Dependencies array (like useEffect)
 * @returns {Object} { data, loading, error, refetch }
 * 
 * @example
 * const { data, loading, error, refetch } = useFetch(
 *   ({ signal }) => api.getIssues({ signal }),
 *   []
 * );
 */
export function useFetch(fetchFn, deps = []) {
  const [state, setState] = useState({
    data: null,
    loading: true,
    error: null,
  });
  
  const { getSignal, isAbortError } = useCancelableRequest();

  const execute = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    
    try {
      const signal = getSignal();
      const data = await fetchFn({ signal });
      setState({ data, loading: false, error: null });
    } catch (err) {
      if (isAbortError(err)) {
        // Request was cancelled, ignore - don't set error state
        setState((s) => ({ ...s, loading: false, error: null }));
        return;
      }
      setState((s) => ({ ...s, loading: false, error: err }));
    }
  }, [fetchFn, getSignal, isAbortError]);

  useEffect(() => {
    execute();
  }, deps);

  return {
    ...state,
    refetch: execute,
  };
}

export default useCancelableRequest;

