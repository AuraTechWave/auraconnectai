import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography } from '@theme';

interface NotificationBadgeProps {
  count: number;
  size?: 'small' | 'medium' | 'large';
  color?: string;
}

export const NotificationBadge: React.FC<NotificationBadgeProps> = ({
  count,
  size = 'medium',
  color = colors.error,
}) => {
  if (count <= 0) return null;

  const sizeStyles = {
    small: styles.small,
    medium: styles.medium,
    large: styles.large,
  };

  const displayCount = count > 99 ? '99+' : count.toString();

  return (
    <View style={[styles.badge, sizeStyles[size], { backgroundColor: color }]}>
      <Text style={[styles.text, size === 'small' && styles.smallText]}>
        {displayCount}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    position: 'absolute',
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 999,
  },
  small: {
    minWidth: 16,
    height: 16,
    top: -4,
    right: -4,
    paddingHorizontal: 4,
  },
  medium: {
    minWidth: 20,
    height: 20,
    top: -8,
    right: -8,
    paddingHorizontal: 6,
  },
  large: {
    minWidth: 24,
    height: 24,
    top: -10,
    right: -10,
    paddingHorizontal: 8,
  },
  text: {
    ...typography.caption,
    color: colors.white,
    fontSize: 11,
    fontWeight: 'bold',
  },
  smallText: {
    fontSize: 9,
  },
});
