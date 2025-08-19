import React from 'react';
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
  TouchableOpacityProps,
  View,
} from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, spacing, typography, borderRadius, shadows } from '../../constants/designSystem';

interface ButtonProps extends TouchableOpacityProps {
  title?: string;
  variant?: 'primary' | 'secondary' | 'tertiary' | 'danger' | 'ghost' | 'outline';
  size?: 'small' | 'medium' | 'large';
  icon?: string;
  iconPosition?: 'left' | 'right';
  loading?: boolean;
  disabled?: boolean;
  fullWidth?: boolean;
  children?: React.ReactNode;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

export const Button: React.FC<ButtonProps> = ({
  title,
  variant = 'primary',
  size = 'medium',
  icon,
  iconPosition = 'left',
  loading = false,
  disabled = false,
  fullWidth = false,
  children,
  style,
  textStyle,
  onPress,
  ...props
}) => {
  const isDisabled = disabled || loading;

  const getButtonStyle = (): ViewStyle => {
    const baseStyle: ViewStyle = {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: borderRadius.md,
      ...shadows.sm,
    };

    const sizeStyles: Record<string, ViewStyle> = {
      small: {
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
        minHeight: 32,
      },
      medium: {
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        minHeight: 44,
      },
      large: {
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.md,
        minHeight: 56,
      },
    };

    const variantStyles: Record<string, ViewStyle> = {
      primary: {
        backgroundColor: isDisabled ? colors.neutral[300] : colors.primary[500],
      },
      secondary: {
        backgroundColor: isDisabled ? colors.neutral[300] : colors.secondary[500],
      },
      tertiary: {
        backgroundColor: isDisabled ? colors.neutral[300] : colors.accent[500],
      },
      danger: {
        backgroundColor: isDisabled ? colors.neutral[300] : colors.error[500],
      },
      ghost: {
        backgroundColor: 'transparent',
        shadowOpacity: 0,
        elevation: 0,
      },
      outline: {
        backgroundColor: 'transparent',
        borderWidth: 1,
        borderColor: isDisabled ? colors.neutral[300] : colors.primary[500],
        shadowOpacity: 0,
        elevation: 0,
      },
    };

    return {
      ...baseStyle,
      ...sizeStyles[size],
      ...variantStyles[variant],
      ...(fullWidth && { width: '100%' }),
      opacity: isDisabled ? 0.6 : 1,
    };
  };

  const getTextStyle = (): TextStyle => {
    const sizeStyles: Record<string, TextStyle> = {
      small: {
        fontSize: typography.fontSize.body,
        lineHeight: typography.lineHeight.body,
        fontWeight: typography.fontWeight.medium,
      },
      medium: {
        fontSize: typography.fontSize.bodyLarge,
        lineHeight: typography.lineHeight.bodyLarge,
        fontWeight: typography.fontWeight.medium,
      },
      large: {
        fontSize: typography.fontSize.subtitle,
        lineHeight: typography.lineHeight.subtitle,
        fontWeight: typography.fontWeight.semiBold,
      },
    };

    const variantTextColors: Record<string, string> = {
      primary: colors.text.inverse,
      secondary: colors.text.inverse,
      tertiary: colors.text.inverse,
      danger: colors.text.inverse,
      ghost: isDisabled ? colors.text.disabled : colors.primary[500],
      outline: isDisabled ? colors.text.disabled : colors.primary[500],
    };

    return {
      ...sizeStyles[size],
      color: variantTextColors[variant],
      marginHorizontal: icon ? spacing.xs : 0,
    };
  };

  const getIconSize = (): number => {
    const sizes: Record<string, number> = {
      small: 16,
      medium: 20,
      large: 24,
    };
    return sizes[size];
  };

  const getIconColor = (): string => {
    if (variant === 'ghost' || variant === 'outline') {
      return isDisabled ? colors.text.disabled : colors.primary[500];
    }
    return colors.text.inverse;
  };

  const renderContent = () => {
    if (loading) {
      return <ActivityIndicator size="small" color={getIconColor()} />;
    }

    return (
      <>
        {icon && iconPosition === 'left' && (
          <MaterialCommunityIcons
            name={icon}
            size={getIconSize()}
            color={getIconColor()}
            style={{ marginRight: spacing.xs }}
          />
        )}
        {children || (title && <Text style={[getTextStyle(), textStyle]}>{title}</Text>)}
        {icon && iconPosition === 'right' && (
          <MaterialCommunityIcons
            name={icon}
            size={getIconSize()}
            color={getIconColor()}
            style={{ marginLeft: spacing.xs }}
          />
        )}
      </>
    );
  };

  return (
    <TouchableOpacity
      style={[getButtonStyle(), style]}
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.7}
      {...props}
    >
      {renderContent()}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
});