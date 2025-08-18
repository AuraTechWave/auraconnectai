import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import {
  Text,
  Card,
  Avatar,
  Chip,
  Searchbar,
  FAB,
  useTheme,
  IconButton,
  Badge,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { StaffStackParamList } from '@navigation/StaffNavigator';
import { useQuery } from '@tanstack/react-query';
import { useOfflineSync } from '@hooks/useOfflineSync';
import { Staff } from '@database/models/Staff';

type NavigationProp = NativeStackNavigationProp<StaffStackParamList>;

interface StaffMember {
  id: number;
  name: string;
  email: string;
  phone: string;
  role: string;
  avatar?: string;
  status: 'active' | 'inactive' | 'on_leave';
  currentShift?: {
    start: string;
    end: string;
  };
  hoursThisWeek: number;
  rating: number;
}

export const StaffListScreen: React.FC = () => {
  const theme = useTheme();
  const navigation = useNavigation<NavigationProp>();
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const { syncData } = useOfflineSync();

  // Fetch staff data
  const { data: staffList = [], refetch } = useQuery<StaffMember[]>({
    queryKey: ['staff', 'list'],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return [
        {
          id: 1,
          name: 'John Doe',
          email: 'john.doe@restaurant.com',
          phone: '+1 234-567-8901',
          role: 'Server',
          status: 'active',
          currentShift: {
            start: '09:00',
            end: '17:00',
          },
          hoursThisWeek: 32,
          rating: 4.5,
        },
        {
          id: 2,
          name: 'Jane Smith',
          email: 'jane.smith@restaurant.com',
          phone: '+1 234-567-8902',
          role: 'Chef',
          status: 'active',
          hoursThisWeek: 38,
          rating: 4.8,
        },
        {
          id: 3,
          name: 'Bob Wilson',
          email: 'bob.wilson@restaurant.com',
          phone: '+1 234-567-8903',
          role: 'Manager',
          status: 'on_leave',
          hoursThisWeek: 0,
          rating: 4.2,
        },
      ];
    },
  });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    await syncData('staff');
    setRefreshing(false);
  }, [refetch, syncData]);

  const filteredStaff = useMemo(() => {
    if (!searchQuery) return staffList;
    return staffList.filter(
      staff =>
        staff.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        staff.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
        staff.email.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [staffList, searchQuery]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return theme.colors.primary;
      case 'inactive':
        return theme.colors.error;
      case 'on_leave':
        return theme.colors.tertiary;
      default:
        return theme.colors.outline;
    }
  };

  const getAvatarText = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase();
  };

  const renderStaffItem = ({ item }: { item: StaffMember }) => (
    <TouchableOpacity
      onPress={() => navigation.navigate('StaffDetails', { staffId: item.id })}>
      <Card style={styles.staffCard}>
        <Card.Content style={styles.cardContent}>
          <View style={styles.staffHeader}>
            <Avatar.Text
              size={48}
              label={getAvatarText(item.name)}
              style={{ backgroundColor: theme.colors.primaryContainer }}
            />
            <View style={styles.staffInfo}>
              <View style={styles.nameRow}>
                <Text variant="titleMedium" style={styles.staffName}>
                  {item.name}
                </Text>
                <Chip
                  mode="flat"
                  compact
                  textStyle={styles.statusChipText}
                  style={[
                    styles.statusChip,
                    { backgroundColor: getStatusColor(item.status) + '20' },
                  ]}>
                  {item.status.replace('_', ' ')}
                </Chip>
              </View>
              <Text variant="bodyMedium" style={styles.roleText}>
                {item.role}
              </Text>
              {item.currentShift && (
                <View style={styles.shiftInfo}>
                  <Text variant="bodySmall" style={styles.shiftText}>
                    Current shift: {item.currentShift.start} - {item.currentShift.end}
                  </Text>
                </View>
              )}
            </View>
          </View>

          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text variant="labelSmall" style={styles.statLabel}>
                Hours this week
              </Text>
              <Text variant="bodyLarge" style={styles.statValue}>
                {item.hoursThisWeek}h
              </Text>
            </View>
            <View style={styles.statItem}>
              <Text variant="labelSmall" style={styles.statLabel}>
                Rating
              </Text>
              <View style={styles.ratingContainer}>
                <Text variant="bodyLarge" style={styles.statValue}>
                  {item.rating}
                </Text>
                <IconButton
                  icon="star"
                  size={16}
                  iconColor={theme.colors.tertiary}
                  style={styles.starIcon}
                />
              </View>
            </View>
          </View>
        </Card.Content>
      </Card>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          Staff
        </Text>
        <IconButton
          icon="calendar-clock"
          size={24}
          onPress={() => navigation.navigate('Schedule')}
        />
      </View>

      <Searchbar
        placeholder="Search staff..."
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={styles.searchBar}
        iconColor={theme.colors.primary}
      />

      <FlatList
        data={filteredStaff}
        renderItem={renderStaffItem}
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
              No staff members found
            </Text>
          </View>
        }
      />

      <FAB
        icon="plus"
        style={[styles.fab, { backgroundColor: theme.colors.primary }]}
        onPress={() => navigation.navigate('AddStaff' as any)}
        label="Add Staff"
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
  searchBar: {
    marginHorizontal: 16,
    marginBottom: 8,
    elevation: 0,
    backgroundColor: 'white',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 80,
  },
  staffCard: {
    marginBottom: 12,
    elevation: 2,
  },
  cardContent: {
    paddingVertical: 8,
  },
  staffHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  staffInfo: {
    flex: 1,
    marginLeft: 12,
  },
  nameRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  staffName: {
    fontWeight: '600',
    flex: 1,
  },
  statusChip: {
    height: 24,
    marginLeft: 8,
  },
  statusChipText: {
    fontSize: 11,
    textTransform: 'capitalize',
  },
  roleText: {
    color: '#64748b',
    marginTop: 2,
  },
  shiftInfo: {
    marginTop: 4,
  },
  shiftText: {
    color: '#94a3b8',
  },
  statsRow: {
    flexDirection: 'row',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
  },
  statItem: {
    flex: 1,
  },
  statLabel: {
    color: '#94a3b8',
    marginBottom: 4,
  },
  statValue: {
    fontWeight: '600',
    color: '#1e293b',
  },
  ratingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  starIcon: {
    margin: 0,
    marginLeft: -4,
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
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
  },
});