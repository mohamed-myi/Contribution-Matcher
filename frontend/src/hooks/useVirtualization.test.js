import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useVirtualization } from './useVirtualization';

describe('useVirtualization', () => {
  const createItems = (count) => 
    Array.from({ length: count }, (_, i) => ({ id: i, title: `Item ${i}` }));

  it('returns virtualItems and totalHeight', () => {
    const items = createItems(10);
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 100,
        containerHeight: 500,
      })
    );

    expect(result.current.virtualItems).toBeDefined();
    expect(result.current.totalHeight).toBe(1000); // 10 items * 100px
  });

  it('returns containerRef', () => {
    const items = createItems(10);
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 100,
        containerHeight: 500,
      })
    );

    expect(result.current.containerRef).toBeDefined();
    expect(result.current.containerRef.current).toBe(null);
  });

  it('does not virtualize small lists', () => {
    const items = createItems(30); // Less than MIN_ITEMS_FOR_VIRTUAL (50)
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 100,
        containerHeight: 500,
      })
    );

    expect(result.current.isVirtualized).toBe(false);
    expect(result.current.virtualItems.length).toBe(30); // All items rendered
  });

  it('virtualizes large lists', () => {
    const items = createItems(100);
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 100,
        containerHeight: 500,
      })
    );

    expect(result.current.isVirtualized).toBe(true);
    // Should only render visible items + overscan
    expect(result.current.virtualItems.length).toBeLessThan(100);
  });

  it('calculates correct totalHeight', () => {
    const items = createItems(50);
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 150,
        containerHeight: 600,
      })
    );

    expect(result.current.totalHeight).toBe(7500); // 50 * 150
  });

  it('virtualItems have correct style properties', () => {
    const items = createItems(10);
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 100,
        containerHeight: 500,
      })
    );

    const firstItem = result.current.virtualItems[0];
    expect(firstItem.style.position).toBe('absolute');
    expect(firstItem.style.top).toBe(0);
    expect(firstItem.style.height).toBe(100);
  });

  it('scrollToIndex scrolls container', () => {
    const items = createItems(100);
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 100,
        containerHeight: 500,
      })
    );

    // Create a mock container
    const mockContainer = {
      scrollTo: vi.fn(),
    };
    result.current.containerRef.current = mockContainer;

    act(() => {
      result.current.scrollToIndex(10);
    });

    expect(mockContainer.scrollTo).toHaveBeenCalledWith({
      top: 1000,
      behavior: 'smooth',
    });
  });

  it('scrollToTop scrolls to top', () => {
    const items = createItems(100);
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 100,
        containerHeight: 500,
      })
    );

    const mockContainer = {
      scrollTo: vi.fn(),
    };
    result.current.containerRef.current = mockContainer;

    act(() => {
      result.current.scrollToTop();
    });

    expect(mockContainer.scrollTo).toHaveBeenCalledWith({
      top: 0,
      behavior: 'smooth',
    });
  });

  it('respects overscan parameter', () => {
    const items = createItems(100);
    const { result } = renderHook(() =>
      useVirtualization({
        items,
        itemHeight: 100,
        containerHeight: 500,
        overscan: 10,
      })
    );

    // With overscan of 10, should render more items
    expect(result.current.virtualItems.length).toBeGreaterThan(5);
  });
});
