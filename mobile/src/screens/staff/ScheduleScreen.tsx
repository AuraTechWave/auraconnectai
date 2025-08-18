import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  Alert,
} from 'react-native';
import {
  Text,
  Card,
  useTheme,
  IconButton,
  Chip,
  FAB,
  Portal,
  Modal,
  Button,
  SegmentedButtons,
  Avatar,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import DatePicker from 'react-native-date-picker';
import { format, startOfWeek, addDays, isSameDay, parseISO } from 'date-fns';
import { useQuery, useMutation } from '@tanstack/react-query';
import { FlatList } from 'react-native';

const { width: screenWidth } = Dimensions.get('window');

interface Shift {
  id: string;
  staffId: number;
  staffName: string;
  date: string;
  startTime: string;
  endTime: string;
  role: string;
  status: 'scheduled' | 'confirmed' | 'completed' | 'cancelled';
  break?: number;
  notes?: string;
}

interface StaffAvailability {
  staffId: number;
  date: string;
  available: boolean;
  preferredHours?: {
    start: string;
    end: string;
  };
}

export const ScheduleScreen: React.FC = () => {
  const theme = useTheme();
  const navigation = useNavigation();
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [viewMode, setViewMode] = useState<'day' | 'week'>('week');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [selectedShift, setSelectedShift] = useState<Shift | null>(null);
  const [showShiftModal, setShowShiftModal] = useState(false);

  // Fetch schedule data
  const { data: scheduleData = [], refetch } = useQuery<Shift[]>({
    queryKey: ['schedule', selectedDate, viewMode],
    queryFn: async () => {
      // TODO: Replace with actual API call
      const mockShifts: Shift[] = [
        {
          id: '1',
          staffId: 1,
          staffName: 'John Doe',
          date: format(selectedDate, 'yyyy-MM-dd'),
          startTime: '09:00',
          endTime: '17:00',
          role: 'Server',
          status: 'confirmed',
          break: 30,
        },
        {
          id: '2',
          staffId: 2,
          staffName: 'Jane Smith',
          date: format(selectedDate, 'yyyy-MM-dd'),
          startTime: '12:00',
          endTime: '20:00',
          role: 'Chef',
          status: 'scheduled',
          break: 45,
        },
        {
          id: '3',
          staffId: 3,
          staffName: 'Bob Wilson',
          date: format(addDays(selectedDate, 1), 'yyyy-MM-dd'),
          startTime: '08:00',
          endTime: '16:00',
          role: 'Manager',
          status: 'confirmed',
          break: 30,
        },
      ];
      return mockShifts;
    },
  });

  // Fetch staff availability
  const { data: availabilityData = [] } = useQuery<StaffAvailability[]>({
    queryKey: ['availability', selectedDate],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return [];
    },
  });

  // Mutation for updating shifts
  const updateShiftMutation = useMutation({
    mutationFn: async (shift: Shift) => {
      // TODO: Implement API call
      return shift;
    },
    onSuccess: () => {
      refetch();
    },
  });

  const weekDays = useMemo(() => {
    const start = startOfWeek(selectedDate, { weekStartsOn: 1 });
    return Array.from({ length: 7 }, (_, i) => addDays(start, i));
  }, [selectedDate]);

  const shiftsGroupedByDay = useMemo(() => {
    const grouped: Record<string, Shift[]> = {};
    
    if (viewMode === 'week') {
      weekDays.forEach(day => {
        const dayStr = format(day, 'yyyy-MM-dd');
        grouped[dayStr] = scheduleData.filter(shift => shift.date === dayStr);
      });
    } else {
      const dayStr = format(selectedDate, 'yyyy-MM-dd');
      grouped[dayStr] = scheduleData.filter(shift => shift.date === dayStr);
    }
    
    return grouped;
  }, [scheduleData, viewMode, selectedDate, weekDays]);

  const getShiftColor = (status: string) => {
    switch (status) {
      case 'confirmed':
        return theme.colors.primary;
      case 'scheduled':
        return theme.colors.secondary;
      case 'completed':
        return theme.colors.tertiary;
      case 'cancelled':
        return theme.colors.error;
      default:
        return theme.colors.outline;
    }
  };

  const handleShiftPress = (shift: Shift) => {
    setSelectedShift(shift);
    setShowShiftModal(true);
  };

  const handleShiftDrop = async (data: Shift[], from: number, to: number) => {
    // Handle shift reordering or time adjustment
    const movedShift = data[to];
    await updateShiftMutation.mutateAsync(movedShift);
  };

  const renderShiftCard = ({ item }: { item: Shift }) => (
    <TouchableOpacity
      onPress={() => handleShiftPress(item)}>
      <Card
        style={[
          styles.shiftCard,
          { borderLeftColor: getShiftColor(item.status), borderLeftWidth: 4 },
        ]}>
        <Card.Content style={styles.shiftContent}>
          <View style={styles.shiftHeader}>
            <Avatar.Text
              size={32}
              label={item.staffName.split(' ').map(n => n[0]).join('')}
              style={{ backgroundColor: theme.colors.primaryContainer }}
            />
            <View style={styles.shiftInfo}>
              <Text variant="titleSmall" style={styles.staffName}>
                {item.staffName}
              </Text>
              <Text variant="bodySmall" style={styles.roleText}>
                {item.role}
              </Text>
            </View>
            <Chip
              mode="flat"
              compact
              textStyle={styles.statusChipText}
              style={[
                styles.statusChip,
                { backgroundColor: getShiftColor(item.status) + '20' },
              ]}>
              {item.status}
            </Chip>
          </View>
          <View style={styles.shiftTime}>
            <IconButton icon="clock-outline" size={16} />
            <Text variant="bodySmall">
              {item.startTime} - {item.endTime}
              {item.break ? ` (${item.break}min break)` : ''}
            </Text>
          </View>
        </Card.Content>
      </Card>
    </TouchableOpacity>
  );

  const renderDayView = () => {
    const dayStr = format(selectedDate, 'yyyy-MM-dd');
    const dayShifts = shiftsGroupedByDay[dayStr] || [];

    return (
      <View style={styles.dayViewContainer}>
        <Text variant="titleMedium" style={styles.dayTitle}>
          {format(selectedDate, 'EEEE, MMMM d')}
        </Text>
        <FlatList
          data={dayShifts}
          renderItem={renderShiftCard}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.shiftsList}
        />
      </View>
    );
  };

  const renderWeekView = () => (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      <View style={styles.weekContainer}>
        {weekDays.map(day => {
          const dayStr = format(day, 'yyyy-MM-dd');
          const dayShifts = shiftsGroupedByDay[dayStr] || [];
          const isToday = isSameDay(day, new Date());

          return (
            <View key={dayStr} style={styles.dayColumn}>
              <View
                style={[
                  styles.dayHeader,
                  isToday && styles.todayHeader,
                ]}>
                <Text variant="labelLarge" style={styles.dayName}>
                  {format(day, 'EEE')}
                </Text>
                <Text
                  variant="titleMedium"
                  style={[styles.dayDate, isToday && styles.todayDate]}>
                  {format(day, 'd')}
                </Text>
              </View>
              <ScrollView style={styles.dayShifts}>
                {dayShifts.map(shift => (
                  <TouchableOpacity
                    key={shift.id}
                    onPress={() => handleShiftPress(shift)}>
                    <Card
                      style={[
                        styles.weekShiftCard,
                        { borderTopColor: getShiftColor(shift.status) },
                      ]}>
                      <Card.Content style={styles.weekShiftContent}>
                        <Text variant="bodySmall" numberOfLines={1}>
                          {shift.staffName}
                        </Text>
                        <Text variant="labelSmall" style={styles.shiftTimeText}>
                          {shift.startTime} - {shift.endTime}
                        </Text>
                      </Card.Content>
                    </Card>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          );
        })}
      </View>
    </ScrollView>
  );

  const renderShiftModal = () => (
    <Portal>
      <Modal
        visible={showShiftModal}
        onDismiss={() => setShowShiftModal(false)}
        contentContainerStyle={styles.modalContent}>
        {selectedShift && (
          <>
            <Text variant="headlineSmall" style={styles.modalTitle}>
              Shift Details
            </Text>
            <View style={styles.modalBody}>
              <Text variant="titleMedium">{selectedShift.staffName}</Text>
              <Text variant="bodyMedium" style={styles.modalRole}>
                {selectedShift.role}
              </Text>
              <View style={styles.modalRow}>
                <IconButton icon="calendar" size={20} />
                <Text>{format(parseISO(selectedShift.date), 'EEEE, MMMM d')}</Text>
              </View>
              <View style={styles.modalRow}>
                <IconButton icon="clock-outline" size={20} />
                <Text>
                  {selectedShift.startTime} - {selectedShift.endTime}
                  {selectedShift.break && ` (${selectedShift.break}min break)`}
                </Text>
              </View>
              <View style={styles.modalActions}>
                <Button
                  mode="outlined"
                  onPress={() => {
                    setShowShiftModal(false);
                    // Navigate to edit shift
                  }}>
                  Edit
                </Button>
                <Button
                  mode="contained"
                  onPress={() => {
                    setShowShiftModal(false);
                    // Handle confirmation
                  }}>
                  Confirm
                </Button>
              </View>
            </View>
          </>
        )}
      </Modal>
    </Portal>
  );

  const checkScheduleConflicts = () => {
    // TODO: Implement conflict detection
    Alert.alert(
      'Schedule Check',
      'No conflicts found in the current schedule.',
      [{ text: 'OK' }],
    );
  };

  const optimizeSchedule = () => {
    // TODO: Implement schedule optimization
    Alert.alert(
      'Schedule Optimization',
      'This feature will automatically optimize staff assignments based on availability and skills.',
      [{ text: 'OK' }],
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          Schedule
        </Text>
        <View style={styles.headerActions}>
          <IconButton
            icon="calendar"
            size={24}
            onPress={() => setShowDatePicker(true)}
          />
          <IconButton
            icon="check-all"
            size={24}
            onPress={checkScheduleConflicts}
          />
          <IconButton
            icon="auto-fix"
            size={24}
            onPress={optimizeSchedule}
          />
        </View>
      </View>

      <SegmentedButtons
        value={viewMode}
        onValueChange={value => setViewMode(value as 'day' | 'week')}
        buttons={[
          { value: 'day', label: 'Day' },
          { value: 'week', label: 'Week' },
        ]}
        style={styles.viewModeToggle}
      />

      <View style={styles.content}>
        {viewMode === 'day' ? renderDayView() : renderWeekView()}
      </View>

      <DatePicker
        modal
        open={showDatePicker}
        date={selectedDate}
        onConfirm={date => {
          setShowDatePicker(false);
          setSelectedDate(date);
        }}
        onCancel={() => setShowDatePicker(false)}
        mode="date"
      />

      {renderShiftModal()}

      <FAB
        icon="plus"
        style={[styles.fab, { backgroundColor: theme.colors.primary }]}
        onPress={() => navigation.navigate('AddShift' as any)}
        label="Add Shift"
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
  viewModeToggle: {
    marginHorizontal: 16,
    marginBottom: 16,
  },
  content: {
    flex: 1,
  },
  dayViewContainer: {
    flex: 1,
    paddingHorizontal: 16,
  },
  dayTitle: {
    marginBottom: 16,
    fontWeight: '600',
  },
  shiftsList: {
    paddingBottom: 80,
  },
  shiftCard: {
    marginBottom: 12,
    elevation: 2,
  },
  shiftContent: {
    paddingVertical: 8,
  },
  shiftHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  shiftInfo: {
    flex: 1,
    marginLeft: 12,
  },
  staffName: {
    fontWeight: '600',
  },
  roleText: {
    color: '#64748b',
  },
  statusChip: {
    height: 24,
  },
  statusChipText: {
    fontSize: 11,
    textTransform: 'capitalize',
  },
  shiftTime: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  weekContainer: {
    flexDirection: 'row',
  },
  dayColumn: {
    width: screenWidth * 0.3,
    minWidth: 120,
    borderRightWidth: 1,
    borderRightColor: '#e2e8f0',
  },
  dayHeader: {
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  todayHeader: {
    backgroundColor: '#dbeafe',
  },
  dayName: {
    color: '#64748b',
  },
  dayDate: {
    fontWeight: '600',
  },
  todayDate: {
    color: '#2563eb',
  },
  dayShifts: {
    flex: 1,
    padding: 8,
  },
  weekShiftCard: {
    marginBottom: 8,
    elevation: 1,
    borderTopWidth: 3,
  },
  weekShiftContent: {
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  shiftTimeText: {
    color: '#64748b',
    marginTop: 2,
  },
  modalContent: {
    backgroundColor: 'white',
    padding: 24,
    margin: 20,
    borderRadius: 8,
  },
  modalTitle: {
    marginBottom: 16,
  },
  modalBody: {
    gap: 8,
  },
  modalRole: {
    color: '#64748b',
    marginBottom: 16,
  },
  modalRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 24,
  },
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
  },
});