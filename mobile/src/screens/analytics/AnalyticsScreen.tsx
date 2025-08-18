import React, { useState, useMemo } from 'react';
import { View, StyleSheet, ScrollView, Dimensions, TouchableOpacity, Alert } from 'react-native';
import { 
  Text, 
  Card, 
  useTheme, 
  SegmentedButtons,
  IconButton,
  Chip,
  Button,
  Portal,
  Modal,
  List,
  Divider,
  ProgressBar,
  DataTable,
  FAB,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@tanstack/react-query';
import { format, startOfWeek, endOfWeek, startOfMonth, endOfMonth, subDays } from 'date-fns';

const { width: screenWidth } = Dimensions.get('window');

interface SalesData {
  daily: Array<{ date: string; amount: number }>;
  weekly: Array<{ week: string; amount: number }>;
  monthly: Array<{ month: string; amount: number }>;
  topItems: Array<{ name: string; quantity: number; revenue: number }>;
  categoryBreakdown: Array<{ category: string; value: number; percentage: number }>;
  totalSales: number;
  averageOrderValue: number;
  ordersCount: number;
  growth: number;
}

interface StaffPerformance {
  id: number;
  name: string;
  ordersServed: number;
  averageOrderTime: number;
  customerRating: number;
  salesAmount: number;
}

interface InventoryMetrics {
  totalValue: number;
  lowStockItems: number;
  expiringItems: number;
  turnoverRate: number;
  wastageValue: number;
}

export const AnalyticsScreen: React.FC = () => {
  const theme = useTheme();
  const [timeRange, setTimeRange] = useState<'day' | 'week' | 'month'>('week');
  const [selectedMetric, setSelectedMetric] = useState<'sales' | 'orders' | 'customers'>('sales');
  const [showExportModal, setShowExportModal] = useState(false);
  const [expandedSections, setExpandedSections] = useState<string[]>(['overview']);

  // Fetch sales data
  const { data: salesData } = useQuery<SalesData>({
    queryKey: ['analytics', 'sales', timeRange],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return {
        daily: [
          { date: '2024-01-15', amount: 2850 },
          { date: '2024-01-16', amount: 3200 },
          { date: '2024-01-17', amount: 2950 },
          { date: '2024-01-18', amount: 3500 },
          { date: '2024-01-19', amount: 4200 },
          { date: '2024-01-20', amount: 4800 },
          { date: '2024-01-21', amount: 3900 },
        ],
        weekly: [
          { week: 'Week 1', amount: 18500 },
          { week: 'Week 2', amount: 21200 },
          { week: 'Week 3', amount: 19800 },
          { week: 'Week 4', amount: 22500 },
        ],
        monthly: [
          { month: 'Oct', amount: 78000 },
          { month: 'Nov', amount: 82000 },
          { month: 'Dec', amount: 95000 },
          { month: 'Jan', amount: 82000 },
        ],
        topItems: [
          { name: 'Burger Deluxe', quantity: 245, revenue: 3675 },
          { name: 'Caesar Salad', quantity: 189, revenue: 2268 },
          { name: 'Margherita Pizza', quantity: 167, revenue: 2505 },
          { name: 'Grilled Salmon', quantity: 134, revenue: 3350 },
          { name: 'Pasta Carbonara', quantity: 156, revenue: 2340 },
        ],
        categoryBreakdown: [
          { category: 'Main Courses', value: 12500, percentage: 45 },
          { category: 'Appetizers', value: 5500, percentage: 20 },
          { category: 'Beverages', value: 4150, percentage: 15 },
          { category: 'Desserts', value: 3300, percentage: 12 },
          { category: 'Others', value: 2200, percentage: 8 },
        ],
        totalSales: 25400,
        averageOrderValue: 45.50,
        ordersCount: 558,
        growth: 12.5,
      };
    },
  });

  // Fetch staff performance
  const { data: staffPerformance = [] } = useQuery<StaffPerformance[]>({
    queryKey: ['analytics', 'staff', timeRange],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return [
        {
          id: 1,
          name: 'John Doe',
          ordersServed: 145,
          averageOrderTime: 12.5,
          customerRating: 4.8,
          salesAmount: 6580,
        },
        {
          id: 2,
          name: 'Jane Smith',
          ordersServed: 132,
          averageOrderTime: 11.2,
          customerRating: 4.9,
          salesAmount: 5940,
        },
        {
          id: 3,
          name: 'Bob Wilson',
          ordersServed: 98,
          averageOrderTime: 13.8,
          customerRating: 4.5,
          salesAmount: 4410,
        },
      ];
    },
  });

  // Fetch inventory metrics
  const { data: inventoryMetrics } = useQuery<InventoryMetrics>({
    queryKey: ['analytics', 'inventory'],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return {
        totalValue: 45000,
        lowStockItems: 12,
        expiringItems: 5,
        turnoverRate: 3.2,
        wastageValue: 850,
      };
    },
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev =>
      prev.includes(section)
        ? prev.filter(s => s !== section)
        : [...prev, section],
    );
  };

  const getTimeRangeLabel = () => {
    switch (timeRange) {
      case 'day':
        return 'Today';
      case 'week':
        return 'This Week';
      case 'month':
        return 'This Month';
      default:
        return '';
    }
  };

  const renderOverviewCards = () => (
    <View style={styles.overviewGrid}>
      <Card style={styles.overviewCard}>
        <Card.Content>
          <View style={styles.overviewHeader}>
            <IconButton icon="cash" size={20} iconColor={theme.colors.primary} />
            <Text variant="bodySmall" style={styles.overviewLabel}>
              Total Sales
            </Text>
          </View>
          <Text variant="headlineSmall" style={styles.overviewValue}>
            ${salesData?.totalSales.toLocaleString() || '0'}
          </Text>
          {salesData?.growth && (
            <View style={styles.growthContainer}>
              <IconButton
                icon={salesData.growth > 0 ? 'trending-up' : 'trending-down'}
                size={16}
                iconColor={salesData.growth > 0 ? theme.colors.primary : theme.colors.error}
              />
              <Text
                variant="bodySmall"
                style={[
                  styles.growthText,
                  { color: salesData.growth > 0 ? theme.colors.primary : theme.colors.error },
                ]}>
                {Math.abs(salesData.growth)}%
              </Text>
            </View>
          )}
        </Card.Content>
      </Card>

      <Card style={styles.overviewCard}>
        <Card.Content>
          <View style={styles.overviewHeader}>
            <IconButton icon="receipt" size={20} iconColor={theme.colors.secondary} />
            <Text variant="bodySmall" style={styles.overviewLabel}>
              Orders
            </Text>
          </View>
          <Text variant="headlineSmall" style={styles.overviewValue}>
            {salesData?.ordersCount || 0}
          </Text>
          <Text variant="bodySmall" style={styles.overviewSubtext}>
            Avg: ${salesData?.averageOrderValue.toFixed(2) || '0'}
          </Text>
        </Card.Content>
      </Card>

      <Card style={styles.overviewCard}>
        <Card.Content>
          <View style={styles.overviewHeader}>
            <IconButton icon="package-variant" size={20} iconColor={theme.colors.tertiary} />
            <Text variant="bodySmall" style={styles.overviewLabel}>
              Inventory
            </Text>
          </View>
          <Text variant="headlineSmall" style={styles.overviewValue}>
            ${inventoryMetrics?.totalValue.toLocaleString() || '0'}
          </Text>
          <View style={styles.inventoryAlerts}>
            {inventoryMetrics?.lowStockItems > 0 && (
              <Chip compact style={styles.alertChip}>
                {inventoryMetrics.lowStockItems} low
              </Chip>
            )}
          </View>
        </Card.Content>
      </Card>

      <Card style={styles.overviewCard}>
        <Card.Content>
          <View style={styles.overviewHeader}>
            <IconButton icon="account-star" size={20} iconColor={theme.colors.outline} />
            <Text variant="bodySmall" style={styles.overviewLabel}>
              Top Staff
            </Text>
          </View>
          <Text variant="titleMedium" style={styles.overviewValue}>
            {staffPerformance[0]?.name.split(' ')[0] || 'N/A'}
          </Text>
          <Text variant="bodySmall" style={styles.overviewSubtext}>
            {staffPerformance[0]?.ordersServed || 0} orders
          </Text>
        </Card.Content>
      </Card>
    </View>
  );

  const renderSalesChart = () => (
    <Card style={styles.chartCard}>
      <List.Accordion
        title="Sales Trend"
        expanded={expandedSections.includes('sales')}
        onPress={() => toggleSection('sales')}
        right={props => (
          <View style={styles.accordionRight}>
            <Text variant="bodyMedium" style={styles.chartTotal}>
              ${salesData?.totalSales.toLocaleString() || '0'}
            </Text>
            <List.Icon {...props} />
          </View>
        )}>
        <View style={styles.chartContainer}>
          {/* Chart placeholder */}
          <View style={styles.chartPlaceholder}>
            <Text variant="bodyMedium" style={styles.placeholderText}>
              Sales chart would be displayed here
            </Text>
            <Text variant="bodySmall" style={styles.placeholderSubtext}>
              Install react-native-chart-kit to enable charts
            </Text>
          </View>
          
          {/* Data table as alternative */}
          <DataTable style={styles.dataTable}>
            <DataTable.Header>
              <DataTable.Title>Period</DataTable.Title>
              <DataTable.Title numeric>Amount</DataTable.Title>
            </DataTable.Header>
            
            {salesData?.[timeRange === 'day' ? 'daily' : timeRange === 'week' ? 'weekly' : 'monthly']
              .slice(-5)
              .map((item, index) => (
                <DataTable.Row key={index}>
                  <DataTable.Cell>
                    {timeRange === 'day' ? format(new Date(item.date), 'MMM d') : item[timeRange === 'week' ? 'week' : 'month']}
                  </DataTable.Cell>
                  <DataTable.Cell numeric>
                    ${item.amount.toLocaleString()}
                  </DataTable.Cell>
                </DataTable.Row>
              ))}
          </DataTable>
        </View>
      </List.Accordion>
    </Card>
  );

  const renderTopItems = () => (
    <Card style={styles.chartCard}>
      <List.Accordion
        title="Top Selling Items"
        expanded={expandedSections.includes('items')}
        onPress={() => toggleSection('items')}>
        <View style={styles.topItemsContainer}>
          {salesData?.topItems.map((item, index) => (
            <View key={index} style={styles.topItem}>
              <View style={styles.topItemInfo}>
                <Text variant="bodyMedium" style={styles.topItemRank}>
                  #{index + 1}
                </Text>
                <View style={styles.topItemDetails}>
                  <Text variant="bodyMedium" style={styles.topItemName}>
                    {item.name}
                  </Text>
                  <Text variant="bodySmall" style={styles.topItemQuantity}>
                    {item.quantity} sold
                  </Text>
                </View>
              </View>
              <Text variant="bodyMedium" style={styles.topItemRevenue}>
                ${item.revenue.toLocaleString()}
              </Text>
            </View>
          ))}
        </View>
      </List.Accordion>
    </Card>
  );

  const renderCategoryBreakdown = () => (
    <Card style={styles.chartCard}>
      <List.Accordion
        title="Sales by Category"
        expanded={expandedSections.includes('categories')}
        onPress={() => toggleSection('categories')}>
        <View style={styles.categoryContainer}>
          {salesData?.categoryBreakdown.map((category, index) => (
            <View key={index} style={styles.categoryItem}>
              <View style={styles.categoryHeader}>
                <Text variant="bodyMedium">{category.category}</Text>
                <Text variant="bodyMedium">${category.value.toLocaleString()}</Text>
              </View>
              <View style={styles.categoryProgress}>
                <ProgressBar
                  progress={category.percentage / 100}
                  color={theme.colors.primary}
                  style={styles.progressBar}
                />
                <Text variant="bodySmall" style={styles.categoryPercentage}>
                  {category.percentage}%
                </Text>
              </View>
            </View>
          ))}
        </View>
      </List.Accordion>
    </Card>
  );

  const renderStaffPerformance = () => (
    <Card style={styles.chartCard}>
      <List.Accordion
        title="Staff Performance"
        expanded={expandedSections.includes('staff')}
        onPress={() => toggleSection('staff')}>
        <DataTable>
          <DataTable.Header>
            <DataTable.Title>Staff</DataTable.Title>
            <DataTable.Title numeric>Orders</DataTable.Title>
            <DataTable.Title numeric>Avg Time</DataTable.Title>
            <DataTable.Title numeric>Rating</DataTable.Title>
          </DataTable.Header>
          
          {staffPerformance.map((staff) => (
            <DataTable.Row key={staff.id}>
              <DataTable.Cell>{staff.name}</DataTable.Cell>
              <DataTable.Cell numeric>{staff.ordersServed}</DataTable.Cell>
              <DataTable.Cell numeric>{staff.averageOrderTime}m</DataTable.Cell>
              <DataTable.Cell numeric>
                <View style={styles.ratingCell}>
                  <Text>{staff.customerRating}</Text>
                  <IconButton
                    icon="star"
                    size={14}
                    iconColor={theme.colors.tertiary}
                    style={styles.starIcon}
                  />
                </View>
              </DataTable.Cell>
            </DataTable.Row>
          ))}
        </DataTable>
      </List.Accordion>
    </Card>
  );

  const renderExportModal = () => (
    <Portal>
      <Modal
        visible={showExportModal}
        onDismiss={() => setShowExportModal(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Export Analytics
        </Text>
        
        <Text variant="bodyMedium" style={styles.modalSubtitle}>
          Select export format:
        </Text>
        
        <View style={styles.exportOptions}>
          <TouchableOpacity
            style={styles.exportOption}
            onPress={() => {
              Alert.alert('Export', 'Exporting to PDF...');
              setShowExportModal(false);
            }}>
            <IconButton icon="file-pdf-box" size={32} />
            <Text variant="bodyMedium">PDF Report</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={styles.exportOption}
            onPress={() => {
              Alert.alert('Export', 'Exporting to Excel...');
              setShowExportModal(false);
            }}>
            <IconButton icon="microsoft-excel" size={32} />
            <Text variant="bodyMedium">Excel</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={styles.exportOption}
            onPress={() => {
              Alert.alert('Export', 'Exporting to CSV...');
              setShowExportModal(false);
            }}>
            <IconButton icon="file-delimited" size={32} />
            <Text variant="bodyMedium">CSV</Text>
          </TouchableOpacity>
        </View>
        
        <Button
          mode="outlined"
          onPress={() => setShowExportModal(false)}
          style={styles.modalButton}>
          Cancel
        </Button>
      </Modal>
    </Portal>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text variant="headlineMedium" style={styles.title}>
            Analytics
          </Text>
          <Text variant="bodyMedium" style={styles.subtitle}>
            {getTimeRangeLabel()} Performance
          </Text>
        </View>
        <IconButton
          icon="download"
          size={24}
          onPress={() => setShowExportModal(true)}
        />
      </View>

      <SegmentedButtons
        value={timeRange}
        onValueChange={value => setTimeRange(value as 'day' | 'week' | 'month')}
        buttons={[
          { value: 'day', label: 'Day' },
          { value: 'week', label: 'Week' },
          { value: 'month', label: 'Month' },
        ]}
        style={styles.timeRangeSelector}
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}>
        
        {renderOverviewCards()}
        {renderSalesChart()}
        {renderTopItems()}
        {renderCategoryBreakdown()}
        {renderStaffPerformance()}
        
      </ScrollView>

      {renderExportModal()}
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
  subtitle: {
    color: '#64748b',
  },
  timeRangeSelector: {
    marginHorizontal: 16,
    marginBottom: 16,
  },
  scrollContent: {
    paddingBottom: 24,
  },
  overviewGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    marginBottom: 16,
  },
  overviewCard: {
    width: (screenWidth - 48) / 2,
    margin: 4,
  },
  overviewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  overviewLabel: {
    color: '#64748b',
    marginLeft: -8,
  },
  overviewValue: {
    fontWeight: '600',
  },
  overviewSubtext: {
    color: '#94a3b8',
    marginTop: 4,
  },
  growthContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
    marginLeft: -8,
  },
  growthText: {
    marginLeft: -8,
    fontWeight: '600',
  },
  inventoryAlerts: {
    marginTop: 4,
  },
  alertChip: {
    height: 24,
    backgroundColor: '#fee2e2',
  },
  chartCard: {
    marginHorizontal: 16,
    marginBottom: 12,
  },
  accordionRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  chartTotal: {
    fontWeight: '600',
    marginRight: 8,
  },
  chartContainer: {
    padding: 16,
  },
  chartPlaceholder: {
    height: 200,
    backgroundColor: '#f1f5f9',
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  placeholderText: {
    color: '#64748b',
  },
  placeholderSubtext: {
    color: '#94a3b8',
    marginTop: 4,
  },
  dataTable: {
    marginTop: -16,
  },
  topItemsContainer: {
    padding: 16,
  },
  topItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  topItemInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  topItemRank: {
    fontWeight: '600',
    marginRight: 12,
    color: '#64748b',
  },
  topItemDetails: {
    flex: 1,
  },
  topItemName: {
    fontWeight: '500',
  },
  topItemQuantity: {
    color: '#64748b',
    marginTop: 2,
  },
  topItemRevenue: {
    fontWeight: '600',
  },
  categoryContainer: {
    padding: 16,
  },
  categoryItem: {
    marginBottom: 16,
  },
  categoryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  categoryProgress: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  progressBar: {
    flex: 1,
    height: 8,
    borderRadius: 4,
  },
  categoryPercentage: {
    marginLeft: 8,
    color: '#64748b',
    minWidth: 35,
  },
  ratingCell: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  starIcon: {
    margin: 0,
    marginLeft: -4,
  },
  modalContent: {
    backgroundColor: 'white',
    padding: 24,
    margin: 20,
    borderRadius: 8,
  },
  modalTitle: {
    marginBottom: 8,
  },
  modalSubtitle: {
    marginBottom: 24,
    color: '#64748b',
  },
  exportOptions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 24,
  },
  exportOption: {
    alignItems: 'center',
  },
  modalButton: {
    marginTop: 8,
  },
});