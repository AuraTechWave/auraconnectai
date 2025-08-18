import React, { useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
} from 'react-native';
import {
  Text,
  Card,
  Searchbar,
  FAB,
  useTheme,
  IconButton,
  Chip,
  TextInput,
  Button,
  ProgressBar,
  Portal,
  Modal,
  Badge,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { InventoryStackParamList } from '@navigation/InventoryNavigator';
import { useQuery, useMutation } from '@tanstack/react-query';
import { format } from 'date-fns';

type RouteProps = RouteProp<InventoryStackParamList, 'InventoryCount'>;

interface CountItem {
  id: number;
  name: string;
  sku: string;
  barcode: string;
  category: string;
  unit: string;
  systemStock: number;
  countedStock?: number;
  variance?: number;
  status: 'pending' | 'counted' | 'discrepancy';
  location: string;
}

interface CountSession {
  id: string;
  date: string;
  status: 'in_progress' | 'completed' | 'cancelled';
  itemsTotal: number;
  itemsCounted: number;
  discrepancies: number;
  createdBy: string;
}

export const InventoryCountScreen: React.FC = () => {
  const theme = useTheme();
  const route = useRoute<RouteProps>();
  const navigation = useNavigation();
  const { sessionId } = route.params;
  
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'pending' | 'counted' | 'discrepancy'>('all');
  const [selectedItem, setSelectedItem] = useState<CountItem | null>(null);
  const [showCountModal, setShowCountModal] = useState(false);
  const [countValue, setCountValue] = useState('');
  const [showSummaryModal, setShowSummaryModal] = useState(false);

  // Fetch or create count session
  const { data: session } = useQuery<CountSession>({
    queryKey: ['inventory', 'count', 'session', sessionId],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return {
        id: sessionId || 'new-session',
        date: new Date().toISOString(),
        status: 'in_progress',
        itemsTotal: 25,
        itemsCounted: 10,
        discrepancies: 3,
        createdBy: 'John Doe',
      };
    },
  });

  // Fetch items to count
  const { data: countItems = [], refetch } = useQuery<CountItem[]>({
    queryKey: ['inventory', 'count', 'items'],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return [
        {
          id: 1,
          name: 'Premium Coffee Beans',
          sku: 'COF-001',
          barcode: '1234567890123',
          category: 'Beverages',
          unit: 'kg',
          systemStock: 45,
          countedStock: 43,
          variance: -2,
          status: 'discrepancy',
          location: 'Aisle 3, Shelf B',
        },
        {
          id: 2,
          name: 'Organic Milk',
          sku: 'DAI-001',
          barcode: '2345678901234',
          category: 'Dairy',
          unit: 'liters',
          systemStock: 8,
          countedStock: 8,
          variance: 0,
          status: 'counted',
          location: 'Cooler 1',
        },
        {
          id: 3,
          name: 'Fresh Tomatoes',
          sku: 'VEG-005',
          barcode: '3456789012345',
          category: 'Produce',
          unit: 'kg',
          systemStock: 10,
          status: 'pending',
          location: 'Produce Section',
        },
      ];
    },
  });

  // Mutation for submitting count
  const submitCountMutation = useMutation({
    mutationFn: async (data: { itemId: number; count: number }) => {
      // TODO: Implement API call
      return data;
    },
    onSuccess: () => {
      refetch();
      setShowCountModal(false);
      setCountValue('');
      setSelectedItem(null);
    },
  });

  // Mutation for completing count session
  const completeSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      // TODO: Implement API call
      return sessionId;
    },
    onSuccess: () => {
      Alert.alert(
        'Count Completed',
        'Inventory count has been completed successfully.',
        [{ text: 'OK', onPress: () => navigation.goBack() }],
      );
    },
  });

  const filteredItems = useCallback(() => {
    let items = countItems;

    if (searchQuery) {
      items = items.filter(
        item =>
          item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.sku.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.barcode.includes(searchQuery),
      );
    }

    if (filterStatus !== 'all') {
      items = items.filter(item => item.status === filterStatus);
    }

    return items;
  }, [countItems, searchQuery, filterStatus]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'counted':
        return theme.colors.primary;
      case 'discrepancy':
        return theme.colors.error;
      case 'pending':
        return theme.colors.outline;
      default:
        return theme.colors.outline;
    }
  };

  const getProgressPercentage = () => {
    if (!session || session.itemsTotal === 0) return 0;
    return session.itemsCounted / session.itemsTotal;
  };

  const handleCount = (item: CountItem) => {
    setSelectedItem(item);
    setCountValue(item.countedStock?.toString() || '');
    setShowCountModal(true);
  };

  const submitCount = () => {
    const count = parseInt(countValue);
    if (isNaN(count) || count < 0) {
      Alert.alert('Error', 'Please enter a valid count');
      return;
    }

    if (selectedItem) {
      submitCountMutation.mutate({ itemId: selectedItem.id, count });
    }
  };

  const handleBarcodeScan = () => {
    navigation.navigate('BarcodeScanner', { mode: 'count' });
  };

  const handleCompleteSession = () => {
    const pendingItems = countItems.filter(item => item.status === 'pending');
    
    if (pendingItems.length > 0) {
      Alert.alert(
        'Incomplete Count',
        `There are still ${pendingItems.length} items pending count. Are you sure you want to complete the session?`,
        [
          { text: 'Cancel', style: 'cancel' },
          { 
            text: 'Complete Anyway', 
            onPress: () => {
              if (session) {
                completeSessionMutation.mutate(session.id);
              }
            },
          },
        ],
      );
    } else {
      setShowSummaryModal(true);
    }
  };

  const renderCountItem = ({ item }: { item: CountItem }) => {
    const hasDiscrepancy = item.status === 'discrepancy';
    
    return (
      <TouchableOpacity onPress={() => handleCount(item)}>
        <Card style={styles.itemCard}>
          <Card.Content>
            <View style={styles.itemHeader}>
              <View style={styles.itemInfo}>
                <Text variant="titleMedium" style={styles.itemName}>
                  {item.name}
                </Text>
                <Text variant="bodySmall" style={styles.itemMeta}>
                  {item.sku} • {item.location}
                </Text>
              </View>
              <Chip
                mode="flat"
                compact
                textStyle={styles.statusChipText}
                style={[
                  styles.statusChip,
                  { backgroundColor: getStatusColor(item.status) + '20' },
                ]}>
                {item.status}
              </Chip>
            </View>

            <View style={styles.countInfo}>
              <View style={styles.countItem}>
                <Text variant="bodySmall" style={styles.countLabel}>
                  System Stock
                </Text>
                <Text variant="bodyLarge" style={styles.countValue}>
                  {item.systemStock} {item.unit}
                </Text>
              </View>
              
              {item.status !== 'pending' && (
                <>
                  <View style={styles.countItem}>
                    <Text variant="bodySmall" style={styles.countLabel}>
                      Counted
                    </Text>
                    <Text variant="bodyLarge" style={styles.countValue}>
                      {item.countedStock} {item.unit}
                    </Text>
                  </View>
                  
                  <View style={styles.countItem}>
                    <Text variant="bodySmall" style={styles.countLabel}>
                      Variance
                    </Text>
                    <Text
                      variant="bodyLarge"
                      style={[
                        styles.countValue,
                        { color: hasDiscrepancy ? theme.colors.error : theme.colors.primary },
                      ]}>
                      {item.variance! > 0 ? '+' : ''}{item.variance} {item.unit}
                    </Text>
                  </View>
                </>
              )}
            </View>
          </Card.Content>
        </Card>
      </TouchableOpacity>
    );
  };

  const renderCountModal = () => (
    <Portal>
      <Modal
        visible={showCountModal}
        onDismiss={() => setShowCountModal(false)}
        contentContainerStyle={styles.modalContent}>
        {selectedItem && (
          <>
            <Text variant="headlineSmall" style={styles.modalTitle}>
              Count Item
            </Text>
            
            <Card style={styles.modalItemCard}>
              <Card.Content>
                <Text variant="titleMedium">{selectedItem.name}</Text>
                <Text variant="bodySmall" style={styles.modalItemMeta}>
                  {selectedItem.sku} • {selectedItem.location}
                </Text>
                <Text variant="bodyMedium" style={styles.systemStock}>
                  System Stock: {selectedItem.systemStock} {selectedItem.unit}
                </Text>
              </Card.Content>
            </Card>

            <TextInput
              label="Physical Count"
              value={countValue}
              onChangeText={setCountValue}
              keyboardType="numeric"
              mode="outlined"
              style={styles.countInput}
              right={<TextInput.Affix text={selectedItem.unit} />}
              autoFocus
            />

            <View style={styles.modalActions}>
              <Button mode="outlined" onPress={() => setShowCountModal(false)}>
                Cancel
              </Button>
              <Button mode="contained" onPress={submitCount}>
                Submit Count
              </Button>
            </View>
          </>
        )}
      </Modal>
    </Portal>
  );

  const renderSummaryModal = () => (
    <Portal>
      <Modal
        visible={showSummaryModal}
        onDismiss={() => setShowSummaryModal(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Count Summary
        </Text>
        
        {session && (
          <View style={styles.summaryContent}>
            <View style={styles.summaryRow}>
              <Text variant="bodyMedium">Total Items:</Text>
              <Text variant="bodyMedium" style={styles.summaryValue}>
                {session.itemsTotal}
              </Text>
            </View>
            
            <View style={styles.summaryRow}>
              <Text variant="bodyMedium">Items Counted:</Text>
              <Text variant="bodyMedium" style={styles.summaryValue}>
                {session.itemsCounted}
              </Text>
            </View>
            
            <View style={styles.summaryRow}>
              <Text variant="bodyMedium">Discrepancies:</Text>
              <Text
                variant="bodyMedium"
                style={[
                  styles.summaryValue,
                  { color: session.discrepancies > 0 ? theme.colors.error : theme.colors.primary },
                ]}>
                {session.discrepancies}
              </Text>
            </View>
            
            <View style={styles.summaryRow}>
              <Text variant="bodyMedium">Accuracy:</Text>
              <Text variant="bodyMedium" style={styles.summaryValue}>
                {((session.itemsCounted - session.discrepancies) / session.itemsCounted * 100).toFixed(1)}%
              </Text>
            </View>
          </View>
        )}

        <View style={styles.modalActions}>
          <Button mode="outlined" onPress={() => setShowSummaryModal(false)}>
            Continue Counting
          </Button>
          <Button
            mode="contained"
            onPress={() => {
              setShowSummaryModal(false);
              if (session) {
                completeSessionMutation.mutate(session.id);
              }
            }}>
            Complete Count
          </Button>
        </View>
      </Modal>
    </Portal>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <IconButton
            icon="arrow-left"
            size={24}
            onPress={() => navigation.goBack()}
          />
          <View>
            <Text variant="headlineMedium" style={styles.title}>
              Inventory Count
            </Text>
            {session && (
              <Text variant="bodySmall" style={styles.sessionDate}>
                {format(new Date(session.date), 'MMM d, yyyy h:mm a')}
              </Text>
            )}
          </View>
        </View>
        <IconButton
          icon="barcode-scan"
          size={24}
          onPress={handleBarcodeScan}
        />
      </View>

      {session && (
        <View style={styles.progressSection}>
          <View style={styles.progressHeader}>
            <Text variant="bodyMedium">
              Progress: {session.itemsCounted} / {session.itemsTotal}
            </Text>
            <Text variant="bodyMedium" style={styles.progressPercentage}>
              {(getProgressPercentage() * 100).toFixed(0)}%
            </Text>
          </View>
          <ProgressBar
            progress={getProgressPercentage()}
            color={theme.colors.primary}
            style={styles.progressBar}
          />
          {session.discrepancies > 0 && (
            <View style={styles.discrepancyBadge}>
              <Badge style={styles.badge}>{session.discrepancies}</Badge>
              <Text variant="bodySmall" style={styles.discrepancyText}>
                discrepancies found
              </Text>
            </View>
          )}
        </View>
      )}

      <Searchbar
        placeholder="Search items..."
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={styles.searchBar}
      />

      <View style={styles.filterChips}>
        <Chip
          mode={filterStatus === 'all' ? 'flat' : 'outlined'}
          onPress={() => setFilterStatus('all')}
          style={styles.filterChip}>
          All ({countItems.length})
        </Chip>
        <Chip
          mode={filterStatus === 'pending' ? 'flat' : 'outlined'}
          onPress={() => setFilterStatus('pending')}
          style={styles.filterChip}>
          Pending ({countItems.filter(i => i.status === 'pending').length})
        </Chip>
        <Chip
          mode={filterStatus === 'counted' ? 'flat' : 'outlined'}
          onPress={() => setFilterStatus('counted')}
          style={styles.filterChip}>
          Counted ({countItems.filter(i => i.status === 'counted').length})
        </Chip>
        <Chip
          mode={filterStatus === 'discrepancy' ? 'flat' : 'outlined'}
          onPress={() => setFilterStatus('discrepancy')}
          style={styles.filterChip}>
          Discrepancy ({countItems.filter(i => i.status === 'discrepancy').length})
        </Chip>
      </View>

      <FlatList
        data={filteredItems()}
        renderItem={renderCountItem}
        keyExtractor={item => item.id.toString()}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text variant="bodyLarge" style={styles.emptyText}>
              No items to count
            </Text>
          </View>
        }
      />

      {renderCountModal()}
      {renderSummaryModal()}

      <FAB
        icon="check-all"
        style={[styles.fab, { backgroundColor: theme.colors.primary }]}
        onPress={handleCompleteSession}
        label="Complete Count"
      />
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
    alignItems: 'center',
    paddingRight: 8,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  title: {
    fontWeight: 'bold',
  },
  sessionDate: {
    color: '#64748b',
  },
  progressSection: {
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  progressPercentage: {
    fontWeight: '600',
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
  },
  discrepancyBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  badge: {
    backgroundColor: '#fee2e2',
    marginRight: 8,
  },
  discrepancyText: {
    color: '#64748b',
  },
  searchBar: {
    marginHorizontal: 16,
    marginBottom: 8,
    elevation: 0,
    backgroundColor: 'white',
  },
  filterChips: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    marginBottom: 8,
    gap: 8,
  },
  filterChip: {
    // Chip styles handled by component
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 80,
  },
  itemCard: {
    marginBottom: 12,
    elevation: 2,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  itemInfo: {
    flex: 1,
  },
  itemName: {
    fontWeight: '600',
  },
  itemMeta: {
    color: '#64748b',
    marginTop: 2,
  },
  statusChip: {
    marginLeft: 8,
  },
  statusChipText: {
    fontSize: 11,
    textTransform: 'capitalize',
  },
  countInfo: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  countItem: {
    alignItems: 'center',
  },
  countLabel: {
    color: '#64748b',
    marginBottom: 4,
  },
  countValue: {
    fontWeight: '600',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 48,
  },
  emptyText: {
    color: '#94a3b8',
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
  modalItemCard: {
    marginBottom: 24,
  },
  modalItemMeta: {
    color: '#64748b',
    marginTop: 4,
  },
  systemStock: {
    marginTop: 12,
    fontWeight: '600',
  },
  countInput: {
    marginBottom: 24,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
  },
  summaryContent: {
    marginBottom: 24,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  summaryValue: {
    fontWeight: '600',
  },
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
  },
});