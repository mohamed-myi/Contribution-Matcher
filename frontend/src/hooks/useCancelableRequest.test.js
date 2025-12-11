import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useCancelableRequest, useFetch } from './useCancelableRequest';

describe('useCancelableRequest', () => {
  it('returns getSignal function', () => {
    const { result } = renderHook(() => useCancelableRequest());
    expect(result.current.getSignal).toBeDefined();
    expect(typeof result.current.getSignal).toBe('function');
  });

  it('returns cancel function', () => {
    const { result } = renderHook(() => useCancelableRequest());
    expect(result.current.cancel).toBeDefined();
    expect(typeof result.current.cancel).toBe('function');
  });

  it('returns cancelAll function', () => {
    const { result } = renderHook(() => useCancelableRequest());
    expect(result.current.cancelAll).toBeDefined();
    expect(typeof result.current.cancelAll).toBe('function');
  });

  it('getSignal returns AbortSignal', () => {
    const { result } = renderHook(() => useCancelableRequest());
    const signal = result.current.getSignal();
    expect(signal).toBeInstanceOf(AbortSignal);
  });

  it('cancels previous signal when getSignal is called again', () => {
    const { result } = renderHook(() => useCancelableRequest());
    const signal1 = result.current.getSignal();
    expect(signal1.aborted).toBe(false);

    const signal2 = result.current.getSignal();
    expect(signal1.aborted).toBe(true);
    expect(signal2.aborted).toBe(false);
  });

  it('cancel aborts current signal', () => {
    const { result } = renderHook(() => useCancelableRequest());
    const signal = result.current.getSignal();
    expect(signal.aborted).toBe(false);

    result.current.cancel();
    expect(signal.aborted).toBe(true);
  });

  it('cancelAll aborts all signals', () => {
    const { result } = renderHook(() => useCancelableRequest());
    const signal1 = result.current.getSignal();
    const signal2 = result.current.getNamedSignal('test');
    
    expect(signal1.aborted).toBe(false);
    expect(signal2.aborted).toBe(false);

    result.current.cancelAll();
    expect(signal1.aborted).toBe(true);
    expect(signal2.aborted).toBe(true);
  });

  it('getNamedSignal creates named signals', () => {
    const { result } = renderHook(() => useCancelableRequest());
    const signal1 = result.current.getNamedSignal('request1');
    const signal2 = result.current.getNamedSignal('request2');
    
    expect(signal1.aborted).toBe(false);
    expect(signal2.aborted).toBe(false);
  });

  it('getNamedSignal cancels previous signal with same name', () => {
    const { result } = renderHook(() => useCancelableRequest());
    const signal1 = result.current.getNamedSignal('request1');
    const signal2 = result.current.getNamedSignal('request1');
    
    expect(signal1.aborted).toBe(true);
    expect(signal2.aborted).toBe(false);
  });

  it('cancelNamed cancels specific named signal', () => {
    const { result } = renderHook(() => useCancelableRequest());
    const signal1 = result.current.getNamedSignal('request1');
    const signal2 = result.current.getNamedSignal('request2');
    
    result.current.cancelNamed('request1');
    expect(signal1.aborted).toBe(true);
    expect(signal2.aborted).toBe(false);
  });

  it('isAbortError identifies abort errors', () => {
    const { result } = renderHook(() => useCancelableRequest());
    const abortError = new Error('Aborted');
    abortError.name = 'AbortError';
    
    expect(result.current.isAbortError(abortError)).toBe(true);
    expect(result.current.isAbortError(new Error('Other'))).toBe(false);
  });
});

describe('useFetch', () => {
  it('returns initial loading state', async () => {
    const fetchFn = vi.fn().mockResolvedValue('data');
    const { result } = renderHook(() => useFetch(fetchFn, []));
    
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(null);
    
    // Wait for effect to complete
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it('fetches data on mount', async () => {
    const fetchFn = vi.fn().mockResolvedValue('test-data');
    const { result } = renderHook(() => useFetch(fetchFn, []));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.data).toBe('test-data');
    expect(fetchFn).toHaveBeenCalled();
  });

  it('handles fetch errors', async () => {
    const fetchError = new Error('Fetch failed');
    const fetchFn = vi.fn().mockRejectedValue(fetchError);
    const { result } = renderHook(() => useFetch(fetchFn, []));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.error).toBe(fetchError);
    expect(result.current.data).toBe(null);
  });

  it('ignores abort errors', async () => {
    const abortError = new Error('Aborted');
    abortError.name = 'AbortError';
    const fetchFn = vi.fn().mockRejectedValue(abortError);
    const { result } = renderHook(() => useFetch(fetchFn, []));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    // Abort errors should not set error state
    expect(result.current.error).toBe(null);
  });

  it('refetch allows manual refetch', async () => {
    const fetchFn = vi.fn().mockResolvedValue('data');
    const { result } = renderHook(() => useFetch(fetchFn, []));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(fetchFn).toHaveBeenCalledTimes(1);
    
    result.current.refetch();
    await waitFor(() => {
      expect(fetchFn).toHaveBeenCalledTimes(2);
    });
  });
});
