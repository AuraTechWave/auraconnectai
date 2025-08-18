import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Linking,
} from 'react-native';
import {
  Text,
  Card,
  Avatar,
  useTheme,
  IconButton,
  Chip,
  Button,
  ProgressBar,
  Divider,
  List,
  DataTable,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { StaffStackParamList } from '@navigation/StaffNavigator';
import { useQuery } from '@tanstack/react-query';
import { format, parseISO, startOfWeek, endOfWeek } from 'date-fns';

type RouteProps = RouteProp<StaffStackParamList, 'StaffDetails'>;

interface StaffDetails {
  id: number;
  name: string;
  email: string;
  phone: string;
  role: string;
  department: string;
  avatar?: string;
  status: 'active' | 'inactive' | 'on_leave';
  hireDate: string;
  employeeId: string;
  address: string;
  emergencyContact: {
    name: string;
    phone: string;
    relationship: string;
  };
  performance: {
    rating: number;
    punctuality: number;
    productivity: number;
    teamwork: number;
  };
  currentWeek: {
    scheduledHours: number;
    workedHours: number;
    overtimeHours: number;
    breaksTotal: number;
  };
  availability: {
    monday: { start: string; end: string; available: boolean };
    tuesday: { start: string; end: string; available: boolean };
    wednesday: { start: string; end: string; available: boolean };
    thursday: { start: string; end: string; available: boolean };
    friday: { start: string; end: string; available: boolean };
    saturday: { start: string; end: string; available: boolean };
    sunday: { start: string; end: string; available: boolean };
  };
  skills: string[];
  certifications: Array<{
    name: string;
    expiryDate: string;
    status: 'valid' | 'expiring' | 'expired';
  }>;
}

export const StaffDetailsScreen: React.FC = () => {
  const theme = useTheme();
  const route = useRoute<RouteProps>();
  const navigation = useNavigation();
  const { staffId } = route.params;
  const [expandedSections, setExpandedSections] = useState<string[]>([
    'performance',
    'schedule',
  ]);

  // Fetch staff details
  const { data: staffDetails } = useQuery<StaffDetails>({
    queryKey: ['staff', staffId],
    queryFn: async () => {
      // TODO: Replace with actual API call
      return {
        id: staffId,
        name: 'John Doe',
        email: 'john.doe@restaurant.com',
        phone: '+1 234-567-8901',
        role: 'Senior Server',
        department: 'Front of House',
        status: 'active',
        hireDate: '2022-03-15',
        employeeId: 'EMP001',
        address: '123 Main St, City, State 12345',
        emergencyContact: {
          name: 'Jane Doe',
          phone: '+1 234-567-8902',
          relationship: 'Spouse',
        },
        performance: {
          rating: 4.5,
          punctuality: 4.8,
          productivity: 4.3,
          teamwork: 4.6,
        },
        currentWeek: {
          scheduledHours: 40,
          workedHours: 32,
          overtimeHours: 2,
          breaksTotal: 4.5,
        },
        availability: {
          monday: { start: '09:00', end: '17:00', available: true },
          tuesday: { start: '09:00', end: '17:00', available: true },
          wednesday: { start: '09:00', end: '17:00', available: true },
          thursday: { start: '09:00', end: '17:00', available: true },
          friday: { start: '09:00', end: '17:00', available: true },
          saturday: { start: '10:00', end: '18:00', available: true },
          sunday: { start: '', end: '', available: false },
        },
        skills: ['Customer Service', 'Wine Knowledge', 'POS Systems', 'Upselling'],
        certifications: [
          {
            name: 'Food Safety Certification',
            expiryDate: '2025-06-15',
            status: 'valid',
          },
          {
            name: 'Alcohol Service License',
            expiryDate: '2024-12-31',
            status: 'expiring',
          },
        ],
      };
    },
  });

  if (!staffDetails) {
    return null;
  }

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

  const getCertificationColor = (status: string) => {
    switch (status) {
      case 'valid':
        return theme.colors.primary;
      case 'expiring':
        return theme.colors.tertiary;
      case 'expired':
        return theme.colors.error;
      default:
        return theme.colors.outline;
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSections(prev =>
      prev.includes(section)
        ? prev.filter(s => s !== section)
        : [...prev, section],
    );
  };

  const renderPerformanceMetric = (label: string, value: number) => (
    <View style={styles.metricItem}>
      <View style={styles.metricHeader}>
        <Text variant="bodyMedium">{label}</Text>
        <Text variant="bodyMedium" style={styles.metricValue}>
          {value.toFixed(1)}
        </Text>
      </View>
      <ProgressBar
        progress={value / 5}
        color={theme.colors.primary}
        style={styles.progressBar}
      />
    </View>
  );

  const renderAvailabilityDay = (
    day: string,
    availability: { start: string; end: string; available: boolean },
  ) => (
    <View key={day} style={styles.availabilityRow}>
      <Text variant="bodyMedium" style={styles.dayLabel}>
        {day.charAt(0).toUpperCase() + day.slice(1)}
      </Text>
      {availability.available ? (
        <Text variant="bodySmall" style={styles.availabilityTime}>
          {availability.start} - {availability.end}
        </Text>
      ) : (
        <Text variant="bodySmall" style={styles.unavailable}>
          Unavailable
        </Text>
      )}
    </View>
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
            onPress={() => navigation.navigate('EditStaff' as any, { staffId })}
          />
        </View>

        <View style={styles.profileSection}>
          <Avatar.Text
            size={80}
            label={staffDetails.name
              .split(' ')
              .map(n => n[0])
              .join('')}
            style={{ backgroundColor: theme.colors.primaryContainer }}
          />
          <Text variant="headlineSmall" style={styles.name}>
            {staffDetails.name}
          </Text>
          <Text variant="bodyLarge" style={styles.role}>
            {staffDetails.role} • {staffDetails.department}
          </Text>
          <Chip
            mode="flat"
            textStyle={styles.statusChipText}
            style={[
              styles.statusChip,
              { backgroundColor: getStatusColor(staffDetails.status) + '20' },
            ]}>
            {staffDetails.status.replace('_', ' ')}
          </Chip>
        </View>

        <View style={styles.contactSection}>
          <TouchableOpacity
            onPress={() => Linking.openURL(`tel:${staffDetails.phone}`)}>
            <Card style={styles.contactCard}>
              <Card.Content style={styles.contactContent}>
                <IconButton icon="phone" size={20} />
                <Text variant="bodyMedium">{staffDetails.phone}</Text>
              </Card.Content>
            </Card>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => Linking.openURL(`mailto:${staffDetails.email}`)}>
            <Card style={styles.contactCard}>
              <Card.Content style={styles.contactContent}>
                <IconButton icon="email" size={20} />
                <Text variant="bodyMedium">{staffDetails.email}</Text>
              </Card.Content>
            </Card>
          </TouchableOpacity>
        </View>

        <Card style={styles.infoCard}>
          <List.Accordion
            title="Employee Information"
            expanded={expandedSections.includes('info')}
            onPress={() => toggleSection('info')}>
            <View style={styles.infoContent}>
              <View style={styles.infoRow}>
                <Text variant="bodyMedium" style={styles.infoLabel}>
                  Employee ID
                </Text>
                <Text variant="bodyMedium">{staffDetails.employeeId}</Text>
              </View>
              <Divider style={styles.divider} />
              <View style={styles.infoRow}>
                <Text variant="bodyMedium" style={styles.infoLabel}>
                  Hire Date
                </Text>
                <Text variant="bodyMedium">
                  {format(parseISO(staffDetails.hireDate), 'MMM d, yyyy')}
                </Text>
              </View>
              <Divider style={styles.divider} />
              <View style={styles.infoRow}>
                <Text variant="bodyMedium" style={styles.infoLabel}>
                  Address
                </Text>
                <Text variant="bodyMedium" style={styles.infoValue}>
                  {staffDetails.address}
                </Text>
              </View>
              <Divider style={styles.divider} />
              <View>
                <Text variant="bodyMedium" style={styles.infoLabel}>
                  Emergency Contact
                </Text>
                <Text variant="bodySmall" style={styles.emergencyInfo}>
                  {staffDetails.emergencyContact.name} (
                  {staffDetails.emergencyContact.relationship})
                </Text>
                <Text variant="bodySmall" style={styles.emergencyInfo}>
                  {staffDetails.emergencyContact.phone}
                </Text>
              </View>
            </View>
          </List.Accordion>
        </Card>

        <Card style={styles.infoCard}>
          <List.Accordion
            title="Performance"
            expanded={expandedSections.includes('performance')}
            onPress={() => toggleSection('performance')}>
            <View style={styles.performanceContent}>
              {renderPerformanceMetric('Overall Rating', staffDetails.performance.rating)}
              {renderPerformanceMetric('Punctuality', staffDetails.performance.punctuality)}
              {renderPerformanceMetric('Productivity', staffDetails.performance.productivity)}
              {renderPerformanceMetric('Teamwork', staffDetails.performance.teamwork)}
            </View>
          </List.Accordion>
        </Card>

        <Card style={styles.infoCard}>
          <List.Accordion
            title="Current Week Schedule"
            expanded={expandedSections.includes('schedule')}
            onPress={() => toggleSection('schedule')}>
            <View style={styles.scheduleContent}>
              <DataTable>
                <DataTable.Row>
                  <DataTable.Cell>Scheduled Hours</DataTable.Cell>
                  <DataTable.Cell numeric>
                    {staffDetails.currentWeek.scheduledHours}h
                  </DataTable.Cell>
                </DataTable.Row>
                <DataTable.Row>
                  <DataTable.Cell>Worked Hours</DataTable.Cell>
                  <DataTable.Cell numeric>
                    {staffDetails.currentWeek.workedHours}h
                  </DataTable.Cell>
                </DataTable.Row>
                <DataTable.Row>
                  <DataTable.Cell>Overtime</DataTable.Cell>
                  <DataTable.Cell numeric>
                    {staffDetails.currentWeek.overtimeHours}h
                  </DataTable.Cell>
                </DataTable.Row>
                <DataTable.Row>
                  <DataTable.Cell>Breaks Total</DataTable.Cell>
                  <DataTable.Cell numeric>
                    {staffDetails.currentWeek.breaksTotal}h
                  </DataTable.Cell>
                </DataTable.Row>
              </DataTable>
            </View>
          </List.Accordion>
        </Card>

        <Card style={styles.infoCard}>
          <List.Accordion
            title="Availability"
            expanded={expandedSections.includes('availability')}
            onPress={() => toggleSection('availability')}>
            <View style={styles.availabilityContent}>
              {Object.entries(staffDetails.availability).map(([day, avail]) =>
                renderAvailabilityDay(day, avail),
              )}
            </View>
          </List.Accordion>
        </Card>

        <Card style={styles.infoCard}>
          <List.Accordion
            title="Skills & Certifications"
            expanded={expandedSections.includes('skills')}
            onPress={() => toggleSection('skills')}>
            <View style={styles.skillsContent}>
              <Text variant="titleSmall" style={styles.sectionSubtitle}>
                Skills
              </Text>
              <View style={styles.skillsContainer}>
                {staffDetails.skills.map(skill => (
                  <Chip key={skill} style={styles.skillChip}>
                    {skill}
                  </Chip>
                ))}
              </View>

              <Text variant="titleSmall" style={[styles.sectionSubtitle, { marginTop: 16 }]}>
                Certifications
              </Text>
              {staffDetails.certifications.map(cert => (
                <View key={cert.name} style={styles.certificationRow}>
                  <View style={styles.certificationInfo}>
                    <Text variant="bodyMedium">{cert.name}</Text>
                    <Text variant="bodySmall" style={styles.certExpiry}>
                      Expires: {format(parseISO(cert.expiryDate), 'MMM d, yyyy')}
                    </Text>
                  </View>
                  <Chip
                    mode="flat"
                    compact
                    textStyle={styles.certStatusText}
                    style={[
                      styles.certStatusChip,
                      { backgroundColor: getCertificationColor(cert.status) + '20' },
                    ]}>
                    {cert.status}
                  </Chip>
                </View>
              ))}
            </View>
          </List.Accordion>
        </Card>

        <View style={styles.actions}>
          <Button
            mode="outlined"
            onPress={() =>
              navigation.navigate('StaffSchedule' as any, { staffId })
            }
            style={styles.actionButton}>
            View Schedule
          </Button>
          <Button
            mode="contained"
            onPress={() =>
              navigation.navigate('StaffPayroll' as any, { staffId })
            }
            style={styles.actionButton}>
            Payroll Info
          </Button>
        </View>
      </ScrollView>
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
  profileSection: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  name: {
    marginTop: 12,
    fontWeight: '600',
  },
  role: {
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
  contactSection: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 12,
    marginBottom: 16,
  },
  contactCard: {
    flex: 1,
  },
  contactContent: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
  },
  infoCard: {
    marginHorizontal: 16,
    marginBottom: 12,
  },
  infoContent: {
    padding: 16,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  infoLabel: {
    color: '#64748b',
    flex: 1,
  },
  infoValue: {
    flex: 2,
    textAlign: 'right',
  },
  emergencyInfo: {
    color: '#64748b',
    marginTop: 4,
  },
  divider: {
    marginVertical: 8,
  },
  performanceContent: {
    padding: 16,
  },
  metricItem: {
    marginBottom: 16,
  },
  metricHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  metricValue: {
    fontWeight: '600',
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
  },
  scheduleContent: {
    paddingHorizontal: 16,
  },
  availabilityContent: {
    padding: 16,
  },
  availabilityRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  dayLabel: {
    flex: 1,
    fontWeight: '500',
  },
  availabilityTime: {
    color: '#059669',
  },
  unavailable: {
    color: '#94a3b8',
    fontStyle: 'italic',
  },
  skillsContent: {
    padding: 16,
  },
  sectionSubtitle: {
    marginBottom: 12,
    fontWeight: '600',
  },
  skillsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  skillChip: {
    backgroundColor: '#e0f2fe',
  },
  certificationRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  certificationInfo: {
    flex: 1,
  },
  certExpiry: {
    color: '#64748b',
    marginTop: 2,
  },
  certStatusChip: {
    height: 24,
  },
  certStatusText: {
    fontSize: 11,
    textTransform: 'capitalize',
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
});