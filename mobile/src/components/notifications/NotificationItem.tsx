import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image } from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { formatDistanceToNow } from 'date-fns';
import { colors, typography } from '@theme';
import {
  StoredNotification,
  NotificationType,
} from '@services/notifications/types';

interface NotificationItemProps {
  notification: StoredNotification;
  onPress: (notification: StoredNotification) => void;
  onMarkAsRead?: (notificationId: string) => void;
}

export const NotificationItem: React.FC<NotificationItemProps> = ({
  notification,
  onPress,
  onMarkAsRead,
}) => {
  const getIcon = () => {
    const iconMap: Record<string, { name: string; color: string }> = {
      [NotificationType.ORDER_CREATED]: { name: 'receipt', color: colors.info },
      [NotificationType.ORDER_ACCEPTED]: {
        name: 'check-circle',
        color: colors.success,
      },
      [NotificationType.ORDER_PREPARING]: {
        name: 'chef-hat',
        color: colors.warning,
      },
      [NotificationType.ORDER_READY]: {
        name: 'bell-ring',
        color: colors.success,
      },
      [NotificationType.ORDER_COMPLETED]: {
        name: 'check-all',
        color: colors.textSecondary,
      },
      [NotificationType.ORDER_CANCELLED]: {
        name: 'close-circle',
        color: colors.error,
      },
      [NotificationType.PROMOTION]: { name: 'tag', color: colors.primary },
      [NotificationType.SYSTEM_UPDATE]: {
        name: 'information',
        color: colors.info,
      },
    };

    const iconConfig = iconMap[notification.data.type] || {
      name: 'bell',
      color: colors.textSecondary,
    };

    return (
      <View
        style={[
          styles.iconContainer,
          { backgroundColor: iconConfig.color + '20' },
        ]}>
        <Icon name={iconConfig.name} size={24} color={iconConfig.color} />
      </View>
    );
  };

  const handlePress = () => {
    if (!notification.read && onMarkAsRead) {
      onMarkAsRead(notification.id);
    }
    onPress(notification);
  };

  return (
    <TouchableOpacity
      style={[styles.container, !notification.read && styles.unreadContainer]}
      onPress={handlePress}
      activeOpacity={0.7}>
      {getIcon()}

      <View style={styles.content}>
        <View style={styles.header}>
          <Text
            style={[styles.title, !notification.read && styles.unreadText]}
            numberOfLines={1}>
            {notification.title}
          </Text>
          {!notification.read && <View style={styles.unreadDot} />}
        </View>

        <Text style={styles.body} numberOfLines={2}>
          {notification.body}
        </Text>

        <Text style={styles.time}>
          {formatDistanceToNow(notification.timestamp, { addSuffix: true })}
        </Text>
      </View>

      <Icon name="chevron-right" size={20} color={colors.textSecondary} />
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  unreadContainer: {
    backgroundColor: colors.background,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  content: {
    flex: 1,
    marginRight: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  title: {
    ...typography.subtitle,
    flex: 1,
    marginRight: 8,
  },
  unreadText: {
    fontWeight: '600',
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
  body: {
    ...typography.body,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  time: {
    ...typography.caption,
    color: colors.textSecondary,
  },
});
