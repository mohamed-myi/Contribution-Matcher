import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { VIRTUALIZATION } from '../constants';

/**
 * useVirtualization - Implements virtual scrolling for large lists.
 * 
 * Only renders visible items plus overscan, dramatically improving
 * performance for lists with 50+ items.
 * 
 * @param {Object} options
 * @param {Array} options.items - Array of items to virtualize
 * @param {number} options.itemHeight - Height of each item in pixels
 * @param {number} options.containerHeight - Height of the container
 * @param {number} options.overscan - Extra items to render (default: 5)
 * 
 * @returns {Object} { virtualItems, totalHeight, containerRef }
 * 
 * @example
 * const { virtualItems, totalHeight, containerRef } = useVirtualization({
 *   items: issues,
 *   itemHeight: 200,
 *   containerHeight: 600,
 * });
 * 
 * return (
 *   <div ref={containerRef} style={{ height: 600, overflow: 'auto' }}>
 *     <div style={{ height: totalHeight, position: 'relative' }}>
 *       {virtualItems.map(({ item, index, style }) => (
 *         <div key={item.id} style={style}>
 *           <IssueCard issue={item} />
 *         </div>
 *       ))}
 *     </div>
 *   </div>
 * );
 */
export function useVirtualization({
  items = [],
  itemHeight = VIRTUALIZATION.ITEM_HEIGHT,
  containerHeight = 600,
  overscan = VIRTUALIZATION.OVERSCAN,
}) {
  const containerRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  
  // Handle scroll events
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    
    let ticking = false;
    
    const handleScroll = () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          setScrollTop(container.scrollTop);
          ticking = false;
        });
        ticking = true;
      }
    };
    
    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);
  
  // Calculate virtual items
  const { virtualItems, totalHeight } = useMemo(() => {
    const totalHeight = items.length * itemHeight;
    
    // Don't virtualize small lists
    if (items.length < VIRTUALIZATION.MIN_ITEMS_FOR_VIRTUAL) {
      return {
        virtualItems: items.map((item, index) => ({
          item,
          index,
          style: {
            position: 'absolute',
            top: index * itemHeight,
            left: 0,
            right: 0,
            height: itemHeight,
          },
        })),
        totalHeight,
      };
    }
    
    // Calculate visible range
    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const endIndex = Math.min(
      items.length - 1,
      Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
    );
    
    // Build virtual items
    const virtualItems = [];
    for (let i = startIndex; i <= endIndex; i++) {
      virtualItems.push({
        item: items[i],
        index: i,
        style: {
          position: 'absolute',
          top: i * itemHeight,
          left: 0,
          right: 0,
          height: itemHeight,
        },
      });
    }
    
    return { virtualItems, totalHeight };
  }, [items, itemHeight, containerHeight, scrollTop, overscan]);
  
  // Scroll to index
  const scrollToIndex = useCallback((index, behavior = 'smooth') => {
    const container = containerRef.current;
    if (!container) return;
    
    const top = index * itemHeight;
    container.scrollTo({ top, behavior });
  }, [itemHeight]);
  
  // Scroll to top
  const scrollToTop = useCallback((behavior = 'smooth') => {
    const container = containerRef.current;
    if (!container) return;
    
    container.scrollTo({ top: 0, behavior });
  }, []);
  
  return {
    virtualItems,
    totalHeight,
    containerRef,
    scrollToIndex,
    scrollToTop,
    isVirtualized: items.length >= VIRTUALIZATION.MIN_ITEMS_FOR_VIRTUAL,
  };
}

export default useVirtualization;

