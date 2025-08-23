import React, { useState } from 'react';
import {
  View,
  TextInput,
  Text,
  StyleSheet,
  ViewStyle,
  TextStyle,
  TextInputProps,
  TouchableOpacity,
  Animated,
} from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, spacing, typography, borderRadius } from '../../constants/designSystem';

interface InputProps extends TextInputProps {
  label?: string;
  error?: string;
  helper?: string;
  leftIcon?: string;
  rightIcon?: string;
  onRightIconPress?: () => void;
  containerStyle?: ViewStyle;
  inputStyle?: TextStyle;
  variant?: 'outlined' | 'filled' | 'underlined';
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
  accessibilityLabel?: string;
  accessibilityHint?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helper,
  leftIcon,
  rightIcon,
  onRightIconPress,
  containerStyle,
  inputStyle,
  variant = 'outlined',
  size = 'medium',
  disabled = false,
  accessibilityLabel,
  accessibilityHint,
  value,
  onFocus,
  onBlur,
  ...props
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const [animatedValue] = useState(new Animated.Value(value ? 1 : 0));

  const handleFocus = (e: any) => {
    setIsFocused(true);
    Animated.timing(animatedValue, {
      toValue: 1,
      duration: 200,
      useNativeDriver: false,
    }).start();
    onFocus?.(e);
  };

  const handleBlur = (e: any) => {
    setIsFocused(false);
    if (!value) {
      Animated.timing(animatedValue, {
        toValue: 0,
        duration: 200,
        useNativeDriver: false,
      }).start();
    }
    onBlur?.(e);
  };

  const getContainerStyle = (): ViewStyle => {
    const baseStyle: ViewStyle = {
      marginVertical: spacing.xs,
    };

    return baseStyle;
  };

  const getInputContainerStyle = (): ViewStyle => {
    const sizeStyles: Record<string, ViewStyle> = {
      small: {
        minHeight: 40,
      },
      medium: {
        minHeight: 48,
      },
      large: {
        minHeight: 56,
      },
    };

    const variantStyles: Record<string, ViewStyle> = {
      outlined: {
        borderWidth: 1,
        borderColor: error
          ? colors.error[500]
          : isFocused
          ? colors.primary[500]
          : colors.border.default,
        borderRadius: borderRadius.md,
        backgroundColor: disabled ? colors.background.tertiary : colors.background.primary,
        paddingHorizontal: spacing.md,
      },
      filled: {
        backgroundColor: disabled
          ? colors.background.tertiary
          : isFocused
          ? colors.neutral[50]
          : colors.background.secondary,
        borderRadius: borderRadius.md,
        borderBottomWidth: 2,
        borderBottomColor: error
          ? colors.error[500]
          : isFocused
          ? colors.primary[500]
          : 'transparent',
        paddingHorizontal: spacing.md,
      },
      underlined: {
        borderBottomWidth: 1,
        borderBottomColor: error
          ? colors.error[500]
          : isFocused
          ? colors.primary[500]
          : colors.border.default,
        paddingHorizontal: 0,
        backgroundColor: 'transparent',
      },
    };

    return {
      flexDirection: 'row',
      alignItems: 'center',
      ...sizeStyles[size],
      ...variantStyles[variant],
    };
  };

  const getInputStyle = (): TextStyle => {
    const sizeStyles: Record<string, TextStyle> = {
      small: {
        fontSize: typography.fontSize.body,
        lineHeight: typography.lineHeight.body,
      },
      medium: {
        fontSize: typography.fontSize.bodyLarge,
        lineHeight: typography.lineHeight.bodyLarge,
      },
      large: {
        fontSize: typography.fontSize.subtitle,
        lineHeight: typography.lineHeight.subtitle,
      },
    };

    return {
      flex: 1,
      color: disabled ? colors.text.disabled : colors.text.primary,
      ...sizeStyles[size],
      paddingVertical: spacing.xs,
    };
  };

  const getLabelStyle = (): TextStyle => {
    const labelTranslateY = animatedValue.interpolate({
      inputRange: [0, 1],
      outputRange: [18, 0],
    });

    const labelScale = animatedValue.interpolate({
      inputRange: [0, 1],
      outputRange: [1, 0.85],
    });

    return {
      position: 'absolute',
      left: variant === 'underlined' ? 0 : spacing.md,
      top: -spacing.xs,
      backgroundColor: variant === 'outlined' ? colors.background.primary : 'transparent',
      paddingHorizontal: spacing.xxs,
      transform: [
        { translateY: labelTranslateY },
        { scale: labelScale },
      ],
    };
  };

  const getIconSize = (): number => {
    const sizes: Record<string, number> = {
      small: 18,
      medium: 20,
      large: 24,
    };
    return sizes[size];
  };

  return (
    <View style={[getContainerStyle(), containerStyle]}>
      {label && variant === 'outlined' && (
        <Animated.Text
          style={[
            getLabelStyle(),
            {
              color: error
                ? colors.error[500]
                : isFocused
                ? colors.primary[500]
                : colors.text.secondary,
              fontSize: typography.fontSize.body,
            },
          ]}
        >
          {label}
        </Animated.Text>
      )}
      {label && variant !== 'outlined' && (
        <Text
          style={{
            fontSize: typography.fontSize.body,
            color: error
              ? colors.error[500]
              : isFocused
              ? colors.primary[500]
              : colors.text.secondary,
            marginBottom: spacing.xxs,
          }}
        >
          {label}
        </Text>
      )}
      <View style={getInputContainerStyle()}>
        {leftIcon && (
          <MaterialCommunityIcons
            name={leftIcon}
            size={getIconSize()}
            color={disabled ? colors.text.disabled : colors.text.secondary}
            style={{ marginRight: spacing.xs }}
          />
        )}
        <TextInput
          style={[getInputStyle(), inputStyle]}
          value={value}
          onFocus={handleFocus}
          onBlur={handleBlur}
          editable={!disabled}
          placeholderTextColor={colors.text.tertiary}
          accessible={true}
          accessibilityLabel={accessibilityLabel || label || props.placeholder || 'Text input'}
          accessibilityHint={accessibilityHint || helper}
          accessibilityState={{
            disabled: disabled,
          }}
          accessibilityValue={{
            text: value,
          }}
          {...props}
        />
        {rightIcon && (
          <TouchableOpacity
            onPress={onRightIconPress}
            disabled={!onRightIconPress}
            activeOpacity={0.7}
          >
            <MaterialCommunityIcons
              name={rightIcon}
              size={getIconSize()}
              color={disabled ? colors.text.disabled : colors.text.secondary}
              style={{ marginLeft: spacing.xs }}
            />
          </TouchableOpacity>
        )}
      </View>
      {error && (
        <Text 
          style={styles.errorText}
          accessible={true}
          accessibilityRole="alert"
          accessibilityLiveRegion="polite"
        >
          {error}
        </Text>
      )}
      {helper && !error && (
        <Text 
          style={styles.helperText}
          accessible={true}
          accessibilityRole="text"
        >
          {helper}
        </Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  errorText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.error, // Use AA compliant error text color
    marginTop: spacing.xxs,
    marginLeft: spacing.xs,
  },
  helperText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginTop: spacing.xxs,
    marginLeft: spacing.xs,
  },
});