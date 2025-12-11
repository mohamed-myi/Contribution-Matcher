import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebounce, useDebouncedCallback } from './useDebounce';

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('initial', 300));
    expect(result.current).toBe('initial');
  });

  it('debounces value changes', () => {
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
      vi.runAllTimers();
    });
    expect(result.current).toBe('updated');
  });

  it('cancels previous timeout on rapid changes', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'first' } }
    );

    act(() => {
      rerender({ value: 'second' });
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    act(() => {
      rerender({ value: 'third' });
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    act(() => {
      rerender({ value: 'fourth' });
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    
    expect(result.current).toBe('fourth');
  });

  it('respects custom delay', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: 'test' } }
    );

    act(() => {
      rerender({ value: 'updated' });
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe('test'); // Still old value

    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe('updated');
  });
});

describe('useDebouncedCallback', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('debounces callback execution', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    act(() => {
      result.current('arg1', 'arg2');
    });
    expect(callback).not.toHaveBeenCalled();

    act(() => {
      vi.runAllTimers();
    });
    expect(callback).toHaveBeenCalledWith('arg1', 'arg2');
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('cancels previous invocation on rapid calls', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    act(() => {
      result.current('first');
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    act(() => {
      result.current('second');
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    act(() => {
      result.current('third');
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    
    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith('third');
  });

  it('flush executes immediately', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    result.current('debounced');
    result.current.flush('immediate');

    expect(callback).toHaveBeenCalledWith('immediate');
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('cancel prevents execution', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    act(() => {
      result.current('test');
      result.current.cancel();
      vi.advanceTimersByTime(300);
    });
    
    expect(callback).not.toHaveBeenCalled();
  });

  it('updates callback reference when callback changes', () => {
    const callback1 = vi.fn();
    const callback2 = vi.fn();
    const { result, rerender } = renderHook(
      ({ callback }) => useDebouncedCallback(callback, 300),
      { initialProps: { callback: callback1 } }
    );

    act(() => {
      result.current('test');
    });
    act(() => {
      rerender({ callback: callback2 });
    });
    act(() => {
      result.current('updated');
    });
    act(() => {
      vi.runAllTimers();
    });
    
    expect(callback1).not.toHaveBeenCalled();
    expect(callback2).toHaveBeenCalledWith('updated');
  });
});
