import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { withObservables } from '@nozbe/with-observables';
import { Q } from '@nozbe/watermelondb';

import database from '@database';
import MenuItem from '@database/models/MenuItem';
import { useOfflineSync } from '@hooks/useOfflineSync';
import { colors, typography } from '@theme';
import { showToast } from '@utils/toast';
import { generateId } from '@utils/helpers';

interface OrderItemData {
  menuItemId: string;
  menuItem: MenuItem;
  quantity: number;
  notes?: string;
}

interface CreateOrderScreenProps {
  menuItems: MenuItem[];
  navigation: any;
}

const CreateOrderScreen: React.FC<CreateOrderScreenProps> = ({
  menuItems,
  navigation,
}) => {
  const [customerName, setCustomerName] = useState('');
  const [tableNumber, setTableNumber] = useState('');
  const [orderItems, setOrderItems] = useState<OrderItemData[]>([]);
  const [notes, setNotes] = useState('');
  const { isOffline, queueOperation } = useOfflineSync();

  const calculateTotal = useCallback(() => {
    return orderItems.reduce(
      (total, item) => total + item.menuItem.price * item.quantity,
      0,
    );
  }, [orderItems]);

  const handleAddItem = useCallback((menuItem: MenuItem) => {
    setOrderItems(prev => {
      const existingIndex = prev.findIndex(
        item => item.menuItemId === menuItem.id,
      );
      
      if (existingIndex >= 0) {
        const updated = [...prev];
        updated[existingIndex].quantity++;
        return updated;
      }
      
      return [...prev, {
        menuItemId: menuItem.id,
        menuItem,
        quantity: 1,
      }];
    });
  }, []);

  const handleUpdateQuantity = useCallback(
    (menuItemId: string, quantity: number) => {
      if (quantity <= 0) {
        setOrderItems(prev => prev.filter(item => item.menuItemId !== menuItemId));
      } else {
        setOrderItems(prev =>
          prev.map(item =>
            item.menuItemId === menuItemId ? { ...item, quantity } : item,
          ),
        );
      }
    },
    [],
  );

  const handleCreateOrder = useCallback(async () => {
    if (orderItems.length === 0) {
      Alert.alert('Error', 'Please add at least one item to the order');
      return;
    }

    try {
      const ordersCollection = database.collections.get('orders');
      const orderItemsCollection = database.collections.get('order_items');
      
      await database.write(async () => {
        // Create order
        const order = await ordersCollection.create(order => {
          order.orderNumber = generateId();
          order.customerName = customerName || 'Walk-in Customer';
          order.tableNumber = tableNumber;
          order.status = 'pending';
          order.totalAmount = calculateTotal();
          order.subtotal = calculateTotal();
          order.tax = 0;
          order.discount = 0;
          order.paymentStatus = 'pending';
          order.notes = notes;
          order.syncStatus = 'pending';
          order.lastModified = Date.now();
        });

        // Create order items
        for (const item of orderItems) {
          await orderItemsCollection.create(orderItem => {
            orderItem.orderId = order.id;
            orderItem.menuItemId = item.menuItemId;
            orderItem.menuItemName = item.menuItem.name;
            orderItem.quantity = item.quantity;
            orderItem.unitPrice = item.menuItem.price;
            orderItem.totalPrice = item.menuItem.price * item.quantity;
            orderItem.notes = item.notes;
            orderItem.syncStatus = 'pending';
            orderItem.lastModified = Date.now();
          });
        }

        // Queue sync operation if online
        if (!isOffline) {
          await queueOperation({
            collection: 'orders',
            operation: 'create',
            recordId: order.id,
            priority: 'high',
          });
        }
      });

      showToast(
        'success',
        'Order Created',
        isOffline ? 'Order saved offline' : 'Order created successfully',
      );
      
      navigation.goBack();
    } catch (error) {
      console.error('Failed to create order:', error);
      Alert.alert('Error', 'Failed to create order. Please try again.');
    }
  }, [orderItems, customerName, tableNumber, notes, calculateTotal, isOffline, queueOperation, navigation]);

  const renderMenuItem = (menuItem: MenuItem) => {
    const orderItem = orderItems.find(item => item.menuItemId === menuItem.id);
    const quantity = orderItem?.quantity || 0;

    return (
      <View key={menuItem.id} style={styles.menuItem}>
        <View style={styles.menuItemInfo}>
          <Text style={styles.menuItemName}>{menuItem.name}</Text>
          <Text style={styles.menuItemPrice}>${menuItem.price.toFixed(2)}</Text>
        </View>
        
        <View style={styles.quantityControls}>
          <TouchableOpacity
            style={styles.quantityButton}
            onPress={() => handleUpdateQuantity(menuItem.id, quantity - 1)}
            disabled={quantity === 0}
          >
            <Icon
              name="minus"
              size={20}
              color={quantity === 0 ? colors.textSecondary : colors.text}
            />
          </TouchableOpacity>
          
          <Text style={styles.quantity}>{quantity}</Text>
          
          <TouchableOpacity
            style={styles.quantityButton}
            onPress={() => handleAddItem(menuItem)}
          >
            <Icon name="plus" size={20} color={colors.text} />
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const renderOrderSummary = () => {
    if (orderItems.length === 0) return null;

    return (
      <View style={styles.orderSummary}>
        <Text style={styles.sectionTitle}>Order Summary</Text>
        {orderItems.map(item => (
          <View key={item.menuItemId} style={styles.summaryItem}>
            <Text style={styles.summaryItemName}>
              {item.quantity}x {item.menuItem.name}
            </Text>
            <Text style={styles.summaryItemPrice}>
              ${(item.menuItem.price * item.quantity).toFixed(2)}
            </Text>
          </View>
        ))}
        <View style={styles.totalRow}>
          <Text style={styles.totalLabel}>Total</Text>
          <Text style={styles.totalAmount}>${calculateTotal().toFixed(2)}</Text>
        </View>
      </View>
    );
  };

  // Group menu items by category
  const menuItemsByCategory = menuItems.reduce((acc, item) => {
    const categoryName = item.categoryName || 'Uncategorized';
    if (!acc[categoryName]) {
      acc[categoryName] = [];
    }
    acc[categoryName].push(item);
    return acc;
  }, {} as Record<string, MenuItem[]>);

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Icon name="arrow-left" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.title}>Create Order</Text>
          <View style={{ width: 24 }} />
        </View>

        {isOffline && (
          <View style={styles.offlineBanner}>
            <Icon name="cloud-off-outline" size={20} color={colors.warning} />
            <Text style={styles.offlineText}>Creating order offline</Text>
          </View>
        )}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Customer Information</Text>
          <TextInput
            style={styles.input}
            placeholder="Customer Name (optional)"
            value={customerName}
            onChangeText={setCustomerName}
            placeholderTextColor={colors.textSecondary}
          />
          <TextInput
            style={styles.input}
            placeholder="Table Number (optional)"
            value={tableNumber}
            onChangeText={setTableNumber}
            placeholderTextColor={colors.textSecondary}
          />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Menu Items</Text>
          {Object.entries(menuItemsByCategory).map(([category, items]) => (
            <View key={category}>
              <Text style={styles.categoryTitle}>{category}</Text>
              {items.map(renderMenuItem)}
            </View>
          ))}
        </View>

        {renderOrderSummary()}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Notes</Text>
          <TextInput
            style={[styles.input, styles.notesInput]}
            placeholder="Add any special instructions..."
            value={notes}
            onChangeText={setNotes}
            placeholderTextColor={colors.textSecondary}
            multiline
            numberOfLines={3}
          />
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity
          style={[styles.createButton, orderItems.length === 0 && styles.disabledButton]}
          onPress={handleCreateOrder}
          disabled={orderItems.length === 0}
        >
          <Text style={styles.createButtonText}>Create Order</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
};

// Enhance component with observable data
const enhance = withObservables([''], () => ({
  menuItems: database.collections
    .get('menu_items')
    .query(
      Q.where('is_active', true),
      Q.where('is_deleted', false),
    )
    .observe(),
}));

export default enhance(CreateOrderScreen);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    ...typography.title,
  },
  offlineBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.warningLight,
    paddingVertical: 8,
    gap: 8,
  },
  offlineText: {
    ...typography.caption,
    color: colors.warning,
    fontWeight: '600',
  },
  section: {
    padding: 16,
  },
  sectionTitle: {
    ...typography.subtitle,
    fontWeight: '600',
    marginBottom: 12,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 12,
    ...typography.body,
    color: colors.text,
  },
  notesInput: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  categoryTitle: {
    ...typography.caption,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    marginTop: 16,
    marginBottom: 8,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 8,
    marginBottom: 8,
  },
  menuItemInfo: {
    flex: 1,
  },
  menuItemName: {
    ...typography.body,
    fontWeight: '500',
    marginBottom: 4,
  },
  menuItemPrice: {
    ...typography.caption,
    color: colors.primary,
  },
  quantityControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  quantityButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  quantity: {
    ...typography.body,
    fontWeight: '600',
    minWidth: 20,
    textAlign: 'center',
  },
  orderSummary: {
    margin: 16,
    padding: 16,
    backgroundColor: colors.surface,
    borderRadius: 8,
  },
  summaryItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  summaryItemName: {
    ...typography.body,
    flex: 1,
  },
  summaryItemPrice: {
    ...typography.body,
    fontWeight: '500',
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  totalLabel: {
    ...typography.subtitle,
    fontWeight: '600',
  },
  totalAmount: {
    ...typography.subtitle,
    fontWeight: '600',
    color: colors.primary,
  },
  footer: {
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  createButton: {
    backgroundColor: colors.primary,
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  disabledButton: {
    backgroundColor: colors.disabled,
  },
  createButtonText: {
    ...typography.button,
    color: colors.white,
    fontWeight: '600',
  },
});