import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Animated,
  RefreshControl,
  Alert,
  Dimensions,
} from 'react-native';
import { FAB, Chip, IconButton, Portal, Modal } from 'react-native-paper';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { format, addDays, startOfWeek, isSameDay, isToday } from 'date-fns';
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
import { useNavigation } from '@react-navigation/native';

const { width: screenWidth } = Dimensions.get('window');

interface Shift {
  id: string;
  staffId: string;
  staffName: string;
  staffAvatar?: string;
  role: string;
  date: Date;
  startTime: string;
  endTime: string;
  breakMinutes: number;
  status: 'scheduled' | 'in-progress' | 'completed' | 'cancelled' | 'swap-requested';
  notes?: string;
  department?: string;
}

interface StaffMember {
  id: string;
  name: string;
  avatar?: string;
  role: string;
  department: string;
  availability: 'available' | 'busy' | 'off' | 'vacation';
  hoursThisWeek: number;
  maxHours: number;
}

const StaffScheduleScreen: React.FC = () => {
  const navigation = useNavigation<any>();
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [viewMode, setViewMode] = useState<'day' | 'week' | 'month'>('week');
  const [refreshing, setRefreshing] = useState(false);
  const [swapModalVisible, setSwapModalVisible] = useState(false);
  const [selectedShift, setSelectedShift] = useState<Shift | null>(null);
  const scrollViewRef = useRef<ScrollView>(null);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  // Mock data
  const [shifts] = useState<Shift[]>([
    {
      id: '1',
      staffId: '1',
      staffName: 'John Smith',
      role: 'Server',
      date: new Date(),
      startTime: '09:00',
      endTime: '17:00',
      breakMinutes: 30,
      status: 'in-progress',
      department: 'Front of House',
    },
    {
      id: '2',
      staffId: '2',
      staffName: 'Maria Garcia',
      role: 'Head Chef',
      date: new Date(),
      startTime: '07:00',
      endTime: '15:00',
      breakMinutes: 45,
      status: 'scheduled',
      department: 'Kitchen',
    },
    {
      id: '3',
      staffId: '3',
      staffName: 'David Chen',
      role: 'Bartender',
      date: new Date(),
      startTime: '16:00',
      endTime: '23:00',
      breakMinutes: 30,
      status: 'scheduled',
      department: 'Bar',
    },
    {
      id: '4',
      staffId: '4',
      staffName: 'Sarah Johnson',
      role: 'Server',
      date: addDays(new Date(), 1),
      startTime: '12:00',
      endTime: '20:00',
      breakMinutes: 30,
      status: 'swap-requested',
      notes: 'Looking for someone to cover - family emergency',
      department: 'Front of House',
    },
  ]);

  const [staff] = useState<StaffMember[]>([
    {
      id: '1',
      name: 'John Smith',
      role: 'Server',
      department: 'Front of House',
      availability: 'busy',
      hoursThisWeek: 32,
      maxHours: 40,
    },
    {
      id: '2',
      name: 'Maria Garcia',
      role: 'Head Chef',
      department: 'Kitchen',
      availability: 'available',
      hoursThisWeek: 38,
      maxHours: 45,
    },
    {
      id: '3',
      name: 'David Chen',
      role: 'Bartender',
      department: 'Bar',
      availability: 'available',
      hoursThisWeek: 28,
      maxHours: 40,
    },
    {
      id: '4',
      name: 'Sarah Johnson',
      role: 'Server',
      department: 'Front of House',
      availability: 'off',
      hoursThisWeek: 24,
      maxHours: 35,
    },
  ]);

  React.useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: animations.duration.normal,
      useNativeDriver: true,
    }).start();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 1500);
  };

  const getWeekDays = () => {
    const start = startOfWeek(selectedDate, { weekStartsOn: 1 });
    return Array.from({ length: 7 }, (_, i) => addDays(start, i));
  };

  const getStatusColor = (status: Shift['status']) => {
    const statusColors: Record<string, string> = {
      'scheduled': colors.primary[500],
      'in-progress': colors.success[500],
      'completed': colors.neutral[500],
      'cancelled': colors.error[500],
      'swap-requested': colors.warning[500],
    };
    return statusColors[status];
  };

  const getAvailabilityColor = (availability: StaffMember['availability']) => {
    const availabilityColors: Record<string, string> = {
      'available': colors.success[500],
      'busy': colors.warning[500],
      'off': colors.error[500],
      'vacation': colors.secondary[500],
    };
    return availabilityColors[availability];
  };

  const handleShiftPress = (shift: Shift) => {
    setSelectedShift(shift);
    Alert.alert(
      'Shift Options',
      `${shift.staffName} - ${shift.startTime} to ${shift.endTime}`,
      [
        { text: 'View Details', onPress: () => handleViewDetails(shift) },
        { text: 'Request Swap', onPress: () => handleRequestSwap(shift) },
        { text: 'Edit Shift', onPress: () => handleEditShift(shift) },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  const handleViewDetails = (shift: Shift) => {
    navigation.navigate('ShiftDetails', { shiftId: shift.id });
  };

  const handleRequestSwap = (shift: Shift) => {
    setSelectedShift(shift);
    setSwapModalVisible(true);
  };

  const handleEditShift = (shift: Shift) => {
    navigation.navigate('EditShift', { shiftId: shift.id });
  };

  const renderWeekView = () => {
    const weekDays = getWeekDays();
    
    return (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        ref={scrollViewRef}
        style={styles.weekContainer}
      >
        {weekDays.map((day, index) => {
          const dayShifts = shifts.filter(shift => isSameDay(shift.date, day));
          const isSelected = isSameDay(day, selectedDate);
          const isTodayDate = isToday(day);
          
          return (
            <TouchableOpacity
              key={index}
              style={[
                styles.dayColumn,
                isSelected && styles.selectedDayColumn,
              ]}
              onPress={() => setSelectedDate(day)}
              activeOpacity={0.7}
            >
              <View style={[
                styles.dayHeader,
                isTodayDate && styles.todayHeader,
              ]}>
                <Text style={[
                  styles.dayName,
                  isSelected && styles.selectedDayName,
                ]}>
                  {format(day, 'EEE')}
                </Text>
                <Text style={[
                  styles.dayNumber,
                  isSelected && styles.selectedDayNumber,
                ]}>
                  {format(day, 'd')}
                </Text>
                {dayShifts.length > 0 && (
                  <Badge
                    label={dayShifts.length}
                    variant="primary"
                    size="small"
                    style={styles.shiftCount}
                  />
                )}
              </View>
              
              <ScrollView style={styles.shiftsColumn}>
                {dayShifts.map((shift) => (
                  <TouchableOpacity
                    key={shift.id}
                    style={[
                      styles.shiftCard,
                      { borderLeftColor: getStatusColor(shift.status) },
                    ]}
                    onPress={() => handleShiftPress(shift)}
                    activeOpacity={0.7}
                  >
                    <View style={styles.shiftTime}>
                      <Text style={styles.shiftTimeText}>
                        {shift.startTime}
                      </Text>
                      <Text style={styles.shiftTimeDivider}>-</Text>
                      <Text style={styles.shiftTimeText}>
                        {shift.endTime}
                      </Text>
                    </View>
                    <Avatar
                      name={shift.staffName}
                      size="small"
                      source={shift.staffAvatar ? { uri: shift.staffAvatar } : undefined}
                    />
                    <Text style={styles.shiftStaffName} numberOfLines={1}>
                      {shift.staffName}
                    </Text>
                    <Text style={styles.shiftRole} numberOfLines={1}>
                      {shift.role}
                    </Text>
                    {shift.status === 'swap-requested' && (
                      <MaterialCommunityIcons
                        name="swap-horizontal"
                        size={16}
                        color={colors.warning[500]}
                        style={styles.swapIcon}
                      />
                    )}
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    );
  };

  const renderStaffOverview = () => {
    return (
      <View style={styles.staffOverview}>
        <Text style={styles.sectionTitle}>Staff Overview</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {staff.map((member) => (
            <Card
              key={member.id}
              variant="outlined"
              style={styles.staffCard}
              onPress={() => navigation.navigate('StaffProfile', { staffId: member.id })}
            >
              <CardContent style={styles.staffCardContent}>
                <Avatar
                  name={member.name}
                  size="medium"
                  source={member.avatar ? { uri: member.avatar } : undefined}
                  status={member.availability === 'available' ? 'online' : 
                          member.availability === 'busy' ? 'busy' : 'offline'}
                />
                <Text style={styles.staffName} numberOfLines={1}>
                  {member.name}
                </Text>
                <Text style={styles.staffRole} numberOfLines={1}>
                  {member.role}
                </Text>
                <View style={styles.hoursContainer}>
                  <Text style={styles.hoursText}>
                    {member.hoursThisWeek}/{member.maxHours}h
                  </Text>
                  <View style={styles.hoursProgress}>
                    <View
                      style={[
                        styles.hoursProgressFill,
                        {
                          width: `${(member.hoursThisWeek / member.maxHours) * 100}%`,
                          backgroundColor: 
                            member.hoursThisWeek >= member.maxHours ? colors.error[500] :
                            member.hoursThisWeek >= member.maxHours * 0.8 ? colors.warning[500] :
                            colors.success[500],
                        },
                      ]}
                    />
                  </View>
                </View>
              </CardContent>
            </Card>
          ))}
        </ScrollView>
      </View>
    );
  };

  const renderQuickStats = () => {
    const todayShifts = shifts.filter(shift => isToday(shift.date));
    const swapRequests = shifts.filter(shift => shift.status === 'swap-requested');
    const totalHours = shifts.reduce((acc, shift) => {
      const start = parseInt(shift.startTime.split(':')[0]);
      const end = parseInt(shift.endTime.split(':')[0]);
      return acc + (end - start);
    }, 0);

    return (
      <View style={styles.quickStats}>
        <View style={styles.statCard}>
          <MaterialCommunityIcons
            name="account-group"
            size={24}
            color={colors.primary[500]}
          />
          <Text style={styles.statValue}>{todayShifts.length}</Text>
          <Text style={styles.statLabel}>Today's Shifts</Text>
        </View>
        <View style={styles.statCard}>
          <MaterialCommunityIcons
            name="swap-horizontal"
            size={24}
            color={colors.warning[500]}
          />
          <Text style={styles.statValue}>{swapRequests.length}</Text>
          <Text style={styles.statLabel}>Swap Requests</Text>
        </View>
        <View style={styles.statCard}>
          <MaterialCommunityIcons
            name="clock-outline"
            size={24}
            color={colors.success[500]}
          />
          <Text style={styles.statValue}>{totalHours}h</Text>
          <Text style={styles.statLabel}>Total Hours</Text>
        </View>
      </View>
    );
  };

  return (
    <Animated.View style={[styles.container, { opacity: fadeAnim }]}>
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerTop}>
            <Text style={styles.headerTitle}>Staff Schedule</Text>
            <View style={styles.headerActions}>
              <IconButton
                icon="calendar-today"
                size={24}
                onPress={() => setViewMode('day')}
                iconColor={viewMode === 'day' ? colors.primary[500] : colors.text.secondary}
              />
              <IconButton
                icon="calendar-week"
                size={24}
                onPress={() => setViewMode('week')}
                iconColor={viewMode === 'week' ? colors.primary[500] : colors.text.secondary}
              />
              <IconButton
                icon="calendar-month"
                size={24}
                onPress={() => setViewMode('month')}
                iconColor={viewMode === 'month' ? colors.primary[500] : colors.text.secondary}
              />
            </View>
          </View>
          
          <View style={styles.dateSelector}>
            <IconButton
              icon="chevron-left"
              size={24}
              onPress={() => setSelectedDate(addDays(selectedDate, -7))}
            />
            <TouchableOpacity
              style={styles.currentDate}
              onPress={() => setSelectedDate(new Date())}
            >
              <Text style={styles.currentDateText}>
                {format(selectedDate, 'MMMM yyyy')}
              </Text>
              {!isToday(selectedDate) && (
                <Chip style={styles.todayChip} onPress={() => setSelectedDate(new Date())}>
                  Today
                </Chip>
              )}
            </TouchableOpacity>
            <IconButton
              icon="chevron-right"
              size={24}
              onPress={() => setSelectedDate(addDays(selectedDate, 7))}
            />
          </View>
        </View>

        {/* Quick Stats */}
        {renderQuickStats()}

        {/* Week View */}
        {viewMode === 'week' && renderWeekView()}

        {/* Staff Overview */}
        {renderStaffOverview()}

        {/* Upcoming Shifts */}
        <View style={styles.upcomingShifts}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Upcoming Shifts</Text>
            <TouchableOpacity>
              <Text style={styles.seeAllText}>See All</Text>
            </TouchableOpacity>
          </View>
          
          {shifts.slice(0, 3).map((shift) => (
            <Card
              key={shift.id}
              variant="outlined"
              style={styles.upcomingShiftCard}
              onPress={() => handleShiftPress(shift)}
            >
              <CardContent style={styles.upcomingShiftContent}>
                <View style={styles.upcomingShiftLeft}>
                  <Avatar
                    name={shift.staffName}
                    size="medium"
                    source={shift.staffAvatar ? { uri: shift.staffAvatar } : undefined}
                  />
                  <View style={styles.upcomingShiftInfo}>
                    <Text style={styles.upcomingShiftName}>{shift.staffName}</Text>
                    <Text style={styles.upcomingShiftRole}>{shift.role}</Text>
                    <View style={styles.upcomingShiftTime}>
                      <MaterialCommunityIcons
                        name="clock-outline"
                        size={14}
                        color={colors.text.secondary}
                      />
                      <Text style={styles.upcomingShiftTimeText}>
                        {shift.startTime} - {shift.endTime}
                      </Text>
                    </View>
                  </View>
                </View>
                <View style={styles.upcomingShiftRight}>
                  <Text style={styles.upcomingShiftDate}>
                    {format(shift.date, 'MMM dd')}
                  </Text>
                  <Badge
                    label={shift.status.replace('-', ' ')}
                    size="small"
                    style={{ backgroundColor: getStatusColor(shift.status) }}
                  />
                </View>
              </CardContent>
            </Card>
          ))}
        </View>
      </ScrollView>

      <FAB.Group
        open={false}
        visible
        icon="plus"
        actions={[
          {
            icon: 'calendar-plus',
            label: 'Add Shift',
            onPress: () => navigation.navigate('AddShift'),
          },
          {
            icon: 'account-plus',
            label: 'Add Staff',
            onPress: () => navigation.navigate('AddStaff'),
          },
          {
            icon: 'swap-horizontal',
            label: 'Swap Shift',
            onPress: () => setSwapModalVisible(true),
          },
        ]}
        onStateChange={() => {}}
        style={styles.fab}
      />
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.secondary,
  },
  header: {
    backgroundColor: colors.background.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    ...shadows.sm,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: typography.fontSize.h3,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  headerActions: {
    flexDirection: 'row',
  },
  dateSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  currentDate: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
  currentDateText: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
  },
  todayChip: {
    marginLeft: spacing.sm,
    height: 28,
  },
  quickStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    padding: spacing.md,
  },
  statCard: {
    alignItems: 'center',
    backgroundColor: colors.background.primary,
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    flex: 1,
    marginHorizontal: spacing.xs,
    ...shadows.sm,
  },
  statValue: {
    fontSize: typography.fontSize.h3,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    marginTop: spacing.xs,
  },
  statLabel: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginTop: spacing.xxs,
  },
  weekContainer: {
    backgroundColor: colors.background.primary,
    paddingVertical: spacing.sm,
  },
  dayColumn: {
    width: screenWidth * 0.35,
    marginHorizontal: spacing.xs,
  },
  selectedDayColumn: {
    backgroundColor: colors.primary[50],
    borderRadius: borderRadius.md,
  },
  dayHeader: {
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.light,
  },
  todayHeader: {
    backgroundColor: colors.primary[100],
    borderRadius: borderRadius.md,
  },
  dayName: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    textTransform: 'uppercase',
  },
  selectedDayName: {
    color: colors.primary[600],
    fontWeight: typography.fontWeight.semiBold,
  },
  dayNumber: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    marginTop: spacing.xxs,
  },
  selectedDayNumber: {
    color: colors.primary[600],
    fontWeight: typography.fontWeight.bold,
  },
  shiftCount: {
    marginTop: spacing.xs,
  },
  shiftsColumn: {
    paddingVertical: spacing.sm,
    maxHeight: 300,
  },
  shiftCard: {
    backgroundColor: colors.background.primary,
    padding: spacing.sm,
    marginBottom: spacing.xs,
    borderRadius: borderRadius.md,
    borderLeftWidth: 3,
    ...shadows.xs,
  },
  shiftTime: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  shiftTimeText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
  },
  shiftTimeDivider: {
    marginHorizontal: spacing.xxs,
    color: colors.text.tertiary,
  },
  shiftStaffName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    marginTop: spacing.xxs,
  },
  shiftRole: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginTop: 2,
  },
  swapIcon: {
    position: 'absolute',
    top: spacing.xs,
    right: spacing.xs,
  },
  staffOverview: {
    padding: spacing.md,
  },
  sectionTitle: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  seeAllText: {
    fontSize: typography.fontSize.body,
    color: colors.primary[500],
    fontWeight: typography.fontWeight.medium,
  },
  staffCard: {
    width: 120,
    marginRight: spacing.sm,
    backgroundColor: colors.background.primary,
  },
  staffCardContent: {
    alignItems: 'center',
    padding: spacing.sm,
  },
  staffName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    marginTop: spacing.xs,
  },
  staffRole: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginTop: 2,
  },
  hoursContainer: {
    width: '100%',
    marginTop: spacing.xs,
  },
  hoursText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    textAlign: 'center',
    marginBottom: spacing.xxs,
  },
  hoursProgress: {
    height: 4,
    backgroundColor: colors.neutral[200],
    borderRadius: borderRadius.full,
    overflow: 'hidden',
  },
  hoursProgressFill: {
    height: '100%',
    borderRadius: borderRadius.full,
  },
  upcomingShifts: {
    padding: spacing.md,
  },
  upcomingShiftCard: {
    marginBottom: spacing.sm,
    backgroundColor: colors.background.primary,
  },
  upcomingShiftContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.xs,
  },
  upcomingShiftLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  upcomingShiftInfo: {
    marginLeft: spacing.sm,
    flex: 1,
  },
  upcomingShiftName: {
    fontSize: typography.fontSize.bodyLarge,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
  },
  upcomingShiftRole: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginTop: 2,
  },
  upcomingShiftTime: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xxs,
  },
  upcomingShiftTimeText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.tertiary,
    marginLeft: spacing.xxs,
  },
  upcomingShiftRight: {
    alignItems: 'flex-end',
  },
  upcomingShiftDate: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    marginBottom: spacing.xxs,
  },
  fab: {
    position: 'absolute',
    right: 0,
    bottom: 0,
  },
});

export default StaffScheduleScreen;