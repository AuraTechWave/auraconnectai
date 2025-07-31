import React from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Text, Card, useTheme, IconButton } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { useAuth } from '@hooks/useAuth';
import { useOffline } from '@hooks/useOffline';

export const DashboardScreen: React.FC = () => {
  const theme = useTheme();
  const { user } = useAuth();
  const { isOnline, queueSize } = useOffline();

  const metrics = [
    { title: 'Today\'s Sales', value: '$2,345', icon: 'cash-multiple', color: '#10b981' },
    { title: 'Active Orders', value: '12', icon: 'receipt', color: '#3b82f6' },
    { title: 'Staff on Duty', value: '8', icon: 'account-group', color: '#8b5cf6' },
    { title: 'Menu Items', value: '156', icon: 'food-variant', color: '#f59e0b' },
  ];

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text variant="headlineMedium" style={styles.greeting}>
            Welcome back, {user?.full_name || 'User'}!
          </Text>
          <Text variant="bodyLarge" style={styles.subtitle}>
            Here's your restaurant overview
          </Text>
        </View>
        <View style={styles.statusContainer}>
          <Icon
            name={isOnline ? 'wifi' : 'wifi-off'}
            size={20}
            color={isOnline ? theme.colors.primary : theme.colors.error}
          />
          {!isOnline && queueSize > 0 && (
            <Text style={styles.queueBadge}>{queueSize}</Text>
          )}
        </View>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}>
        <View style={styles.metricsGrid}>
          {metrics.map((metric, index) => (
            <Card key={index} style={styles.metricCard}>
              <Card.Content style={styles.metricContent}>
                <View
                  style={[
                    styles.iconContainer,
                    { backgroundColor: `${metric.color}20` },
                  ]}>
                  <Icon name={metric.icon} size={24} color={metric.color} />
                </View>
                <Text variant="bodyMedium" style={styles.metricTitle}>
                  {metric.title}
                </Text>
                <Text variant="headlineSmall" style={styles.metricValue}>
                  {metric.value}
                </Text>
              </Card.Content>
            </Card>
          ))}
        </View>

        <Card style={styles.quickActionsCard}>
          <Card.Title title="Quick Actions" />
          <Card.Content>
            <View style={styles.quickActions}>
              <View style={styles.quickAction}>
                <IconButton
                  icon="plus-circle"
                  size={40}
                  iconColor={theme.colors.primary}
                  onPress={() => {}}
                />
                <Text variant="bodySmall">New Order</Text>
              </View>
              <View style={styles.quickAction}>
                <IconButton
                  icon="account-plus"
                  size={40}
                  iconColor={theme.colors.secondary}
                  onPress={() => {}}
                />
                <Text variant="bodySmall">Add Staff</Text>
              </View>
              <View style={styles.quickAction}>
                <IconButton
                  icon="food"
                  size={40}
                  iconColor={theme.colors.tertiary}
                  onPress={() => {}}
                />
                <Text variant="bodySmall">Menu Item</Text>
              </View>
              <View style={styles.quickAction}>
                <IconButton
                  icon="chart-line"
                  size={40}
                  iconColor="#10b981"
                  onPress={() => {}}
                />
                <Text variant="bodySmall">Reports</Text>
              </View>
            </View>
          </Card.Content>
        </Card>

        <Card style={styles.recentActivityCard}>
          <Card.Title title="Recent Activity" />
          <Card.Content>
            <Text variant="bodyMedium" style={styles.activityItem}>
              • New order #1234 received - 5 min ago
            </Text>
            <Text variant="bodyMedium" style={styles.activityItem}>
              • Staff member John clocked in - 15 min ago
            </Text>
            <Text variant="bodyMedium" style={styles.activityItem}>
              • Menu item "Special Burger" updated - 1 hr ago
            </Text>
          </Card.Content>
        </Card>
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
    alignItems: 'flex-start',
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
  greeting: {
    fontWeight: 'bold',
  },
  subtitle: {
    opacity: 0.7,
    marginTop: 4,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  queueBadge: {
    backgroundColor: '#ef4444',
    color: '#fff',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
    fontSize: 12,
    marginLeft: 8,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  metricCard: {
    width: '48%',
    marginBottom: 16,
  },
  metricContent: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  metricTitle: {
    opacity: 0.7,
    marginBottom: 4,
  },
  metricValue: {
    fontWeight: 'bold',
  },
  quickActionsCard: {
    marginBottom: 16,
  },
  quickActions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  quickAction: {
    alignItems: 'center',
  },
  recentActivityCard: {
    marginBottom: 16,
  },
  activityItem: {
    marginBottom: 8,
    lineHeight: 20,
  },
});