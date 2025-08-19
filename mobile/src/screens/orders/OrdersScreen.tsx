import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { FAB, Searchbar, Chip, SegmentedButtons } from 'react-native-paper';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { format } from 'date-fns';
import {
  Card,
  CardContent,
  Badge,
  Avatar,
  Button,
  colors,
  spacing,
  typography,
  borderRadius,
  shadows,
} from '../../components/ui';

interface Order {
  id: string;
  orderNumber: string;
  customerName: string;
  customerAvatar?: string;
  tableNumber?: string;
  items: Array<{
    name: string;
    quantity: number;
    price: number;
  }>;
  status: 'pending' | 'preparing' | 'ready' | 'served' | 'completed' | 'cancelled';
  orderType: 'dine-in' | 'takeout' | 'delivery';
  totalAmount: number;
  createdAt: Date;
  estimatedTime?: number;
  notes?: string;
  paymentStatus: 'pending' | 'paid' | 'refunded';
  priority?: 'low' | 'normal' | 'high' | 'urgent';
}

export default function OrdersScreen() {
  const navigation = useNavigation<any>();
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');

  // Mock data - replace with actual data fetching
  const [orders] = useState<Order[]>([
    {
      id: '1',
      orderNumber: '#ORD-001',
      customerName: 'John Doe',
      tableNumber: 'T-12',
      items: [
        { name: 'Margherita Pizza', quantity: 1, price: 12.99 },
        { name: 'Caesar Salad', quantity: 2, price: 8.99 },
        { name: 'Coke', quantity: 2, price: 2.99 },
      ],
      status: 'preparing',
      orderType: 'dine-in',
      totalAmount: 36.95,
      createdAt: new Date(),
      estimatedTime: 20,
      paymentStatus: 'pending',
      priority: 'normal',
    },
    {
      id: '2',
      orderNumber: '#ORD-002',
      customerName: 'Jane Smith',
      items: [
        { name: 'Burger Deluxe', quantity: 2, price: 15.99 },
        { name: 'French Fries', quantity: 2, price: 4.99 },
      ],
      status: 'ready',
      orderType: 'takeout',
      totalAmount: 41.96,
      createdAt: new Date(Date.now() - 1800000),
      estimatedTime: 5,
      paymentStatus: 'paid',
      priority: 'high',
    },
    {
      id: '3',
      orderNumber: '#ORD-003',
      customerName: 'Mike Johnson',
      tableNumber: 'T-05',
      items: [
        { name: 'Pasta Carbonara', quantity: 1, price: 14.99 },
        { name: 'Tiramisu', quantity: 1, price: 6.99 },
      ],
      status: 'pending',
      orderType: 'dine-in',
      totalAmount: 21.98,
      createdAt: new Date(Date.now() - 300000),
      paymentStatus: 'pending',
      priority: 'urgent',
      notes: 'Allergic to nuts',
    },
  ]);

  const statusColors: Record<string, string> = {
    pending: colors.warning[500],
    preparing: colors.primary[500],
    ready: colors.success[500],
    served: colors.secondary[500],
    completed: colors.neutral[500],
    cancelled: colors.error[500],
  };

  const priorityColors: Record<string, string> = {
    low: colors.neutral[400],
    normal: colors.primary[400],
    high: colors.warning[500],
    urgent: colors.error[500],
  };

  const orderTypeIcons: Record<string, string> = {
    'dine-in': 'silverware-fork-knife',
    'takeout': 'bag-personal',
    'delivery': 'bike-fast',
  };

  const filteredOrders = useMemo(() => {
    return orders.filter(order => {
      const matchesSearch = 
        order.orderNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
        order.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        order.tableNumber?.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesStatus = selectedStatus === 'all' || order.status === selectedStatus;
      const matchesType = selectedType === 'all' || order.orderType === selectedType;
      
      return matchesSearch && matchesStatus && matchesType;
    });
  }, [orders, searchQuery, selectedStatus, selectedType]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    // Simulate refresh
    setTimeout(() => setRefreshing(false), 1500);
  }, []);

  const getTimeAgo = (date: Date): string => {
    const minutes = Math.floor((Date.now() - date.getTime()) / 60000);
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return format(date, 'MMM dd');
  };

  const renderOrderCard = ({ item }: { item: Order }) => (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={() => navigation.navigate('OrderDetails', { orderId: item.id })}
    >
      <Card variant="elevated" style={styles.orderCard}>
        <View style={styles.orderHeader}>
          <View style={styles.orderHeaderLeft}>
            <View style={styles.orderNumberRow}>
              <Text style={styles.orderNumber}>{item.orderNumber}</Text>
              {item.priority && item.priority !== 'normal' && (
                <Badge
                  label={item.priority.toUpperCase()}
                  variant="error"
                  size="small"
                  style={{ marginLeft: spacing.xs }}
                />
              )}
            </View>
            <Text style={styles.orderTime}>{getTimeAgo(item.createdAt)}</Text>
          </View>
          <View style={styles.orderHeaderRight}>
            <Badge
              label={item.status.replace('_', ' ').toUpperCase()}
              style={{ backgroundColor: statusColors[item.status] }}
              textStyle={{ color: colors.text.inverse }}
            />
          </View>
        </View>

        <CardContent style={styles.orderContent}>
          <View style={styles.customerRow}>
            <Avatar
              name={item.customerName}
              size="small"
              source={item.customerAvatar ? { uri: item.customerAvatar } : undefined}
            />
            <View style={styles.customerInfo}>
              <Text style={styles.customerName}>{item.customerName}</Text>
              <View style={styles.orderMeta}>
                <MaterialCommunityIcons
                  name={orderTypeIcons[item.orderType]}
                  size={14}
                  color={colors.text.secondary}
                />
                <Text style={styles.orderMetaText}>
                  {item.orderType === 'dine-in' && item.tableNumber
                    ? item.tableNumber
                    : item.orderType.replace('-', ' ')}
                </Text>
                {item.estimatedTime && (
                  <>
                    <Text style={styles.orderMetaDivider}>•</Text>
                    <MaterialCommunityIcons
                      name="clock-outline"
                      size={14}
                      color={colors.text.secondary}
                    />
                    <Text style={styles.orderMetaText}>{item.estimatedTime} min</Text>
                  </>
                )}
              </View>
            </View>
          </View>

          <View style={styles.itemsList}>
            {item.items.slice(0, 2).map((orderItem, index) => (
              <Text key={index} style={styles.itemText}>
                {orderItem.quantity}x {orderItem.name}
              </Text>
            ))}
            {item.items.length > 2 && (
              <Text style={styles.moreItems}>
                +{item.items.length - 2} more items
              </Text>
            )}
          </View>

          {item.notes && (
            <View style={styles.notesContainer}>
              <MaterialCommunityIcons
                name="note-text-outline"
                size={14}
                color={colors.warning[600]}
              />
              <Text style={styles.notesText}>{item.notes}</Text>
            </View>
          )}

          <View style={styles.orderFooter}>
            <View style={styles.totalAmount}>
              <Text style={styles.totalLabel}>Total</Text>
              <Text style={styles.totalValue}>${item.totalAmount.toFixed(2)}</Text>
            </View>
            <View style={styles.paymentStatus}>
              <MaterialCommunityIcons
                name={item.paymentStatus === 'paid' ? 'check-circle' : 'clock-outline'}
                size={16}
                color={item.paymentStatus === 'paid' ? colors.success[500] : colors.warning[500]}
              />
              <Text
                style={[
                  styles.paymentText,
                  {
                    color: item.paymentStatus === 'paid' ? colors.success[600] : colors.warning[600],
                  },
                ]}
              >
                {item.paymentStatus === 'paid' ? 'Paid' : 'Payment Pending'}
              </Text>
            </View>
          </View>
        </CardContent>
      </Card>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Searchbar
          placeholder="Search orders..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
          icon="magnify"
        />
        
        <View style={styles.filterRow}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filtersContainer}
          >
            <Chip
              selected={selectedStatus === 'all'}
              onPress={() => setSelectedStatus('all')}
              style={styles.filterChip}
            >
              All Orders
            </Chip>
            <Chip
              selected={selectedStatus === 'pending'}
              onPress={() => setSelectedStatus('pending')}
              style={styles.filterChip}
            >
              Pending
            </Chip>
            <Chip
              selected={selectedStatus === 'preparing'}
              onPress={() => setSelectedStatus('preparing')}
              style={styles.filterChip}
            >
              Preparing
            </Chip>
            <Chip
              selected={selectedStatus === 'ready'}
              onPress={() => setSelectedStatus('ready')}
              style={styles.filterChip}
            >
              Ready
            </Chip>
            <Chip
              selected={selectedStatus === 'completed'}
              onPress={() => setSelectedStatus('completed')}
              style={styles.filterChip}
            >
              Completed
            </Chip>
          </ScrollView>
        </View>

        <SegmentedButtons
          value={selectedType}
          onValueChange={setSelectedType}
          buttons={[
            { value: 'all', label: 'All', icon: 'format-list-bulleted' },
            { value: 'dine-in', label: 'Dine-in', icon: 'silverware' },
            { value: 'takeout', label: 'Takeout', icon: 'bag-personal' },
            { value: 'delivery', label: 'Delivery', icon: 'bike-fast' },
          ]}
          style={styles.segmentedButtons}
        />
      </View>

      <FlatList
        data={filteredOrders}
        renderItem={renderOrderCard}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <MaterialCommunityIcons
              name="clipboard-text-outline"
              size={64}
              color={colors.text.tertiary}
            />
            <Text style={styles.emptyText}>No orders found</Text>
            <Text style={styles.emptySubtext}>
              {searchQuery ? 'Try adjusting your search' : 'New orders will appear here'}
            </Text>
          </View>
        }
      />

      <FAB
        icon="plus"
        style={styles.fab}
        onPress={() => navigation.navigate('CreateOrder')}
        label="New Order"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.secondary,
  },
  header: {
    backgroundColor: colors.background.primary,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
    ...shadows.sm,
  },
  searchBar: {
    marginBottom: spacing.sm,
    elevation: 0,
  },
  filterRow: {
    marginBottom: spacing.sm,
  },
  filtersContainer: {
    paddingVertical: spacing.xs,
  },
  filterChip: {
    marginRight: spacing.xs,
  },
  segmentedButtons: {
    marginTop: spacing.xs,
  },
  listContent: {
    padding: spacing.md,
  },
  orderCard: {
    marginBottom: spacing.md,
    backgroundColor: colors.background.primary,
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.light,
  },
  orderHeaderLeft: {
    flex: 1,
  },
  orderHeaderRight: {
    marginLeft: spacing.sm,
  },
  orderNumberRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  orderNumber: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
  },
  orderTime: {
    fontSize: typography.fontSize.caption,
    color: colors.text.tertiary,
    marginTop: 2,
  },
  orderContent: {
    padding: 0,
  },
  customerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  customerInfo: {
    marginLeft: spacing.sm,
    flex: 1,
  },
  customerName: {
    fontSize: typography.fontSize.bodyLarge,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
  },
  orderMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 2,
  },
  orderMetaText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginLeft: 4,
  },
  orderMetaDivider: {
    fontSize: typography.fontSize.caption,
    color: colors.text.tertiary,
    marginHorizontal: spacing.xs,
  },
  itemsList: {
    marginBottom: spacing.sm,
  },
  itemText: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginBottom: 2,
  },
  moreItems: {
    fontSize: typography.fontSize.body,
    color: colors.text.tertiary,
    fontStyle: 'italic',
  },
  notesContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.warning[50],
    padding: spacing.xs,
    borderRadius: borderRadius.sm,
    marginBottom: spacing.sm,
  },
  notesText: {
    fontSize: typography.fontSize.caption,
    color: colors.warning[700],
    marginLeft: spacing.xs,
    flex: 1,
  },
  orderFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border.light,
  },
  totalAmount: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  totalLabel: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginRight: spacing.xs,
  },
  totalValue: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
  },
  paymentStatus: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  paymentText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.medium,
    marginLeft: 4,
  },
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xxxl,
  },
  emptyText: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    marginTop: spacing.md,
  },
  emptySubtext: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginTop: spacing.xs,
  },
  fab: {
    position: 'absolute',
    right: spacing.md,
    bottom: spacing.md,
    backgroundColor: colors.primary[500],
  },
});