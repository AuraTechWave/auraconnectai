import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, typography } from '@theme';
import { NotificationService } from '@services/notifications/NotificationService';
import { NotificationItem } from '@components/notifications/NotificationItem';
import { NotificationSettingsModal } from '@components/notifications/NotificationSettingsModal';
import { StoredNotification } from '@services/notifications/types';
import { showToast } from '@utils/toast';

interface NotificationsScreenProps {
  navigation: any;
}

export const NotificationsScreen: React.FC<NotificationsScreenProps> = ({
  navigation,
}) => {
  const [notifications, setNotifications] = useState<StoredNotification[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const notificationService = NotificationService.getInstance();

  useEffect(() => {
    loadNotifications();
    const cleanup = setupListeners();

    return () => {
      cleanup();
    };
  }, []);

  const setupListeners = () => {
    const handleNotificationDisplayed = () => {
      loadNotifications();
    };

    const handleNavigateToOrder = (orderId: string) => {
      navigation.navigate('OrderDetails', { orderId });
    };

    // Listen for new notifications
    notificationService.on('notificationDisplayed', handleNotificationDisplayed);

    // Listen for navigation events
    notificationService.on('navigateToOrder', handleNavigateToOrder);

    // Return cleanup function
    return () => {
      notificationService.off('notificationDisplayed', handleNotificationDisplayed);
      notificationService.off('navigateToOrder', handleNavigateToOrder);
    };
  };

  const loadNotifications = async () => {
    try {
      const stored = await notificationService.getStoredNotifications();
      setNotifications(stored);
      
      const unread = stored.filter(n => !n.read).length;
      setUnreadCount(unread);
    } catch (error) {
      console.error('Failed to load notifications', error);
    }
  };

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadNotifications();
    setRefreshing(false);
  }, []);

  const handleNotificationPress = useCallback((notification: StoredNotification) => {
    if (notification.data.type.includes('order_') && notification.data.orderId) {
      navigation.navigate('OrderDetails', { orderId: notification.data.orderId });
    }
  }, [navigation]);

  const handleMarkAsRead = useCallback(async (notificationId: string) => {
    await notificationService.markNotificationAsRead(notificationId);
    await loadNotifications();
  }, []);

  const handleMarkAllAsRead = useCallback(async () => {
    try {
      const unreadNotifications = notifications.filter(n => !n.read);
      for (const notification of unreadNotifications) {
        await notificationService.markNotificationAsRead(notification.id);
      }
      await loadNotifications();
      showToast('success', 'Success', 'All notifications marked as read');
    } catch (error) {
      showToast('error', 'Error', 'Failed to mark notifications as read');
    }
  }, [notifications]);

  const handleClearAll = useCallback(async () => {
    Alert.alert(
      'Clear All Notifications',
      'Are you sure you want to clear all notifications?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear All',
          style: 'destructive',
          onPress: async () => {
            await notificationService.clearNotificationHistory();
            setNotifications([]);
            setUnreadCount(0);
            showToast('success', 'Success', 'All notifications cleared');
          },
        },
      ],
    );
  }, []);

  const renderHeader = () => (
    <View style={styles.header}>
      <View>
        <Text style={styles.title}>Notifications</Text>
        {unreadCount > 0 && (
          <Text style={styles.subtitle}>{unreadCount} unread</Text>
        )}
      </View>
      <View style={styles.headerActions}>
        {unreadCount > 0 && (
          <TouchableOpacity
            style={styles.headerButton}
            onPress={handleMarkAllAsRead}
          >
            <Icon name="check-all" size={24} color={colors.primary} />
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={styles.headerButton}
          onPress={() => setShowSettings(true)}
        >
          <Icon name="cog" size={24} color={colors.text} />
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Icon name="bell-off-outline" size={64} color={colors.textSecondary} />
      <Text style={styles.emptyText}>No notifications yet</Text>
      <Text style={styles.emptySubtext}>
        You'll receive notifications for order updates and important announcements
      </Text>
    </View>
  );

  const renderFooter = () => {
    if (notifications.length === 0) return null;

    return (
      <TouchableOpacity
        style={styles.clearButton}
        onPress={handleClearAll}
      >
        <Icon name="trash-can-outline" size={20} color={colors.error} />
        <Text style={styles.clearButtonText}>Clear All</Text>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <FlatList
        data={notifications}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <NotificationItem
            notification={item}
            onPress={handleNotificationPress}
            onMarkAsRead={handleMarkAsRead}
          />
        )}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={renderEmpty}
        ListFooterComponent={renderFooter}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            colors={[colors.primary]}
          />
        }
      />

      <NotificationSettingsModal
        visible={showSettings}
        onClose={() => setShowSettings(false)}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  listContent: {
    flexGrow: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    padding: 16,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    ...typography.title,
    marginBottom: 4,
  },
  subtitle: {
    ...typography.caption,
    color: colors.primary,
  },
  headerActions: {
    flexDirection: 'row',
  },
  headerButton: {
    marginLeft: 16,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 100,
    paddingHorizontal: 32,
  },
  emptyText: {
    ...typography.title,
    color: colors.textSecondary,
    marginTop: 16,
  },
  emptySubtext: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: 8,
    textAlign: 'center',
  },
  clearButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    marginTop: 16,
    marginHorizontal: 16,
    backgroundColor: colors.surface,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.error + '20',
  },
  clearButtonText: {
    ...typography.button,
    color: colors.error,
    marginLeft: 8,
  },
});