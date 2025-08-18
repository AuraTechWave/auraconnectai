import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import {
  Text,
  Card,
  Searchbar,
  FAB,
  useTheme,
  IconButton,
  Chip,
  SegmentedButtons,
  Badge,
  ProgressBar,
  Portal,
  Modal,
  Button,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { InventoryStackParamList } from '@navigation/InventoryNavigator';
import { useQuery } from '@tanstack/react-query';
import { useOfflineSync } from '@hooks/useOfflineSync';

type NavigationProp = NativeStackNavigationProp<InventoryStackParamList>;

interface InventoryItem {
  id: number;
  name: string;
  sku: string;
  barcode: string;
  category: string;
  currentStock: number;
  minStock: number;
  maxStock: number;
  unit: string;
  lastRestocked: string;
  supplier: string;
  cost: number;
  status: 'in_stock' | 'low_stock' | 'out_of_stock';
  expiryDate?: string;
}

interface Category {
  id: string;
  name: string;
  itemCount: number;
}

export const InventoryListScreen: React.FC = () => {
  const theme = useTheme();
  const navigation = useNavigation<NavigationProp>();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [refreshing, setRefreshing] = useState(false);
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const { syncData } = useOfflineSync();

  // Fetch inventory data
  const { data: inventoryItems = [], refetch } = useQuery<InventoryItem[]>({
    queryKey: ['inventory', 'items'],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return [
        {
          id: 1,
          name: 'Premium Coffee Beans',
          sku: 'COF-001',
          barcode: '1234567890123',
          category: 'Beverages',
          currentStock: 45,
          minStock: 20,
          maxStock: 100,
          unit: 'kg',
          lastRestocked: '2024-01-15',
          supplier: 'Coffee Suppliers Inc.',
          cost: 25.99,
          status: 'in_stock' as const,
        },
        {
          id: 2,
          name: 'Organic Milk',
          sku: 'DAI-001',
          barcode: '2345678901234',
          category: 'Dairy',
          currentStock: 8,
          minStock: 15,
          maxStock: 50,
          unit: 'liters',
          lastRestocked: '2024-01-18',
          supplier: 'Local Dairy Farm',
          cost: 3.99,
          status: 'low_stock' as const,
          expiryDate: '2024-01-25',
        },
        {
          id: 3,
          name: 'Fresh Tomatoes',
          sku: 'VEG-005',
          barcode: '3456789012345',
          category: 'Produce',
          currentStock: 0,
          minStock: 10,
          maxStock: 30,
          unit: 'kg',
          lastRestocked: '2024-01-10',
          supplier: 'Fresh Produce Co.',
          cost: 2.49,
          status: 'out_of_stock' as const,
        },
      ];
    },
  });

  // Fetch categories
  const { data: categories = [] } = useQuery<Category[]>({
    queryKey: ['inventory', 'categories'],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return [
        { id: 'all', name: 'All Items', itemCount: inventoryItems.length },
        { id: 'beverages', name: 'Beverages', itemCount: 12 },
        { id: 'dairy', name: 'Dairy', itemCount: 8 },
        { id: 'produce', name: 'Produce', itemCount: 15 },
        { id: 'meat', name: 'Meat & Seafood', itemCount: 10 },
        { id: 'dry_goods', name: 'Dry Goods', itemCount: 20 },
      ];
    },
  });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    await syncData('inventory');
    setRefreshing(false);
  }, [refetch, syncData]);

  const filteredItems = useMemo(() => {
    let items = inventoryItems;

    // Filter by search query
    if (searchQuery) {
      items = items.filter(
        item =>
          item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.sku.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.barcode.includes(searchQuery),
      );
    }

    // Filter by category
    if (selectedCategory !== 'all') {
      items = items.filter(
        item => item.category.toLowerCase() === selectedCategory,
      );
    }

    // Filter by status
    if (filterStatus !== 'all') {
      items = items.filter(item => item.status === filterStatus);
    }

    return items;
  }, [inventoryItems, searchQuery, selectedCategory, filterStatus]);

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

  const getStockPercentage = (current: number, max: number) => {
    return max > 0 ? current / max : 0;
  };

  const renderInventoryItem = ({ item }: { item: InventoryItem }) => {
    const stockPercentage = getStockPercentage(item.currentStock, item.maxStock);
    const isLowStock = item.currentStock <= item.minStock;
    const isExpiringSoon = item.expiryDate && 
      new Date(item.expiryDate) <= new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);

    return (
      <TouchableOpacity
        onPress={() => navigation.navigate('InventoryItem', { itemId: item.id })}>
        <Card style={styles.itemCard}>
          <Card.Content>
            <View style={styles.itemHeader}>
              <View style={styles.itemInfo}>
                <Text variant="titleMedium" style={styles.itemName}>
                  {item.name}
                </Text>
                <Text variant="bodySmall" style={styles.itemSku}>
                  SKU: {item.sku} • {item.barcode}
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
                {item.status.replace(/_/g, ' ')}
              </Chip>
            </View>

            <View style={styles.stockInfo}>
              <View style={styles.stockNumbers}>
                <Text variant="bodyMedium">
                  Stock: {item.currentStock} {item.unit}
                </Text>
                <Text variant="bodySmall" style={styles.stockRange}>
                  Min: {item.minStock} • Max: {item.maxStock}
                </Text>
              </View>
              <ProgressBar
                progress={stockPercentage}
                color={getStatusColor(item.status)}
                style={styles.stockProgress}
              />
            </View>

            <View style={styles.itemFooter}>
              <Text variant="bodySmall" style={styles.supplier}>
                {item.supplier}
              </Text>
              <View style={styles.badges}>
                {isLowStock && (
                  <Badge style={[styles.badge, styles.lowStockBadge]}>
                    Low Stock
                  </Badge>
                )}
                {isExpiringSoon && (
                  <Badge style={[styles.badge, styles.expiryBadge]}>
                    Expiring Soon
                  </Badge>
                )}
              </View>
            </View>
          </Card.Content>
        </Card>
      </TouchableOpacity>
    );
  };

  const renderFilterModal = () => (
    <Portal>
      <Modal
        visible={showFilterModal}
        onDismiss={() => setShowFilterModal(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Filter Inventory
        </Text>
        
        <Text variant="titleMedium" style={styles.filterSection}>
          Stock Status
        </Text>
        <SegmentedButtons
          value={filterStatus}
          onValueChange={setFilterStatus}
          buttons={[
            { value: 'all', label: 'All' },
            { value: 'in_stock', label: 'In Stock' },
            { value: 'low_stock', label: 'Low' },
            { value: 'out_of_stock', label: 'Out' },
          ]}
          style={styles.segmentedButtons}
        />

        <View style={styles.modalActions}>
          <Button
            mode="text"
            onPress={() => {
              setFilterStatus('all');
              setShowFilterModal(false);
            }}>
            Clear
          </Button>
          <Button
            mode="contained"
            onPress={() => setShowFilterModal(false)}>
            Apply
          </Button>
        </View>
      </Modal>
    </Portal>
  );

  const handleBarcodeScan = (mode: 'add' | 'search' | 'count') => {
    navigation.navigate('BarcodeScanner', { mode });
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          Inventory
        </Text>
        <View style={styles.headerActions}>
          <IconButton
            icon="filter"
            size={24}
            onPress={() => setShowFilterModal(true)}
          />
          <IconButton
            icon="barcode-scan"
            size={24}
            onPress={() => handleBarcodeScan('search')}
          />
          <IconButton
            icon="clipboard-list"
            size={24}
            onPress={() => navigation.navigate('InventoryCount', {})}
          />
        </View>
      </View>

      <Searchbar
        placeholder="Search by name, SKU, or barcode..."
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={styles.searchBar}
        iconColor={theme.colors.primary}
      />

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.categoriesContainer}>
        {categories.map(category => (
          <Chip
            key={category.id}
            mode={selectedCategory === category.id ? 'flat' : 'outlined'}
            onPress={() => setSelectedCategory(category.id)}
            style={[
              styles.categoryChip,
              selectedCategory === category.id && styles.selectedCategoryChip,
            ]}>
            {category.name} ({category.itemCount})
          </Chip>
        ))}
      </ScrollView>

      <FlatList
        data={filteredItems}
        renderItem={renderInventoryItem}
        keyExtractor={item => item.id.toString()}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={[theme.colors.primary]}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text variant="bodyLarge" style={styles.emptyText}>
              No inventory items found
            </Text>
          </View>
        }
      />

      {renderFilterModal()}

      <FAB
        icon="plus"
        style={[styles.fab, { backgroundColor: theme.colors.primary }]}
        onPress={() => handleBarcodeScan('add')}
        label="Add Item"
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
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  title: {
    fontWeight: 'bold',
  },
  headerActions: {
    flexDirection: 'row',
  },
  searchBar: {
    marginHorizontal: 16,
    marginBottom: 8,
    elevation: 0,
    backgroundColor: 'white',
  },
  categoriesContainer: {
    paddingHorizontal: 16,
    marginBottom: 8,
    maxHeight: 40,
  },
  categoryChip: {
    marginRight: 8,
  },
  selectedCategoryChip: {
    backgroundColor: '#e0f2fe',
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
  itemSku: {
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
  stockInfo: {
    marginBottom: 12,
  },
  stockNumbers: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  stockRange: {
    color: '#64748b',
  },
  stockProgress: {
    height: 6,
    borderRadius: 3,
  },
  itemFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  supplier: {
    color: '#64748b',
  },
  badges: {
    flexDirection: 'row',
    gap: 8,
  },
  badge: {
    paddingHorizontal: 8,
  },
  lowStockBadge: {
    backgroundColor: '#fef3c7',
  },
  expiryBadge: {
    backgroundColor: '#fee2e2',
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
  filterSection: {
    marginBottom: 12,
  },
  segmentedButtons: {
    marginBottom: 24,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
  },
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
  },
});