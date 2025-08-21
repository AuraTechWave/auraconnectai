import { InteractionManager } from 'react-native';
import { memo } from 'react';

/**
 * Performance utilities for React Native
 */

// Delay heavy operations until after animations
export const runAfterInteractions = (callback: () => void) => {
  InteractionManager.runAfterInteractions(callback);
};

// Debounce function for search and input handlers
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

// Throttle function for scroll handlers
export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle = false;
  
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
};

// FlatList optimization configs
export const flatListOptimizations = {
  removeClippedSubviews: true,
  maxToRenderPerBatch: 10,
  initialNumToRender: 10,
  windowSize: 10,
  updateCellsBatchingPeriod: 50,
  getItemLayout: (itemHeight: number) => (
    _data: any,
    index: number
  ) => ({
    length: itemHeight,
    offset: itemHeight * index,
    index,
  }),
};

// Memoization helper for list items
export const memoizeListItem = <P extends object>(
  Component: React.ComponentType<P>,
  propsAreEqual?: (prevProps: P, nextProps: P) => boolean
) => {
  return memo(Component, propsAreEqual);
};

// Image optimization settings
export const imageOptimizations = {
  resizeMethod: 'resize' as const,
  // defaultSource should be set per component based on context
  cache: 'force-cache' as const,
};

// Animation performance settings
export const animationConfig = {
  useNativeDriver: true,
  duration: 300,
  easing: {
    in: 'ease-in',
    out: 'ease-out',
    inOut: 'ease-in-out',
  },
};