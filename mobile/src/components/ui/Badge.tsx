import React from 'react';
import { View, Text, StyleSheet, ViewStyle, TextStyle } from 'react-native';
import { colors, spacing, typography, borderRadius } from '../../constants/designSystem';

interface BadgeProps {
  label: string | number;
  variant?: 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';
  size?: 'small' | 'medium' | 'large';
  dot?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

export const Badge: React.FC<BadgeProps> = ({
  label,
  variant = 'default',
  size = 'medium',
  dot = false,
  style,
  textStyle,
}) => {
  const getBadgeStyle = (): ViewStyle => {
    const sizeStyles: Record<string, ViewStyle> = {
      small: {
        paddingHorizontal: dot ? 0 : spacing.xs,
        paddingVertical: dot ? 0 : 2,
        minWidth: dot ? 8 : 16,
        height: dot ? 8 : 16,
      },
      medium: {
        paddingHorizontal: dot ? 0 : spacing.xs,
        paddingVertical: dot ? 0 : spacing.xxs,
        minWidth: dot ? 10 : 20,
        height: dot ? 10 : 20,
      },
      large: {
        paddingHorizontal: dot ? 0 : spacing.sm,
        paddingVertical: dot ? 0 : spacing.xs,
        minWidth: dot ? 12 : 24,
        height: dot ? 12 : 24,
      },
    };

    const variantStyles: Record<string, ViewStyle> = {
      default: {
        backgroundColor: colors.neutral[200],
      },
      primary: {
        backgroundColor: colors.primary[500],
      },
      secondary: {
        backgroundColor: colors.secondary[500],
      },
      success: {
        backgroundColor: colors.success[500],
      },
      warning: {
        backgroundColor: colors.warning[500],
      },
      error: {
        backgroundColor: colors.error[500],
      },
      info: {
        backgroundColor: colors.primary[400],
      },
    };

    return {
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: borderRadius.full,
      ...sizeStyles[size],
      ...variantStyles[variant],
    };
  };

  const getTextStyle = (): TextStyle => {
    const sizeStyles: Record<string, TextStyle> = {
      small: {
        fontSize: typography.fontSize.tiny,
        lineHeight: typography.lineHeight.tiny,
      },
      medium: {
        fontSize: typography.fontSize.caption,
        lineHeight: typography.lineHeight.caption,
      },
      large: {
        fontSize: typography.fontSize.body,
        lineHeight: typography.lineHeight.body,
      },
    };

    const textColor = variant === 'default' ? colors.text.primary : colors.text.inverse;

    return {
      color: textColor,
      fontWeight: typography.fontWeight.semiBold,
      ...sizeStyles[size],
    };
  };

  if (dot) {
    return <View style={[getBadgeStyle(), style]} />;
  }

  return (
    <View style={[getBadgeStyle(), style]}>
      <Text style={[getTextStyle(), textStyle]}>{label}</Text>
    </View>
  );
};

interface BadgeContainerProps {
  children: React.ReactNode;
  badge?: React.ReactNode;
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
}

export const BadgeContainer: React.FC<BadgeContainerProps> = ({
  children,
  badge,
  position = 'top-right',
}) => {
  const getBadgePosition = (): ViewStyle => {
    const positions: Record<string, ViewStyle> = {
      'top-left': {
        top: -4,
        left: -4,
      },
      'top-right': {
        top: -4,
        right: -4,
      },
      'bottom-left': {
        bottom: -4,
        left: -4,
      },
      'bottom-right': {
        bottom: -4,
        right: -4,
      },
    };

    return {
      position: 'absolute',
      ...positions[position],
      zIndex: 1,
    };
  };

  return (
    <View style={styles.container}>
      {children}
      {badge && <View style={getBadgePosition()}>{badge}</View>}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'relative',
  },
});