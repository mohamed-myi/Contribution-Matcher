import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useDebounce, useDebouncedCallback } from './useDebounce';

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('initial', 300));
    expect(result.current).toBe('initial');
  });

  it('debounces value changes', async () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'test' } }
    );

    expect(result.current).toBe('test');

    act(() => {
      rerender({ value: 'updated' });
    });
    expect(result.current).toBe('test'); // Still old value

    act(() => {
      vi.advanceTimersByTime(300);
    });
    await waitFor(() => {
      expect(result.current).toBe('updated');
    });
  });

  it('cancels previous timeout on rapid changes', async () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'first' } }
    );

    act(() => {
      rerender({ value: 'second' });
      vi.advanceTimersByTime(100);
      rerender({ value: 'third' });
      vi.advanceTimersByTime(100);
      rerender({ value: 'fourth' });
      vi.advanceTimersByTime(300);
    });
    
    await waitFor(() => {
      expect(result.current).toBe('fourth');
    });
  });

  it('respects custom delay', async () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: 'test' } }
    );

    act(() => {
      rerender({ value: 'updated' });
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe('test'); // Still old value

    act(() => {
      vi.advanceTimersByTime(200);
    });
    await waitFor(() => {
      expect(result.current).toBe('updated');
    });
  });
});

describe('useDebouncedCallback', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('debounces callback execution', async () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    act(() => {
      result.current('arg1', 'arg2');
    });
    expect(callback).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(300);
    });
    await waitFor(() => {
      expect(callback).toHaveBeenCalledWith('arg1', 'arg2');
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  it('cancels previous invocation on rapid calls', async () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    act(() => {
      result.current('first');
      vi.advanceTimersByTime(100);
      result.current('second');
      vi.advanceTimersByTime(100);
      result.current('third');
      vi.advanceTimersByTime(300);
    });
    
    await waitFor(() => {
      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith('third');
    });
  });

  it('flush executes immediately', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    result.current('debounced');
    result.current.flush('immediate');

    expect(callback).toHaveBeenCalledWith('immediate');
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('cancel prevents execution', async () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    act(() => {
      result.current('test');
      result.current.cancel();
      vi.advanceTimersByTime(300);
    });
    
    await waitFor(() => {
      expect(callback).not.toHaveBeenCalled();
    });
  });

  it('updates callback reference when callback changes', async () => {
    const callback1 = vi.fn();
    const callback2 = vi.fn();
    const { result, rerender } = renderHook(
      ({ callback }) => useDebouncedCallback(callback, 300),
      { initialProps: { callback: callback1 } }
    );

    act(() => {
      result.current('test');
      rerender({ callback: callback2 });
      result.current('updated');
      vi.advanceTimersByTime(300);
    });
    
    await waitFor(() => {
      expect(callback1).not.toHaveBeenCalled();
      expect(callback2).toHaveBeenCalledWith('updated');
    });
  });
});
