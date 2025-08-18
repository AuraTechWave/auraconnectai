import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import {
  Text,
  Card,
  useTheme,
  IconButton,
  Chip,
  Button,
  ProgressBar,
  Divider,
  DataTable,
  FAB,
  Portal,
  Modal,
  TextInput,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { InventoryStackParamList } from '@navigation/InventoryNavigator';
import { useQuery, useMutation } from '@tanstack/react-query';
import { format, parseISO, addDays } from 'date-fns';

type RouteProps = RouteProp<InventoryStackParamList, 'InventoryItem'>;

interface InventoryItemDetails {
  id: number;
  name: string;
  sku: string;
  barcode: string;
  category: string;
  description: string;
  currentStock: number;
  minStock: number;
  maxStock: number;
  reorderPoint: number;
  unit: string;
  cost: number;
  retailPrice: number;
  supplier: {
    name: string;
    contact: string;
    leadTime: number;
  };
  status: 'in_stock' | 'low_stock' | 'out_of_stock';
  lastRestocked: string;
  lastCounted: string;
  expiryDate?: string;
  location: string;
  notes?: string;
  stockHistory: Array<{
    date: string;
    type: 'restock' | 'sale' | 'adjustment' | 'count';
    quantity: number;
    balance: number;
    user: string;
    notes?: string;
  }>;
}

export const InventoryItemScreen: React.FC = () => {
  const theme = useTheme();
  const route = useRoute<RouteProps>();
  const navigation = useNavigation();
  const { itemId } = route.params;
  
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [adjustmentType, setAdjustmentType] = useState<'add' | 'remove'>('add');
  const [adjustmentQuantity, setAdjustmentQuantity] = useState('');
  const [adjustmentNotes, setAdjustmentNotes] = useState('');

  // Fetch item details
  const { data: itemDetails, refetch } = useQuery<InventoryItemDetails>({
    queryKey: ['inventory', 'item', itemId],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return {
        id: itemId,
        name: 'Premium Coffee Beans',
        sku: 'COF-001',
        barcode: '1234567890123',
        category: 'Beverages',
        description: 'High-quality arabica coffee beans from Colombia',
        currentStock: 45,
        minStock: 20,
        maxStock: 100,
        reorderPoint: 25,
        unit: 'kg',
        cost: 25.99,
        retailPrice: 39.99,
        supplier: {
          name: 'Coffee Suppliers Inc.',
          contact: '+1 234-567-8900',
          leadTime: 5,
        },
        status: 'in_stock',
        lastRestocked: '2024-01-15',
        lastCounted: '2024-01-18',
        location: 'Aisle 3, Shelf B',
        notes: 'Store in cool, dry place. Rotate stock weekly.',
        stockHistory: [
          {
            date: '2024-01-18T10:30:00',
            type: 'count',
            quantity: 0,
            balance: 45,
            user: 'John Doe',
            notes: 'Monthly inventory count',
          },
          {
            date: '2024-01-15T14:20:00',
            type: 'restock',
            quantity: 50,
            balance: 45,
            user: 'Jane Smith',
          },
          {
            date: '2024-01-14T16:45:00',
            type: 'sale',
            quantity: -5,
            balance: -5,
            user: 'System',
          },
        ],
      };
    },
  });

  // Mutation for stock adjustment
  const adjustStockMutation = useMutation({
    mutationFn: async (adjustment: {
      itemId: number;
      quantity: number;
      notes: string;
    }) => {
      // TODO: Implement API call
      return adjustment;
    },
    onSuccess: () => {
      refetch();
      setShowAdjustModal(false);
      setAdjustmentQuantity('');
      setAdjustmentNotes('');
      Alert.alert('Success', 'Stock adjusted successfully');
    },
  });

  if (!itemDetails) {
    return null;
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'in_stock':
        return theme.colors.primary;
      case 'low_stock':
        return theme.colors.tertiary;
      case 'out_of_stock':
        return theme.colors.error;
      default:
        return theme.colors.outline;
    }
  };

  const getStockPercentage = () => {
    return itemDetails.maxStock > 0 
      ? itemDetails.currentStock / itemDetails.maxStock 
      : 0;
  };

  const getHistoryIcon = (type: string) => {
    switch (type) {
      case 'restock':
        return 'package-variant';
      case 'sale':
        return 'cart-arrow-down';
      case 'adjustment':
        return 'pencil';
      case 'count':
        return 'clipboard-list';
      default:
        return 'circle';
    }
  };

  const getHistoryColor = (type: string) => {
    switch (type) {
      case 'restock':
        return theme.colors.primary;
      case 'sale':
        return theme.colors.secondary;
      case 'adjustment':
        return theme.colors.tertiary;
      case 'count':
        return theme.colors.outline;
      default:
        return theme.colors.outline;
    }
  };

  const handleStockAdjustment = () => {
    const quantity = parseInt(adjustmentQuantity);
    if (isNaN(quantity) || quantity <= 0) {
      Alert.alert('Error', 'Please enter a valid quantity');
      return;
    }

    const finalQuantity = adjustmentType === 'remove' ? -quantity : quantity;
    
    adjustStockMutation.mutate({
      itemId: itemDetails.id,
      quantity: finalQuantity,
      notes: adjustmentNotes,
    });
  };

  const renderAdjustmentModal = () => (
    <Portal>
      <Modal
        visible={showAdjustModal}
        onDismiss={() => setShowAdjustModal(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Adjust Stock
        </Text>

        <View style={styles.adjustmentTypeContainer}>
          <Chip
            mode={adjustmentType === 'add' ? 'flat' : 'outlined'}
            onPress={() => setAdjustmentType('add')}
            style={styles.adjustmentChip}>
            Add Stock
          </Chip>
          <Chip
            mode={adjustmentType === 'remove' ? 'flat' : 'outlined'}
            onPress={() => setAdjustmentType('remove')}
            style={styles.adjustmentChip}>
            Remove Stock
          </Chip>
        </View>

        <TextInput
          label="Quantity"
          value={adjustmentQuantity}
          onChangeText={setAdjustmentQuantity}
          keyboardType="numeric"
          mode="outlined"
          style={styles.input}
          right={<TextInput.Affix text={itemDetails.unit} />}
        />

        <TextInput
          label="Notes (optional)"
          value={adjustmentNotes}
          onChangeText={setAdjustmentNotes}
          mode="outlined"
          multiline
          numberOfLines={3}
          style={styles.input}
        />

        <View style={styles.modalActions}>
          <Button mode="outlined" onPress={() => setShowAdjustModal(false)}>
            Cancel
          </Button>
          <Button mode="contained" onPress={handleStockAdjustment}>
            Confirm
          </Button>
        </View>
      </Modal>
    </Portal>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <IconButton
            icon="arrow-left"
            size={24}
            onPress={() => navigation.goBack()}
          />
          <IconButton
            icon="pencil"
            size={24}
            onPress={() => navigation.navigate('EditInventoryItem' as any, { itemId })}
          />
        </View>

        <View style={styles.itemHeader}>
          <Text variant="headlineSmall" style={styles.itemName}>
            {itemDetails.name}
          </Text>
          <Text variant="bodyLarge" style={styles.itemSku}>
            SKU: {itemDetails.sku} • {itemDetails.barcode}
          </Text>
          <Chip
            mode="flat"
            textStyle={styles.statusChipText}
            style={[
              styles.statusChip,
              { backgroundColor: getStatusColor(itemDetails.status) + '20' },
            ]}>
            {itemDetails.status.replace(/_/g, ' ')}
          </Chip>
        </View>

        <Card style={styles.stockCard}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Stock Information
            </Text>
            
            <View style={styles.stockNumbers}>
              <View style={styles.stockItem}>
                <Text variant="bodyMedium" style={styles.stockLabel}>
                  Current Stock
                </Text>
                <Text variant="headlineSmall" style={styles.stockValue}>
                  {itemDetails.currentStock} {itemDetails.unit}
                </Text>
              </View>
              <View style={styles.stockItem}>
                <Text variant="bodyMedium" style={styles.stockLabel}>
                  Reorder Point
                </Text>
                <Text variant="headlineSmall" style={styles.stockValue}>
                  {itemDetails.reorderPoint} {itemDetails.unit}
                </Text>
              </View>
            </View>

            <ProgressBar
              progress={getStockPercentage()}
              color={getStatusColor(itemDetails.status)}
              style={styles.stockProgress}
            />

            <View style={styles.stockLimits}>
              <Text variant="bodySmall">Min: {itemDetails.minStock}</Text>
              <Text variant="bodySmall">Max: {itemDetails.maxStock}</Text>
            </View>
          </Card.Content>
        </Card>

        <Card style={styles.infoCard}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Details
            </Text>
            
            <View style={styles.detailRow}>
              <Text variant="bodyMedium" style={styles.detailLabel}>
                Category
              </Text>
              <Text variant="bodyMedium">{itemDetails.category}</Text>
            </View>
            
            <Divider style={styles.divider} />
            
            <View style={styles.detailRow}>
              <Text variant="bodyMedium" style={styles.detailLabel}>
                Location
              </Text>
              <Text variant="bodyMedium">{itemDetails.location}</Text>
            </View>
            
            <Divider style={styles.divider} />
            
            <View style={styles.detailRow}>
              <Text variant="bodyMedium" style={styles.detailLabel}>
                Cost Price
              </Text>
              <Text variant="bodyMedium">${itemDetails.cost.toFixed(2)}</Text>
            </View>
            
            <Divider style={styles.divider} />
            
            <View style={styles.detailRow}>
              <Text variant="bodyMedium" style={styles.detailLabel}>
                Retail Price
              </Text>
              <Text variant="bodyMedium">${itemDetails.retailPrice.toFixed(2)}</Text>
            </View>
            
            <Divider style={styles.divider} />
            
            <View style={styles.detailRow}>
              <Text variant="bodyMedium" style={styles.detailLabel}>
                Last Restocked
              </Text>
              <Text variant="bodyMedium">
                {format(parseISO(itemDetails.lastRestocked), 'MMM d, yyyy')}
              </Text>
            </View>
            
            <Divider style={styles.divider} />
            
            <View style={styles.detailRow}>
              <Text variant="bodyMedium" style={styles.detailLabel}>
                Last Counted
              </Text>
              <Text variant="bodyMedium">
                {format(parseISO(itemDetails.lastCounted), 'MMM d, yyyy')}
              </Text>
            </View>

            {itemDetails.notes && (
              <>
                <Divider style={styles.divider} />
                <Text variant="bodySmall" style={styles.notes}>
                  {itemDetails.notes}
                </Text>
              </>
            )}
          </Card.Content>
        </Card>

        <Card style={styles.infoCard}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Supplier Information
            </Text>
            
            <View style={styles.supplierInfo}>
              <Text variant="bodyMedium">{itemDetails.supplier.name}</Text>
              <Text variant="bodySmall" style={styles.supplierContact}>
                {itemDetails.supplier.contact}
              </Text>
              <Text variant="bodySmall" style={styles.leadTime}>
                Lead time: {itemDetails.supplier.leadTime} days
              </Text>
            </View>

            <Button
              mode="outlined"
              onPress={() => Alert.alert('Reorder', 'Reorder functionality coming soon')}
              style={styles.reorderButton}>
              Create Reorder
            </Button>
          </Card.Content>
        </Card>

        <Card style={styles.infoCard}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Stock History
            </Text>
            
            {itemDetails.stockHistory.map((history, index) => (
              <View key={index}>
                <View style={styles.historyItem}>
                  <IconButton
                    icon={getHistoryIcon(history.type)}
                    size={20}
                    iconColor={getHistoryColor(history.type)}
                  />
                  <View style={styles.historyContent}>
                    <View style={styles.historyHeader}>
                      <Text variant="bodyMedium" style={styles.historyType}>
                        {history.type.charAt(0).toUpperCase() + history.type.slice(1)}
                      </Text>
                      <Text
                        variant="bodyLarge"
                        style={[
                          styles.historyQuantity,
                          { color: history.quantity > 0 ? theme.colors.primary : theme.colors.error },
                        ]}>
                        {history.quantity > 0 ? '+' : ''}{history.quantity} {itemDetails.unit}
                      </Text>
                    </View>
                    <Text variant="bodySmall" style={styles.historyMeta}>
                      {format(parseISO(history.date), 'MMM d, yyyy h:mm a')} • {history.user}
                    </Text>
                    {history.notes && (
                      <Text variant="bodySmall" style={styles.historyNotes}>
                        {history.notes}
                      </Text>
                    )}
                  </View>
                </View>
                {index < itemDetails.stockHistory.length - 1 && (
                  <Divider style={styles.historyDivider} />
                )}
              </View>
            ))}
          </Card.Content>
        </Card>

        <View style={styles.actions}>
          <Button
            mode="outlined"
            onPress={() => navigation.navigate('InventoryCount', { sessionId: 'new' })}
            style={styles.actionButton}>
            Count Stock
          </Button>
          <Button
            mode="contained"
            onPress={() => setShowAdjustModal(true)}
            style={styles.actionButton}>
            Adjust Stock
          </Button>
        </View>
      </ScrollView>

      {renderAdjustmentModal()}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
  },
  itemHeader: {
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  itemName: {
    fontWeight: '600',
    textAlign: 'center',
  },
  itemSku: {
    color: '#64748b',
    marginTop: 4,
  },
  statusChip: {
    marginTop: 12,
  },
  statusChipText: {
    fontSize: 12,
    textTransform: 'capitalize',
  },
  stockCard: {
    marginHorizontal: 16,
    marginBottom: 12,
  },
  sectionTitle: {
    fontWeight: '600',
    marginBottom: 16,
  },
  stockNumbers: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 16,
  },
  stockItem: {
    alignItems: 'center',
  },
  stockLabel: {
    color: '#64748b',
    marginBottom: 4,
  },
  stockValue: {
    fontWeight: '600',
  },
  stockProgress: {
    height: 8,
    borderRadius: 4,
    marginBottom: 8,
  },
  stockLimits: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  infoCard: {
    marginHorizontal: 16,
    marginBottom: 12,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  detailLabel: {
    color: '#64748b',
  },
  divider: {
    marginVertical: 8,
  },
  notes: {
    color: '#64748b',
    fontStyle: 'italic',
    marginTop: 8,
  },
  supplierInfo: {
    marginBottom: 16,
  },
  supplierContact: {
    color: '#64748b',
    marginTop: 4,
  },
  leadTime: {
    color: '#94a3b8',
    marginTop: 4,
  },
  reorderButton: {
    marginTop: 8,
  },
  historyItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginVertical: 8,
  },
  historyContent: {
    flex: 1,
    marginLeft: -8,
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  historyType: {
    fontWeight: '500',
  },
  historyQuantity: {
    fontWeight: '600',
  },
  historyMeta: {
    color: '#64748b',
    marginTop: 2,
  },
  historyNotes: {
    color: '#94a3b8',
    marginTop: 4,
  },
  historyDivider: {
    marginLeft: 40,
  },
  actions: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 24,
    gap: 12,
  },
  actionButton: {
    flex: 1,
  },
  modalContent: {
    backgroundColor: 'white',
    padding: 24,
    margin: 20,
    borderRadius: 8,
  },
  modalTitle: {
    marginBottom: 24,
  },
  adjustmentTypeContainer: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  adjustmentChip: {
    flex: 1,
  },
  input: {
    marginBottom: 16,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 8,
  },
});