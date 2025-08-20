import React, { memo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { formatDistanceToNow } from 'date-fns';
import { Badge } from '../ui';
import { colors, spacing, typography, borderRadius, shadows } from '../../constants/designSystem';
import { shadowStyles, textStyles } from '../../styles/sharedStyles';

interface OrderListItemProps {
  order: {
    id: string;
    orderNumber: string;
    customerName: string;
    tableNumber?: string;
    items: number;
    totalAmount: number;
    status: string;
    orderType: string;
    createdAt: Date;
    priority?: string;
  };
  onPress: (orderId: string) => void;
}

// Memoized order list item for performance
export const OrderListItem = memo<OrderListItemProps>(({ order, onPress }) => {
  const getStatusColor = (status: string) => {
    const statusColors: Record<string, string> = {
      pending: colors.warning.base,
      preparing: colors.info.base,
      ready: colors.success.base,
      served: colors.primary.base,
      completed: colors.text.secondary,
      cancelled: colors.error.base,
    };
    return statusColors[status] || colors.text.secondary;
  };

  const getPriorityIcon = (priority?: string) => {
    if (!priority || priority === 'normal') return null;
    
    const iconProps = {
      low: { name: 'chevron-down', color: colors.info.base },
      high: { name: 'chevron-up', color: colors.warning.base },
      urgent: { name: 'chevron-double-up', color: colors.error.base },
    };
    
    const icon = iconProps[priority as keyof typeof iconProps];
    if (!icon) return null;
    
    return (
      <MaterialCommunityIcons
        name={icon.name as any}
        size={20}
        color={icon.color}
      />
    );
  };

  const getOrderTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      'dine-in': 'silverware-fork-knife',
      'takeout': 'package-variant',
      'delivery': 'bike-fast',
    };
    return icons[type] || 'food';
  };

  return (
    <TouchableOpacity
      style={[styles.container, shadowStyles.sm]}
      onPress={() => onPress(order.id)}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.orderNumber}>{order.orderNumber}</Text>
          {order.priority && getPriorityIcon(order.priority)}
        </View>
        <Badge
          label={order.status.replace('_', ' ')}
          color={getStatusColor(order.status)}
          size="small"
        />
      </View>

      <View style={styles.content}>
        <View style={styles.customerInfo}>
          <MaterialCommunityIcons
            name="account"
            size={16}
            color={colors.text.secondary}
          />
          <Text style={styles.customerName} numberOfLines={1}>
            {order.customerName}
          </Text>
          {order.tableNumber && (
            <>
              <Text style={styles.separator}>•</Text>
              <MaterialCommunityIcons
                name="table-chair"
                size={16}
                color={colors.text.secondary}
              />
              <Text style={styles.tableNumber}>{order.tableNumber}</Text>
            </>
          )}
        </View>

        <View style={styles.orderInfo}>
          <View style={styles.orderMeta}>
            <MaterialCommunityIcons
              name={getOrderTypeIcon(order.orderType)}
              size={16}
              color={colors.text.secondary}
            />
            <Text style={styles.metaText}>
              {order.orderType.replace('-', ' ')}
            </Text>
            <Text style={styles.separator}>•</Text>
            <Text style={styles.metaText}>{order.items} items</Text>
          </View>
          <Text style={styles.totalAmount}>${order.totalAmount.toFixed(2)}</Text>
        </View>
      </View>

      <View style={styles.footer}>
        <Text style={styles.timeAgo}>
          {formatDistanceToNow(order.createdAt, { addSuffix: true })}
        </Text>
        <MaterialCommunityIcons
          name="chevron-right"
          size={20}
          color={colors.text.tertiary}
        />
      </View>
    </TouchableOpacity>
  );
}, (prevProps, nextProps) => {
  // Custom comparison for better performance
  return (
    prevProps.order.id === nextProps.order.id &&
    prevProps.order.status === nextProps.order.status &&
    prevProps.order.priority === nextProps.order.priority
  );
});

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface.primary,
    marginHorizontal: spacing.md,
    marginVertical: spacing.xs,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  orderNumber: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.semibold as any,
    color: colors.text.primary,
  },
  content: {
    marginBottom: spacing.sm,
  },
  customerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.xs,
    gap: spacing.xs,
  },
  customerName: {
    fontSize: typography.sizes.md,
    color: colors.text.primary,
    flex: 1,
  },
  tableNumber: {
    fontSize: typography.sizes.md,
    color: colors.text.secondary,
  },
  separator: {
    fontSize: typography.sizes.md,
    color: colors.text.tertiary,
    marginHorizontal: spacing.xs,
  },
  orderInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  metaText: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    textTransform: 'capitalize' as any,
  },
  totalAmount: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.semibold as any,
    color: colors.text.primary,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: colors.border.light,
    paddingTop: spacing.sm,
  },
  timeAgo: {
    fontSize: typography.sizes.sm,
    color: colors.text.tertiary,
  },
});

OrderListItem.displayName = 'OrderListItem';