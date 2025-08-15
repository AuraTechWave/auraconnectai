import React, { useState, useCallback } from 'react';
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
import { withObservables } from '@nozbe/with-observables';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { format } from 'date-fns';

import database from '@database';
import Order from '@database/models/Order';
import { SyncStatusBar, SyncProgressModal } from '@components/sync';
import { useOfflineSync, useCollectionSync } from '@hooks/useOfflineSync';
import { colors, typography } from '@theme';
import { Q } from '@nozbe/watermelondb';

interface OrderItemProps {
  order: Order;
  onPress: (order: Order) => void;
}

const OrderItem: React.FC<OrderItemProps> = ({ order, onPress }) => {
  const getSyncIcon = () => {
    switch (order.syncStatus) {
      case 'pending':
        return (
          <Icon name="cloud-upload-outline" size={20} color={colors.warning} />
        );
      case 'conflict':
        return <Icon name="alert-circle" size={20} color={colors.error} />;
      case 'synced':
        return (
          <Icon name="cloud-check-outline" size={20} color={colors.success} />
        );
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    switch (order.status) {
      case 'pending':
        return colors.warning;
      case 'preparing':
        return colors.info;
      case 'ready':
        return colors.success;
      case 'completed':
        return colors.textSecondary;
      case 'cancelled':
        return colors.error;
      default:
        return colors.text;
    }
  };

  return (
    <TouchableOpacity
      style={styles.orderItem}
      onPress={() => onPress(order)}
      activeOpacity={0.7}>
      <View style={styles.orderHeader}>
        <Text style={styles.orderNumber}>Order #{order.orderNumber}</Text>
        {getSyncIcon()}
      </View>

      <View style={styles.orderContent}>
        <View style={styles.orderInfo}>
          <Text style={styles.customerName}>
            {order.customerName || 'Walk-in Customer'}
          </Text>
          <Text style={styles.orderTime}>
            {format(new Date(order.createdAt), 'MMM dd, h:mm a')}
          </Text>
        </View>

        <View style={styles.orderStats}>
          <Text style={[styles.orderStatus, { color: getStatusColor() }]}>
            {order.status.toUpperCase()}
          </Text>
          <Text style={styles.orderTotal}>${order.totalAmount.toFixed(2)}</Text>
        </View>
      </View>

      {order.notes && (
        <Text style={styles.orderNotes} numberOfLines={1}>
          Note: {order.notes}
        </Text>
      )}
    </TouchableOpacity>
  );
};

interface OfflineOrdersScreenProps {
  orders: Order[];
  navigation: any;
}

const OfflineOrdersScreen: React.FC<OfflineOrdersScreenProps> = ({
  orders,
  navigation,
}) => {
  const [refreshing, setRefreshing] = useState(false);
  const [showSyncModal, setShowSyncModal] = useState(false);
  const { syncState, sync, isOffline } = useOfflineSync();
  const collectionStats = useCollectionSync('orders');

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      if (!isOffline) {
        await sync();
      }
    } finally {
      setRefreshing(false);
    }
  }, [sync, isOffline]);

  const handleOrderPress = useCallback(
    (order: Order) => {
      navigation.navigate('OrderDetails', { orderId: order.id });
    },
    [navigation],
  );

  const handleCreateOrder = useCallback(() => {
    navigation.navigate('CreateOrder');
  }, [navigation]);

  const handleSyncPress = useCallback(() => {
    if (isOffline) {
      Alert.alert(
        'Offline Mode',
        'You are currently offline. Orders will be synced when you reconnect.',
        [{ text: 'OK' }],
      );
    } else {
      setShowSyncModal(true);
      sync();
    }
  }, [isOffline, sync]);

  const renderHeader = () => (
    <View style={styles.header}>
      <Text style={styles.title}>Orders</Text>
      <View style={styles.headerStats}>
        <Text style={styles.statsText}>{collectionStats.total} total</Text>
        {collectionStats.pending > 0 && (
          <Text style={[styles.statsText, { color: colors.warning }]}>
            {collectionStats.pending} pending
          </Text>
        )}
        {collectionStats.conflicts > 0 && (
          <Text style={[styles.statsText, { color: colors.error }]}>
            {collectionStats.conflicts} conflicts
          </Text>
        )}
      </View>
    </View>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Icon name="receipt" size={64} color={colors.textSecondary} />
      <Text style={styles.emptyText}>No orders yet</Text>
      <Text style={styles.emptySubtext}>
        {isOffline
          ? 'You can create orders offline'
          : 'Create your first order to get started'}
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <SyncStatusBar onPress={handleSyncPress} />

      <FlatList
        data={orders}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <OrderItem order={item} onPress={handleOrderPress} />
        )}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            colors={[colors.primary]}
          />
        }
      />

      <TouchableOpacity
        style={styles.fab}
        onPress={handleCreateOrder}
        activeOpacity={0.8}>
        <Icon name="plus" size={24} color={colors.white} />
      </TouchableOpacity>

      <SyncProgressModal
        visible={showSyncModal}
        onClose={() => setShowSyncModal(false)}
      />
    </SafeAreaView>
  );
};

// Enhance component with observable data
const enhance = withObservables([''], () => ({
  orders: database.collections
    .get('orders')
    .query(Q.where('is_deleted', false), Q.sortBy('created_at', Q.desc))
    .observe(),
}));

export default enhance(OfflineOrdersScreen);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  listContent: {
    flexGrow: 1,
    paddingBottom: 80,
  },
  header: {
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    ...typography.title,
    marginBottom: 8,
  },
  headerStats: {
    flexDirection: 'row',
    gap: 16,
  },
  statsText: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  orderItem: {
    backgroundColor: colors.surface,
    marginHorizontal: 16,
    marginVertical: 8,
    padding: 16,
    borderRadius: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  orderNumber: {
    ...typography.subtitle,
    fontWeight: '600',
  },
  orderContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderInfo: {
    flex: 1,
  },
  customerName: {
    ...typography.body,
    color: colors.text,
    marginBottom: 4,
  },
  orderTime: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  orderStats: {
    alignItems: 'flex-end',
  },
  orderStatus: {
    ...typography.caption,
    fontWeight: '600',
    marginBottom: 4,
  },
  orderTotal: {
    ...typography.subtitle,
    fontWeight: '600',
    color: colors.text,
  },
  orderNotes: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 8,
    fontStyle: 'italic',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 100,
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
    paddingHorizontal: 40,
  },
  fab: {
    position: 'absolute',
    bottom: 20,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
});
