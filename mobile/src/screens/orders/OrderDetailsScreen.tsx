import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Animated,
  Share,
  Alert,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import { Divider, Menu, IconButton } from 'react-native-paper';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { format } from 'date-fns';
import {
  Card,
  CardContent,
  Badge,
  Avatar,
  Button,
  Input,
  colors,
  spacing,
  typography,
  borderRadius,
  shadows,
  animations,
} from '../../components/ui';

interface OrderItem {
  id: string;
  name: string;
  quantity: number;
  price: number;
  notes?: string;
  modifiers?: string[];
  status?: 'pending' | 'preparing' | 'ready' | 'served';
}

interface OrderDetails {
  id: string;
  orderNumber: string;
  customerName: string;
  customerPhone?: string;
  customerEmail?: string;
  customerAvatar?: string;
  tableNumber?: string;
  items: OrderItem[];
  status: 'pending' | 'preparing' | 'ready' | 'served' | 'completed' | 'cancelled';
  orderType: 'dine-in' | 'takeout' | 'delivery';
  totalAmount: number;
  subtotal: number;
  tax: number;
  discount?: number;
  tip?: number;
  createdAt: Date;
  updatedAt: Date;
  estimatedTime?: number;
  actualTime?: number;
  notes?: string;
  paymentStatus: 'pending' | 'paid' | 'refunded';
  paymentMethod?: string;
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  assignedTo?: string;
  deliveryAddress?: string;
  deliveryInstructions?: string;
}

const OrderDetailsScreen: React.FC = () => {
  const route = useRoute();
  const navigation = useNavigation<any>();
  const [menuVisible, setMenuVisible] = useState(false);
  const [notesModalVisible, setNotesModalVisible] = useState(false);
  const [additionalNotes, setAdditionalNotes] = useState('');
  const fadeAnim = useRef(new Animated.Value(0)).current;

  // Type guard for orderId - support both string and number for backward compatibility
  const orderId = route.params?.orderId;
  const orderIdString = typeof orderId === 'number' ? orderId.toString() : orderId;
  
  // Check if orderId is missing (null or undefined, but not 0)
  const isOrderIdMissing = orderId === null || orderId === undefined;
  
  React.useEffect(() => {
    if (isOrderIdMissing) {
      Alert.alert('Error', 'Order ID is missing', [
        { text: 'OK', onPress: () => navigation.goBack() }
      ]);
    }
  }, [isOrderIdMissing, navigation]);
  
  if (isOrderIdMissing) {
    return null;
  }

  // Mock data - replace with actual data fetching based on orderIdString
  // TODO: Use orderIdString for API call: fetchOrder(orderIdString)
  const [order] = useState<OrderDetails>({
    id: '1',
    orderNumber: '#ORD-001',
    customerName: 'John Doe',
    customerPhone: '+1 234 567 8900',
    customerEmail: 'john.doe@example.com',
    tableNumber: 'T-12',
    items: [
      {
        id: '1',
        name: 'Margherita Pizza',
        quantity: 1,
        price: 12.99,
        modifiers: ['Extra cheese', 'Thin crust'],
        status: 'preparing',
      },
      {
        id: '2',
        name: 'Caesar Salad',
        quantity: 2,
        price: 8.99,
        notes: 'No croutons',
        status: 'ready',
      },
      {
        id: '3',
        name: 'Coke',
        quantity: 2,
        price: 2.99,
        status: 'served',
      },
    ],
    status: 'preparing',
    orderType: 'dine-in',
    subtotal: 30.96,
    tax: 3.71,
    tip: 2.28,
    totalAmount: 36.95,
    createdAt: new Date(Date.now() - 1200000),
    updatedAt: new Date(Date.now() - 600000),
    estimatedTime: 20,
    actualTime: 15,
    paymentStatus: 'pending',
    priority: 'normal',
    assignedTo: 'Chef Maria',
    notes: 'Customer is celebrating birthday',
  });

  React.useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: animations.duration.normal,
      useNativeDriver: true,
    }).start();
  }, [fadeAnim]);

  const statusColors: Record<string, string> = {
    pending: colors.warning[500],
    preparing: colors.primary[500],
    ready: colors.success[500],
    served: colors.secondary[500],
    completed: colors.neutral[500],
    cancelled: colors.error[500],
  };

  const itemStatusColors: Record<string, string> = {
    pending: colors.neutral[400],
    preparing: colors.primary[400],
    ready: colors.success[400],
    served: colors.secondary[400],
  };

  const handleStatusUpdate = (newStatus: string) => {
    Alert.alert(
      'Update Status',
      `Change order status to ${newStatus}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Update',
          onPress: () => {
            // Update order status
            console.log('Updating status to:', newStatus);
          },
        },
      ]
    );
  };

  const handleShare = async () => {
    try {
      await Share.share({
        message: `Order ${order.orderNumber}\nCustomer: ${order.customerName}\nTotal: $${order.totalAmount.toFixed(2)}`,
      });
    } catch (error) {
      console.error('Error sharing:', error);
    }
  };

  const handlePrint = () => {
    Alert.alert('Print Order', 'Order sent to kitchen printer');
  };

  const handleCancel = () => {
    Alert.alert(
      'Cancel Order',
      'Are you sure you want to cancel this order?',
      [
        { text: 'No', style: 'cancel' },
        {
          text: 'Yes, Cancel',
          style: 'destructive',
          onPress: () => {
            // Cancel order
            navigation.goBack();
          },
        },
      ]
    );
  };

  const renderOrderItem = (item: OrderItem) => (
    <View key={item.id} style={styles.itemCard}>
      <View style={styles.itemHeader}>
        <View style={styles.itemInfo}>
          <View style={styles.itemNameRow}>
            <Text style={styles.itemQuantity}>{item.quantity}x</Text>
            <Text style={styles.itemName}>{item.name}</Text>
          </View>
          {item.modifiers && item.modifiers.length > 0 && (
            <Text style={styles.itemModifiers}>
              {item.modifiers.join(', ')}
            </Text>
          )}
          {item.notes && (
            <View style={styles.itemNotes}>
              <MaterialCommunityIcons
                name="note-outline"
                size={12}
                color={colors.warning[600]}
              />
              <Text style={styles.itemNotesText}>{item.notes}</Text>
            </View>
          )}
        </View>
        <View style={styles.itemRight}>
          <Text style={styles.itemPrice}>${(item.price * item.quantity).toFixed(2)}</Text>
          {item.status && (
            <Badge
              label={item.status}
              size="small"
              style={{
                backgroundColor: itemStatusColors[item.status],
                marginTop: spacing.xxs,
              }}
            />
          )}
        </View>
      </View>
    </View>
  );

  return (
    <Animated.View style={[styles.container, { opacity: fadeAnim }]}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Header Card */}
        <Card variant="elevated" style={styles.headerCard}>
          <CardContent>
            <View style={styles.headerRow}>
              <View style={styles.headerLeft}>
                <Text style={styles.orderNumber}>{order.orderNumber}</Text>
                <Text style={styles.orderDate}>
                  {format(order.createdAt, 'MMM dd, yyyy • hh:mm a')}
                </Text>
              </View>
              <View style={styles.headerRight}>
                <Badge
                  label={order.status.toUpperCase()}
                  style={{ backgroundColor: statusColors[order.status] }}
                  textStyle={{ color: colors.text.inverse }}
                />
                <Menu
                  visible={menuVisible}
                  onDismiss={() => setMenuVisible(false)}
                  anchor={
                    <IconButton
                      icon="dots-vertical"
                      size={24}
                      onPress={() => setMenuVisible(true)}
                    />
                  }
                >
                  <Menu.Item onPress={handleShare} title="Share" leadingIcon="share" />
                  <Menu.Item onPress={handlePrint} title="Print" leadingIcon="printer" />
                  <Divider />
                  <Menu.Item
                    onPress={handleCancel}
                    title="Cancel Order"
                    leadingIcon="close-circle"
                    titleStyle={{ color: colors.error[500] }}
                  />
                </Menu>
              </View>
            </View>

            {/* Quick Actions */}
            <View style={styles.quickActions}>
              <Button
                title="Mark Ready"
                variant="primary"
                size="small"
                icon="check"
                onPress={() => handleStatusUpdate('ready')}
                style={styles.actionButton}
              />
              <Button
                title="Add Note"
                variant="outline"
                size="small"
                icon="note-plus"
                onPress={() => setNotesModalVisible(true)}
                style={styles.actionButton}
              />
              <Button
                title="Print Bill"
                variant="outline"
                size="small"
                icon="receipt"
                onPress={handlePrint}
                style={styles.actionButton}
              />
            </View>
          </CardContent>
        </Card>

        {/* Customer Information */}
        <Card variant="outlined" style={styles.section}>
          <CardContent>
            <Text style={styles.sectionTitle}>Customer Information</Text>
            <View style={styles.customerInfo}>
              <Avatar
                name={order.customerName}
                size="medium"
                source={order.customerAvatar ? { uri: order.customerAvatar } : undefined}
              />
              <View style={styles.customerDetails}>
                <Text style={styles.customerName}>{order.customerName}</Text>
                {order.customerPhone && (
                  <TouchableOpacity style={styles.contactRow}>
                    <MaterialCommunityIcons
                      name="phone"
                      size={14}
                      color={colors.text.secondary}
                    />
                    <Text style={styles.contactText}>{order.customerPhone}</Text>
                  </TouchableOpacity>
                )}
                {order.customerEmail && (
                  <TouchableOpacity style={styles.contactRow}>
                    <MaterialCommunityIcons
                      name="email"
                      size={14}
                      color={colors.text.secondary}
                    />
                    <Text style={styles.contactText}>{order.customerEmail}</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>

            {/* Order Meta */}
            <View style={styles.metaGrid}>
              <View style={styles.metaItem}>
                <MaterialCommunityIcons
                  name={order.orderType === 'dine-in' ? 'silverware' : 'bag-personal'}
                  size={20}
                  color={colors.text.secondary}
                />
                <Text style={styles.metaLabel}>Type</Text>
                <Text style={styles.metaValue}>
                  {order.orderType === 'dine-in' && order.tableNumber
                    ? order.tableNumber
                    : order.orderType}
                </Text>
              </View>
              <View style={styles.metaItem}>
                <MaterialCommunityIcons
                  name="clock-outline"
                  size={20}
                  color={colors.text.secondary}
                />
                <Text style={styles.metaLabel}>Est. Time</Text>
                <Text style={styles.metaValue}>{order.estimatedTime} min</Text>
              </View>
              <View style={styles.metaItem}>
                <MaterialCommunityIcons
                  name="account-tie"
                  size={20}
                  color={colors.text.secondary}
                />
                <Text style={styles.metaLabel}>Assigned</Text>
                <Text style={styles.metaValue}>{order.assignedTo || 'Unassigned'}</Text>
              </View>
            </View>
          </CardContent>
        </Card>

        {/* Order Items */}
        <Card variant="outlined" style={styles.section}>
          <CardContent>
            <Text style={styles.sectionTitle}>Order Items</Text>
            {order.items.map(renderOrderItem)}
          </CardContent>
        </Card>

        {/* Special Instructions */}
        {order.notes && (
          <Card variant="filled" style={styles.section}>
            <CardContent>
              <View style={styles.notesHeader}>
                <MaterialCommunityIcons
                  name="information"
                  size={20}
                  color={colors.warning[600]}
                />
                <Text style={styles.notesTitle}>Special Instructions</Text>
              </View>
              <Text style={styles.notesContent}>{order.notes}</Text>
            </CardContent>
          </Card>
        )}

        {/* Payment Summary */}
        <Card variant="elevated" style={styles.section}>
          <CardContent>
            <Text style={styles.sectionTitle}>Payment Summary</Text>
            
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Subtotal</Text>
              <Text style={styles.summaryValue}>${order.subtotal.toFixed(2)}</Text>
            </View>
            
            {order.discount && (
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Discount</Text>
                <Text style={[styles.summaryValue, { color: colors.success[600] }]}>
                  -${order.discount.toFixed(2)}
                </Text>
              </View>
            )}
            
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Tax</Text>
              <Text style={styles.summaryValue}>${order.tax.toFixed(2)}</Text>
            </View>
            
            {order.tip && (
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Tip</Text>
                <Text style={styles.summaryValue}>${order.tip.toFixed(2)}</Text>
              </View>
            )}
            
            <Divider style={styles.divider} />
            
            <View style={styles.summaryRow}>
              <Text style={styles.totalLabel}>Total</Text>
              <Text style={styles.totalValue}>${order.totalAmount.toFixed(2)}</Text>
            </View>
            
            <View style={[styles.summaryRow, { marginTop: spacing.sm }]}>
              <View style={styles.paymentStatusContainer}>
                <MaterialCommunityIcons
                  name={order.paymentStatus === 'paid' ? 'check-circle' : 'clock-outline'}
                  size={20}
                  color={order.paymentStatus === 'paid' ? colors.success[500] : colors.warning[500]}
                />
                <Text
                  style={[
                    styles.paymentStatus,
                    {
                      color: order.paymentStatus === 'paid'
                        ? colors.success[600]
                        : colors.warning[600],
                    },
                  ]}
                >
                  {order.paymentStatus === 'paid' ? 'Paid' : 'Payment Pending'}
                </Text>
              </View>
              {order.paymentStatus === 'pending' && (
                <Button
                  title="Process Payment"
                  variant="primary"
                  size="small"
                  icon="credit-card"
                  onPress={() => navigation.navigate('ProcessPayment', { orderId: orderIdString })}
                />
              )}
            </View>
          </CardContent>
        </Card>

        {/* Timeline */}
        <Card variant="outlined" style={[styles.section, { marginBottom: spacing.xxl }]}>
          <CardContent>
            <Text style={styles.sectionTitle}>Order Timeline</Text>
            <View style={styles.timeline}>
              <View style={styles.timelineItem}>
                <View style={[styles.timelineDot, { backgroundColor: colors.success[500] }]} />
                <View style={styles.timelineContent}>
                  <Text style={styles.timelineTime}>
                    {format(order.createdAt, 'hh:mm a')}
                  </Text>
                  <Text style={styles.timelineText}>Order placed</Text>
                </View>
              </View>
              <View style={styles.timelineItem}>
                <View style={[styles.timelineDot, { backgroundColor: colors.primary[500] }]} />
                <View style={styles.timelineContent}>
                  <Text style={styles.timelineTime}>
                    {format(new Date(order.createdAt.getTime() + 300000), 'hh:mm a')}
                  </Text>
                  <Text style={styles.timelineText}>Order confirmed</Text>
                </View>
              </View>
              {order.status === 'preparing' && (
                <View style={styles.timelineItem}>
                  <View style={[styles.timelineDot, { backgroundColor: colors.warning[500] }]} />
                  <View style={styles.timelineContent}>
                    <Text style={styles.timelineTime}>In progress</Text>
                    <Text style={styles.timelineText}>Preparing order</Text>
                  </View>
                </View>
              )}
            </View>
          </CardContent>
        </Card>
      </ScrollView>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.secondary,
  },
  headerCard: {
    margin: spacing.md,
    backgroundColor: colors.background.primary,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  headerLeft: {
    flex: 1,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  orderNumber: {
    fontSize: typography.fontSize.h3,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  orderDate: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginTop: spacing.xxs,
  },
  quickActions: {
    flexDirection: 'row',
    marginTop: spacing.md,
    gap: spacing.xs,
  },
  actionButton: {
    flex: 1,
  },
  section: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
    marginBottom: spacing.md,
  },
  customerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  customerDetails: {
    marginLeft: spacing.md,
    flex: 1,
  },
  customerName: {
    fontSize: typography.fontSize.bodyLarge,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    marginBottom: spacing.xxs,
  },
  contactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xxs,
  },
  contactText: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginLeft: spacing.xs,
  },
  metaGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border.light,
  },
  metaItem: {
    alignItems: 'center',
  },
  metaLabel: {
    fontSize: typography.fontSize.caption,
    color: colors.text.tertiary,
    marginTop: spacing.xxs,
  },
  metaValue: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    marginTop: 2,
  },
  itemCard: {
    backgroundColor: colors.background.tertiary,
    padding: spacing.sm,
    borderRadius: borderRadius.md,
    marginBottom: spacing.xs,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  itemInfo: {
    flex: 1,
  },
  itemNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  itemQuantity: {
    fontSize: typography.fontSize.bodyLarge,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
    marginRight: spacing.xs,
  },
  itemName: {
    fontSize: typography.fontSize.bodyLarge,
    color: colors.text.primary,
    flex: 1,
  },
  itemModifiers: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginTop: 2,
  },
  itemNotes: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xxs,
  },
  itemNotesText: {
    fontSize: typography.fontSize.caption,
    color: colors.warning[600],
    marginLeft: 4,
    flex: 1,
  },
  itemRight: {
    alignItems: 'flex-end',
  },
  itemPrice: {
    fontSize: typography.fontSize.bodyLarge,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
  },
  notesHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  notesTitle: {
    fontSize: typography.fontSize.bodyLarge,
    fontWeight: typography.fontWeight.medium,
    color: colors.warning[700],
    marginLeft: spacing.xs,
  },
  notesContent: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    lineHeight: typography.lineHeight.body * 1.4,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  summaryLabel: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
  },
  summaryValue: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
  },
  divider: {
    marginVertical: spacing.sm,
  },
  totalLabel: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
  },
  totalValue: {
    fontSize: typography.fontSize.h3,
    fontWeight: typography.fontWeight.bold,
    color: colors.primary[600],
  },
  paymentStatusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  paymentStatus: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.medium,
    marginLeft: spacing.xs,
  },
  timeline: {
    paddingLeft: spacing.md,
  },
  timelineItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
  },
  timelineDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginTop: 4,
  },
  timelineContent: {
    marginLeft: spacing.md,
    flex: 1,
  },
  timelineTime: {
    fontSize: typography.fontSize.caption,
    color: colors.text.tertiary,
  },
  timelineText: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    marginTop: 2,
  },
});

export default OrderDetailsScreen;