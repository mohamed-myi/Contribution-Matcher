import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * useDebounce - Debounces a value by the specified delay.
 * 
 * @param {any} value - The value to debounce
 * @param {number} delay - Delay in milliseconds (default: 300)
 * @returns {any} The debounced value
 * 
 * @example
 * const [searchTerm, setSearchTerm] = useState('');
 * const debouncedSearch = useDebounce(searchTerm, 300);
 * 
 * useEffect(() => {
 *   // Only called after user stops typing for 300ms
 *   fetchResults(debouncedSearch);
 * }, [debouncedSearch]);
 */
export function useDebounce(value, delay = 300) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * useDebouncedCallback - Creates a debounced version of a callback function.
 * 
 * @param {Function} callback - The function to debounce
 * @param {number} delay - Delay in milliseconds (default: 300)
 * @returns {Function} The debounced callback
 * 
 * @example
 * const debouncedFilter = useDebouncedCallback((filters) => {
 *   fetchIssues(filters);
 * }, 300);
 * 
 * <input onChange={(e) => debouncedFilter({ search: e.target.value })} />
 */
export function useDebouncedCallback(callback, delay = 300) {
  const timeoutRef = useRef(null);
  const callbackRef = useRef(callback);

  // Update callback ref when it changes
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const debouncedCallback = useCallback((...args) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      callbackRef.current(...args);
    }, delay);
  }, [delay]);

  // Allow immediate invocation if needed
  debouncedCallback.flush = useCallback((...args) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    callbackRef.current(...args);
  }, []);

  // Cancel pending invocation
  debouncedCallback.cancel = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  }, []);

  return debouncedCallback;
}

export default useDebounce;

