import { StyleSheet } from 'react-native';
import { colors, spacing, typography, borderRadius, shadows } from '../constants/designSystem';

// Shared container styles
export const containerStyles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: spacing.xxl,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});

// Shared text styles
export const textStyles = StyleSheet.create({
  h1: {
    fontSize: typography.sizes.xxl,
    fontWeight: typography.weights.bold as any,
    color: colors.text.primary,
    marginBottom: spacing.md,
  },
  h2: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.semibold as any,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
  h3: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.semibold as any,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
  body: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.regular as any,
    color: colors.text.primary,
    lineHeight: typography.sizes.md * 1.5,
  },
  caption: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.regular as any,
    color: colors.text.secondary,
  },
  error: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.regular as any,
    color: colors.error.base,
  },
});

// Shared form styles
export const formStyles = StyleSheet.create({
  inputContainer: {
    marginBottom: spacing.md,
  },
  label: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.medium as any,
    color: colors.text.primary,
    marginBottom: spacing.xs,
  },
  helperText: {
    fontSize: typography.sizes.xs,
    color: colors.text.secondary,
    marginTop: spacing.xs,
  },
});

// Shared list styles
export const listStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  contentContainer: {
    paddingVertical: spacing.sm,
  },
  separator: {
    height: 1,
    backgroundColor: colors.border.light,
    marginHorizontal: spacing.md,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: spacing.xxxl,
  },
  emptyText: {
    fontSize: typography.sizes.md,
    color: colors.text.secondary,
    textAlign: 'center',
  },
});

// Shared shadow styles
export const shadowStyles = StyleSheet.create({
  sm: shadows.sm,
  md: shadows.md,
  lg: shadows.lg,
  xl: shadows.xl,
});

// Shared spacing utilities
export const spacingStyles = StyleSheet.create({
  p_xs: { padding: spacing.xs },
  p_sm: { padding: spacing.sm },
  p_md: { padding: spacing.md },
  p_lg: { padding: spacing.lg },
  p_xl: { padding: spacing.xl },
  
  px_xs: { paddingHorizontal: spacing.xs },
  px_sm: { paddingHorizontal: spacing.sm },
  px_md: { paddingHorizontal: spacing.md },
  px_lg: { paddingHorizontal: spacing.lg },
  px_xl: { paddingHorizontal: spacing.xl },
  
  py_xs: { paddingVertical: spacing.xs },
  py_sm: { paddingVertical: spacing.sm },
  py_md: { paddingVertical: spacing.md },
  py_lg: { paddingVertical: spacing.lg },
  py_xl: { paddingVertical: spacing.xl },
  
  m_xs: { margin: spacing.xs },
  m_sm: { margin: spacing.sm },
  m_md: { margin: spacing.md },
  m_lg: { margin: spacing.lg },
  m_xl: { margin: spacing.xl },
  
  mx_xs: { marginHorizontal: spacing.xs },
  mx_sm: { marginHorizontal: spacing.sm },
  mx_md: { marginHorizontal: spacing.md },
  mx_lg: { marginHorizontal: spacing.lg },
  mx_xl: { marginHorizontal: spacing.xl },
  
  my_xs: { marginVertical: spacing.xs },
  my_sm: { marginVertical: spacing.sm },
  my_md: { marginVertical: spacing.md },
  my_lg: { marginVertical: spacing.lg },
  my_xl: { marginVertical: spacing.xl },
});

// Layout utilities
export const layoutStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rowCenter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  column: {
    flexDirection: 'column',
  },
  columnCenter: {
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
  },
  flex1: {
    flex: 1,
  },
  flexGrow: {
    flexGrow: 1,
  },
  flexShrink: {
    flexShrink: 1,
  },
});

// Performance optimization utilities
export const performanceStyles = {
  // Use these for FlatList optimization
  listOptimization: {
    removeClippedSubviews: true,
    maxToRenderPerBatch: 10,
    initialNumToRender: 10,
    windowSize: 10,
    updateCellsBatchingPeriod: 50,
  },
  
  // Use for images
  imageOptimization: {
    resizeMode: 'cover' as const,
    fadeDuration: 0, // Disable fade for performance
  },
};