import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
  TouchableOpacity,
} from 'react-native';
import {
  Text,
  List,
  Switch,
  useTheme,
  Divider,
  Portal,
  Modal,
  TextInput,
  Button,
  RadioButton,
  Chip,
  Avatar,
  IconButton,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '@hooks/useAuth';
import { useOffline } from '@hooks/useOffline';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DeviceInfo from 'react-native-device-info';

interface UserPreferences {
  notifications: {
    enabled: boolean;
    orderUpdates: boolean;
    staffAlerts: boolean;
    inventoryAlerts: boolean;
    promotions: boolean;
    sound: boolean;
    vibration: boolean;
    groupSimilar: boolean;
    quietHours: {
      enabled: boolean;
      start: string;
      end: string;
    };
    priority: {
      orders: 'high' | 'medium' | 'low';
      staff: 'high' | 'medium' | 'low';
      inventory: 'high' | 'medium' | 'low';
    };
  };
  display: {
    theme: 'light' | 'dark' | 'system';
    compactMode: boolean;
    showImages: boolean;
  };
  sync: {
    autoSync: boolean;
    syncInterval: number;
    wifiOnly: boolean;
    backgroundSync: boolean;
  };
  privacy: {
    biometricLogin: boolean;
    autoLogout: boolean;
    autoLogoutTime: number;
    analyticsEnabled: boolean;
  };
  offline: {
    dataRetention: number;
    cacheSize: number;
    autoCleanup: boolean;
    queueActions: boolean;
    offlineFeatures: {
      orders: boolean;
      inventory: boolean;
      staff: boolean;
      menu: boolean;
    };
    maxOfflineOrders: number;
    maxOfflineItems: number;
  };
  sync: {
    autoSync: boolean;
    syncInterval: number;
    wifiOnly: boolean;
    backgroundSync: boolean;
    conflictResolution: 'local' | 'server';
  };
}

export const SettingsScreen: React.FC = () => {
  const theme = useTheme();
  const navigation = useNavigation();
  const { user, logout } = useAuth();
  const { isOffline, syncStatus } = useOffline();
  
  const [preferences, setPreferences] = useState<UserPreferences>({
    notifications: {
      enabled: true,
      orderUpdates: true,
      staffAlerts: true,
      inventoryAlerts: true,
      promotions: false,
      sound: true,
      vibration: true,
      groupSimilar: true,
      quietHours: {
        enabled: false,
        start: '22:00',
        end: '07:00',
      },
      priority: {
        orders: 'high',
        staff: 'medium',
        inventory: 'low',
      },
    },
    display: {
      theme: 'system',
      compactMode: false,
      showImages: true,
    },
    sync: {
      autoSync: true,
      syncInterval: 15,
      wifiOnly: false,
      backgroundSync: true,
    },
    privacy: {
      biometricLogin: false,
      autoLogout: true,
      autoLogoutTime: 30,
      analyticsEnabled: true,
    },
    offline: {
      dataRetention: 7,
      cacheSize: 100,
      autoCleanup: true,
      queueActions: true,
      offlineFeatures: {
        orders: true,
        inventory: true,
        staff: true,
        menu: true,
      },
      maxOfflineOrders: 100,
      maxOfflineItems: 500,
    },
  });

  const [expandedSections, setExpandedSections] = useState<string[]>(['account']);
  const [showThemeModal, setShowThemeModal] = useState(false);
  const [showSyncIntervalModal, setShowSyncIntervalModal] = useState(false);
  const [showLogoutTimeModal, setShowLogoutTimeModal] = useState(false);
  const [showRetentionModal, setShowRetentionModal] = useState(false);
  const [showNotificationScheduleModal, setShowNotificationScheduleModal] = useState(false);
  const [showNotificationPriorityModal, setShowNotificationPriorityModal] = useState(false);
  const [showOfflineSettingsModal, setShowOfflineSettingsModal] = useState(false);

  const toggleSection = (section: string) => {
    setExpandedSections(prev =>
      prev.includes(section)
        ? prev.filter(s => s !== section)
        : [...prev, section],
    );
  };

  const updatePreference = (
    category: keyof UserPreferences,
    key: string,
    value: any,
  ) => {
    setPreferences(prev => ({
      ...prev,
      [category]: {
        ...prev[category],
        [key]: value,
      },
    }));
    
    // Save to AsyncStorage
    AsyncStorage.setItem(
      `preferences.${category}.${key}`,
      JSON.stringify(value),
    );
  };

  const handleLogout = () => {
    Alert.alert(
      'Logout',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: () => logout(),
        },
      ],
    );
  };

  const clearCache = () => {
    Alert.alert(
      'Clear Cache',
      'This will remove all cached data. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            // TODO: Implement cache clearing
            await AsyncStorage.clear();
            Alert.alert('Success', 'Cache cleared successfully');
          },
        },
      ],
    );
  };

  const renderAccountSection = () => (
    <List.Accordion
      title="Account"
      expanded={expandedSections.includes('account')}
      onPress={() => toggleSection('account')}
      left={props => <List.Icon {...props} icon="account" />}>
      <View style={styles.sectionContent}>
        <TouchableOpacity style={styles.accountInfo}>
          <Avatar.Text
            size={64}
            label={user?.name?.split(' ').map(n => n[0]).join('') || 'U'}
            style={{ backgroundColor: theme.colors.primaryContainer }}
          />
          <View style={styles.accountDetails}>
            <Text variant="titleMedium">{user?.name || 'User'}</Text>
            <Text variant="bodyMedium" style={styles.accountEmail}>
              {user?.email || 'user@example.com'}
            </Text>
            <Chip style={styles.roleChip}>{user?.role || 'Staff'}</Chip>
          </View>
        </TouchableOpacity>

        <Divider style={styles.divider} />

        <TouchableOpacity
          style={styles.listItem}
          onPress={() => navigation.navigate('EditProfile' as any)}>
          <Text variant="bodyLarge">Edit Profile</Text>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.listItem}
          onPress={() => navigation.navigate('ChangePassword' as any)}>
          <Text variant="bodyLarge">Change Password</Text>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <TouchableOpacity style={styles.listItem} onPress={handleLogout}>
          <Text variant="bodyLarge" style={{ color: theme.colors.error }}>
            Logout
          </Text>
          <IconButton icon="logout" size={20} iconColor={theme.colors.error} />
        </TouchableOpacity>
      </View>
    </List.Accordion>
  );

  const renderNotificationSettings = () => (
    <List.Accordion
      title="Notifications"
      expanded={expandedSections.includes('notifications')}
      onPress={() => toggleSection('notifications')}
      left={props => <List.Icon {...props} icon="bell" />}>
      <View style={styles.sectionContent}>
        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Enable Notifications</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Receive push notifications
            </Text>
          </View>
          <Switch
            value={preferences.notifications.enabled}
            onValueChange={value =>
              updatePreference('notifications', 'enabled', value)
            }
          />
        </View>

        <Divider style={styles.divider} />

        <Text variant="titleSmall" style={styles.subsectionTitle}>
          Notification Types
        </Text>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyMedium">Order Updates</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              New orders, status changes, cancellations
            </Text>
          </View>
          <Switch
            value={preferences.notifications.orderUpdates}
            onValueChange={value =>
              updatePreference('notifications', 'orderUpdates', value)
            }
            disabled={!preferences.notifications.enabled}
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyMedium">Staff Alerts</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Schedule changes, attendance, messages
            </Text>
          </View>
          <Switch
            value={preferences.notifications.staffAlerts}
            onValueChange={value =>
              updatePreference('notifications', 'staffAlerts', value)
            }
            disabled={!preferences.notifications.enabled}
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyMedium">Inventory Alerts</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Low stock, expiring items, reorder reminders
            </Text>
          </View>
          <Switch
            value={preferences.notifications.inventoryAlerts}
            onValueChange={value =>
              updatePreference('notifications', 'inventoryAlerts', value)
            }
            disabled={!preferences.notifications.enabled}
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyMedium">Promotions</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Marketing campaigns, special offers
            </Text>
          </View>
          <Switch
            value={preferences.notifications.promotions}
            onValueChange={value =>
              updatePreference('notifications', 'promotions', value)
            }
            disabled={!preferences.notifications.enabled}
          />
        </View>

        <Divider style={styles.divider} />

        <Text variant="titleSmall" style={styles.subsectionTitle}>
          Notification Preferences
        </Text>

        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => setShowNotificationScheduleModal(true)}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Quiet Hours</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              {preferences.notifications.quietHours.enabled
                ? `${preferences.notifications.quietHours.start} - ${preferences.notifications.quietHours.end}`
                : 'No quiet hours set'}
            </Text>
          </View>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => setShowNotificationPriorityModal(true)}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Priority Settings</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Customize notification importance
            </Text>
          </View>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyMedium">Sound</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Play notification sounds
            </Text>
          </View>
          <Switch
            value={preferences.notifications.sound}
            onValueChange={value =>
              updatePreference('notifications', 'sound', value)
            }
            disabled={!preferences.notifications.enabled}
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyMedium">Vibration</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Vibrate on notifications
            </Text>
          </View>
          <Switch
            value={preferences.notifications.vibration}
            onValueChange={value =>
              updatePreference('notifications', 'vibration', value)
            }
            disabled={!preferences.notifications.enabled}
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyMedium">Group Similar</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Bundle similar notifications together
            </Text>
          </View>
          <Switch
            value={preferences.notifications.groupSimilar}
            onValueChange={value =>
              updatePreference('notifications', 'groupSimilar', value)
            }
            disabled={!preferences.notifications.enabled}
          />
        </View>
      </View>
    </List.Accordion>
  );

  const renderDisplaySettings = () => (
    <List.Accordion
      title="Display"
      expanded={expandedSections.includes('display')}
      onPress={() => toggleSection('display')}
      left={props => <List.Icon {...props} icon="palette" />}>
      <View style={styles.sectionContent}>
        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => setShowThemeModal(true)}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Theme</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              {preferences.display.theme === 'system'
                ? 'System Default'
                : preferences.display.theme === 'light'
                ? 'Light'
                : 'Dark'}
            </Text>
          </View>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Compact Mode</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Show more items on screen
            </Text>
          </View>
          <Switch
            value={preferences.display.compactMode}
            onValueChange={value =>
              updatePreference('display', 'compactMode', value)
            }
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Show Images</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Display product images
            </Text>
          </View>
          <Switch
            value={preferences.display.showImages}
            onValueChange={value =>
              updatePreference('display', 'showImages', value)
            }
          />
        </View>
      </View>
    </List.Accordion>
  );

  const renderSyncSettings = () => (
    <List.Accordion
      title="Sync & Offline"
      expanded={expandedSections.includes('sync')}
      onPress={() => toggleSection('sync')}
      left={props => <List.Icon {...props} icon="sync" />}>
      <View style={styles.sectionContent}>
        <View style={styles.syncStatus}>
          <Text variant="bodyMedium">
            Status: {isOffline ? 'Offline' : 'Online'}
          </Text>
          {syncStatus && (
            <Chip compact style={styles.syncChip}>
              {syncStatus}
            </Chip>
          )}
        </View>

        <Divider style={styles.divider} />

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Auto Sync</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Sync data automatically
            </Text>
          </View>
          <Switch
            value={preferences.sync.autoSync}
            onValueChange={value => updatePreference('sync', 'autoSync', value)}
          />
        </View>

        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => setShowSyncIntervalModal(true)}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Sync Interval</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Every {preferences.sync.syncInterval} minutes
            </Text>
          </View>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">WiFi Only</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Sync only on WiFi connection
            </Text>
          </View>
          <Switch
            value={preferences.sync.wifiOnly}
            onValueChange={value => updatePreference('sync', 'wifiOnly', value)}
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Background Sync</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Sync when app is in background
            </Text>
          </View>
          <Switch
            value={preferences.sync.backgroundSync}
            onValueChange={value =>
              updatePreference('sync', 'backgroundSync', value)
            }
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Conflict Resolution</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              {preferences.sync.conflictResolution === 'local' ? 'Prefer local changes' : 'Prefer server changes'}
            </Text>
          </View>
          <IconButton 
            icon="chevron-right" 
            size={20}
            onPress={() => {
              Alert.alert(
                'Conflict Resolution',
                'Choose how to handle sync conflicts',
                [
                  { text: 'Prefer Local', onPress: () => updatePreference('sync', 'conflictResolution', 'local') },
                  { text: 'Prefer Server', onPress: () => updatePreference('sync', 'conflictResolution', 'server') },
                  { text: 'Cancel', style: 'cancel' },
                ],
              );
            }}
          />
        </View>

        <Divider style={styles.divider} />

        <Text variant="titleSmall" style={styles.subsectionTitle}>
          Offline Mode
        </Text>

        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => setShowOfflineSettingsModal(true)}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Offline Settings</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Configure offline data and features
            </Text>
          </View>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => setShowRetentionModal(true)}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Data Retention</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Keep data for {preferences.offline.dataRetention} days
            </Text>
          </View>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Auto Cleanup</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Remove old offline data
            </Text>
          </View>
          <Switch
            value={preferences.offline.autoCleanup}
            onValueChange={value =>
              updatePreference('offline', 'autoCleanup', value)
            }
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Queue Actions</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Queue actions when offline
            </Text>
          </View>
          <Switch
            value={preferences.offline.queueActions}
            onValueChange={value =>
              updatePreference('offline', 'queueActions', value)
            }
          />
        </View>

        <TouchableOpacity style={styles.actionButton} onPress={clearCache}>
          <Text variant="bodyLarge" style={{ color: theme.colors.primary }}>
            Clear Cache
          </Text>
          <Text variant="bodySmall" style={styles.cacheSize}>
            {preferences.offline.cacheSize} MB used
          </Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.actionButton} 
          onPress={() => Alert.alert('Sync Now', 'Manual sync initiated')}>
          <Text variant="bodyLarge" style={{ color: theme.colors.primary }}>
            Sync Now
          </Text>
          <Text variant="bodySmall" style={styles.cacheSize}>
            Last synced: 5 mins ago
          </Text>
        </TouchableOpacity>
      </View>
    </List.Accordion>
  );

  const renderPrivacySettings = () => (
    <List.Accordion
      title="Privacy & Security"
      expanded={expandedSections.includes('privacy')}
      onPress={() => toggleSection('privacy')}
      left={props => <List.Icon {...props} icon="shield-lock" />}>
      <View style={styles.sectionContent}>
        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Biometric Login</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Use fingerprint or face ID
            </Text>
          </View>
          <Switch
            value={preferences.privacy.biometricLogin}
            onValueChange={value =>
              updatePreference('privacy', 'biometricLogin', value)
            }
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Auto Logout</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Logout after inactivity
            </Text>
          </View>
          <Switch
            value={preferences.privacy.autoLogout}
            onValueChange={value =>
              updatePreference('privacy', 'autoLogout', value)
            }
          />
        </View>

        <TouchableOpacity
          style={styles.settingItem}
          onPress={() => setShowLogoutTimeModal(true)}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Auto Logout Time</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              After {preferences.privacy.autoLogoutTime} minutes
            </Text>
          </View>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Analytics</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Help improve the app
            </Text>
          </View>
          <Switch
            value={preferences.privacy.analyticsEnabled}
            onValueChange={value =>
              updatePreference('privacy', 'analyticsEnabled', value)
            }
          />
        </View>
      </View>
    </List.Accordion>
  );

  const renderAboutSection = () => (
    <List.Accordion
      title="About"
      expanded={expandedSections.includes('about')}
      onPress={() => toggleSection('about')}
      left={props => <List.Icon {...props} icon="information" />}>
      <View style={styles.sectionContent}>
        <View style={styles.aboutItem}>
          <Text variant="bodyMedium" style={styles.aboutLabel}>
            Version
          </Text>
          <Text variant="bodyMedium">{DeviceInfo.getVersion()}</Text>
        </View>

        <View style={styles.aboutItem}>
          <Text variant="bodyMedium" style={styles.aboutLabel}>
            Build
          </Text>
          <Text variant="bodyMedium">{DeviceInfo.getBuildNumber()}</Text>
        </View>

        <Divider style={styles.divider} />

        <TouchableOpacity
          style={styles.listItem}
          onPress={() => navigation.navigate('TermsOfService' as any)}>
          <Text variant="bodyLarge">Terms of Service</Text>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.listItem}
          onPress={() => navigation.navigate('PrivacyPolicy' as any)}>
          <Text variant="bodyLarge">Privacy Policy</Text>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.listItem}
          onPress={() => navigation.navigate('Support' as any)}>
          <Text variant="bodyLarge">Support</Text>
          <IconButton icon="chevron-right" size={20} />
        </TouchableOpacity>
      </View>
    </List.Accordion>
  );

  const renderThemeModal = () => (
    <Portal>
      <Modal
        visible={showThemeModal}
        onDismiss={() => setShowThemeModal(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Choose Theme
        </Text>
        <RadioButton.Group
          onValueChange={value => {
            updatePreference('display', 'theme', value);
            setShowThemeModal(false);
          }}
          value={preferences.display.theme}>
          <RadioButton.Item label="System Default" value="system" />
          <RadioButton.Item label="Light" value="light" />
          <RadioButton.Item label="Dark" value="dark" />
        </RadioButton.Group>
      </Modal>
    </Portal>
  );

  const renderSyncIntervalModal = () => (
    <Portal>
      <Modal
        visible={showSyncIntervalModal}
        onDismiss={() => setShowSyncIntervalModal(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Sync Interval
        </Text>
        <RadioButton.Group
          onValueChange={value => {
            updatePreference('sync', 'syncInterval', parseInt(value));
            setShowSyncIntervalModal(false);
          }}
          value={preferences.sync.syncInterval.toString()}>
          <RadioButton.Item label="Every 5 minutes" value="5" />
          <RadioButton.Item label="Every 15 minutes" value="15" />
          <RadioButton.Item label="Every 30 minutes" value="30" />
          <RadioButton.Item label="Every hour" value="60" />
        </RadioButton.Group>
      </Modal>
    </Portal>
  );

  const renderNotificationScheduleModal = () => (
    <Portal>
      <Modal
        visible={showNotificationScheduleModal}
        onDismiss={() => setShowNotificationScheduleModal(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Quiet Hours
        </Text>
        
        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Text variant="bodyLarge">Enable Quiet Hours</Text>
            <Text variant="bodySmall" style={styles.settingDescription}>
              Mute notifications during specified times
            </Text>
          </View>
          <Switch
            value={preferences.notifications.quietHours.enabled}
            onValueChange={value => 
              setPreferences(prev => ({
                ...prev,
                notifications: {
                  ...prev.notifications,
                  quietHours: {
                    ...prev.notifications.quietHours,
                    enabled: value,
                  },
                },
              }))
            }
          />
        </View>

        <Divider style={styles.divider} />

        <View style={styles.timeSelectors}>
          <TouchableOpacity 
            style={styles.timeSelector}
            disabled={!preferences.notifications.quietHours.enabled}>
            <Text variant="bodyMedium" style={styles.timeLabel}>Start Time</Text>
            <Text variant="bodyLarge" style={styles.timeValue}>
              {preferences.notifications.quietHours.start}
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={styles.timeSelector}
            disabled={!preferences.notifications.quietHours.enabled}>
            <Text variant="bodyMedium" style={styles.timeLabel}>End Time</Text>
            <Text variant="bodyLarge" style={styles.timeValue}>
              {preferences.notifications.quietHours.end}
            </Text>
          </TouchableOpacity>
        </View>

        <Button 
          mode="contained" 
          onPress={() => setShowNotificationScheduleModal(false)}
          style={styles.modalButton}>
          Done
        </Button>
      </Modal>
    </Portal>
  );

  const renderNotificationPriorityModal = () => (
    <Portal>
      <Modal
        visible={showNotificationPriorityModal}
        onDismiss={() => setShowNotificationPriorityModal(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Notification Priority
        </Text>
        
        <Text variant="bodyMedium" style={styles.modalSubtitle}>
          Set priority levels for different notification types
        </Text>

        <View style={styles.prioritySection}>
          <Text variant="titleSmall" style={styles.priorityTitle}>
            Order Notifications
          </Text>
          <RadioButton.Group
            onValueChange={value => 
              setPreferences(prev => ({
                ...prev,
                notifications: {
                  ...prev.notifications,
                  priority: {
                    ...prev.notifications.priority,
                    orders: value as 'high' | 'medium' | 'low',
                  },
                },
              }))
            }
            value={preferences.notifications.priority.orders}>
            <View style={styles.priorityOptions}>
              <RadioButton.Item label="High" value="high" mode="android" />
              <RadioButton.Item label="Medium" value="medium" mode="android" />
              <RadioButton.Item label="Low" value="low" mode="android" />
            </View>
          </RadioButton.Group>
        </View>

        <View style={styles.prioritySection}>
          <Text variant="titleSmall" style={styles.priorityTitle}>
            Staff Notifications
          </Text>
          <RadioButton.Group
            onValueChange={value => 
              setPreferences(prev => ({
                ...prev,
                notifications: {
                  ...prev.notifications,
                  priority: {
                    ...prev.notifications.priority,
                    staff: value as 'high' | 'medium' | 'low',
                  },
                },
              }))
            }
            value={preferences.notifications.priority.staff}>
            <View style={styles.priorityOptions}>
              <RadioButton.Item label="High" value="high" mode="android" />
              <RadioButton.Item label="Medium" value="medium" mode="android" />
              <RadioButton.Item label="Low" value="low" mode="android" />
            </View>
          </RadioButton.Group>
        </View>

        <View style={styles.prioritySection}>
          <Text variant="titleSmall" style={styles.priorityTitle}>
            Inventory Notifications
          </Text>
          <RadioButton.Group
            onValueChange={value => 
              setPreferences(prev => ({
                ...prev,
                notifications: {
                  ...prev.notifications,
                  priority: {
                    ...prev.notifications.priority,
                    inventory: value as 'high' | 'medium' | 'low',
                  },
                },
              }))
            }
            value={preferences.notifications.priority.inventory}>
            <View style={styles.priorityOptions}>
              <RadioButton.Item label="High" value="high" mode="android" />
              <RadioButton.Item label="Medium" value="medium" mode="android" />
              <RadioButton.Item label="Low" value="low" mode="android" />
            </View>
          </RadioButton.Group>
        </View>

        <Button 
          mode="contained" 
          onPress={() => setShowNotificationPriorityModal(false)}
          style={styles.modalButton}>
          Save
        </Button>
      </Modal>
    </Portal>
  );

  const renderOfflineSettingsModal = () => (
    <Portal>
      <Modal
        visible={showOfflineSettingsModal}
        onDismiss={() => setShowOfflineSettingsModal(false)}
        contentContainerStyle={[styles.modalContent, styles.largeModal]}>
        <ScrollView>
          <Text variant="headlineSmall" style={styles.modalTitle}>
            Offline Settings
          </Text>
          
          <Text variant="titleSmall" style={styles.subsectionTitle}>
            Offline Features
          </Text>

          <View style={styles.settingItem}>
            <View style={styles.settingInfo}>
              <Text variant="bodyLarge">Orders</Text>
              <Text variant="bodySmall" style={styles.settingDescription}>
                Create and manage orders offline
              </Text>
            </View>
            <Switch
              value={preferences.offline.offlineFeatures.orders}
              onValueChange={value => 
                setPreferences(prev => ({
                  ...prev,
                  offline: {
                    ...prev.offline,
                    offlineFeatures: {
                      ...prev.offline.offlineFeatures,
                      orders: value,
                    },
                  },
                }))
              }
            />
          </View>

          <View style={styles.settingItem}>
            <View style={styles.settingInfo}>
              <Text variant="bodyLarge">Inventory</Text>
              <Text variant="bodySmall" style={styles.settingDescription}>
                Update inventory counts offline
              </Text>
            </View>
            <Switch
              value={preferences.offline.offlineFeatures.inventory}
              onValueChange={value => 
                setPreferences(prev => ({
                  ...prev,
                  offline: {
                    ...prev.offline,
                    offlineFeatures: {
                      ...prev.offline.offlineFeatures,
                      inventory: value,
                    },
                  },
                }))
              }
            />
          </View>

          <View style={styles.settingItem}>
            <View style={styles.settingInfo}>
              <Text variant="bodyLarge">Staff Management</Text>
              <Text variant="bodySmall" style={styles.settingDescription}>
                View staff schedules offline
              </Text>
            </View>
            <Switch
              value={preferences.offline.offlineFeatures.staff}
              onValueChange={value => 
                setPreferences(prev => ({
                  ...prev,
                  offline: {
                    ...prev.offline,
                    offlineFeatures: {
                      ...prev.offline.offlineFeatures,
                      staff: value,
                    },
                  },
                }))
              }
            />
          </View>

          <View style={styles.settingItem}>
            <View style={styles.settingInfo}>
              <Text variant="bodyLarge">Menu</Text>
              <Text variant="bodySmall" style={styles.settingDescription}>
                Browse menu items offline
              </Text>
            </View>
            <Switch
              value={preferences.offline.offlineFeatures.menu}
              onValueChange={value => 
                setPreferences(prev => ({
                  ...prev,
                  offline: {
                    ...prev.offline,
                    offlineFeatures: {
                      ...prev.offline.offlineFeatures,
                      menu: value,
                    },
                  },
                }))
              }
            />
          </View>

          <Divider style={styles.divider} />

          <Text variant="titleSmall" style={styles.subsectionTitle}>
            Storage Limits
          </Text>

          <View style={styles.sliderContainer}>
            <Text variant="bodyMedium">Max Offline Orders</Text>
            <View style={styles.sliderRow}>
              <Text variant="bodySmall" style={styles.sliderValue}>
                {preferences.offline.maxOfflineOrders}
              </Text>
              <View style={styles.sliderTrack} />
            </View>
          </View>

          <View style={styles.sliderContainer}>
            <Text variant="bodyMedium">Max Offline Items</Text>
            <View style={styles.sliderRow}>
              <Text variant="bodySmall" style={styles.sliderValue}>
                {preferences.offline.maxOfflineItems}
              </Text>
              <View style={styles.sliderTrack} />
            </View>
          </View>

          <Divider style={styles.divider} />

          <View style={styles.offlineStats}>
            <Text variant="titleSmall" style={styles.subsectionTitle}>
              Offline Data Usage
            </Text>
            <View style={styles.statRow}>
              <Text variant="bodyMedium">Orders cached:</Text>
              <Text variant="bodyMedium">23</Text>
            </View>
            <View style={styles.statRow}>
              <Text variant="bodyMedium">Menu items cached:</Text>
              <Text variant="bodyMedium">156</Text>
            </View>
            <View style={styles.statRow}>
              <Text variant="bodyMedium">Total size:</Text>
              <Text variant="bodyMedium">47.3 MB</Text>
            </View>
          </View>

          <Button 
            mode="contained" 
            onPress={() => setShowOfflineSettingsModal(false)}
            style={styles.modalButton}>
            Done
          </Button>
        </ScrollView>
      </Modal>
    </Portal>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          Settings
        </Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        <List.Section>
          {renderAccountSection()}
          {renderNotificationSettings()}
          {renderDisplaySettings()}
          {renderSyncSettings()}
          {renderPrivacySettings()}
          {renderAboutSection()}
        </List.Section>
      </ScrollView>

      {renderThemeModal()}
      {renderSyncIntervalModal()}
      {renderNotificationScheduleModal()}
      {renderNotificationPriorityModal()}
      {renderOfflineSettingsModal()}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
  title: {
    fontWeight: 'bold',
  },
  sectionContent: {
    backgroundColor: 'white',
    paddingVertical: 8,
  },
  accountInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  accountDetails: {
    marginLeft: 16,
    flex: 1,
  },
  accountEmail: {
    color: '#64748b',
    marginTop: 2,
  },
  roleChip: {
    alignSelf: 'flex-start',
    marginTop: 8,
  },
  listItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  settingInfo: {
    flex: 1,
    marginRight: 16,
  },
  settingDescription: {
    color: '#64748b',
    marginTop: 2,
  },
  divider: {
    marginVertical: 8,
  },
  subsectionTitle: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    fontWeight: '600',
    color: '#64748b',
  },
  syncStatus: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  syncChip: {
    backgroundColor: '#e0f2fe',
  },
  actionButton: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  cacheSize: {
    color: '#64748b',
    marginTop: 2,
  },
  aboutItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  aboutLabel: {
    color: '#64748b',
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
  largeModal: {
    maxHeight: '80%',
  },
  timeSelectors: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginVertical: 24,
  },
  timeSelector: {
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#f1f5f9',
    borderRadius: 8,
    minWidth: 120,
  },
  timeLabel: {
    color: '#64748b',
    marginBottom: 8,
  },
  timeValue: {
    fontWeight: '600',
  },
  prioritySection: {
    marginBottom: 24,
  },
  priorityTitle: {
    marginBottom: 8,
    fontWeight: '600',
  },
  priorityOptions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  sliderContainer: {
    marginVertical: 12,
  },
  sliderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  sliderValue: {
    minWidth: 40,
    color: '#64748b',
  },
  sliderTrack: {
    flex: 1,
    height: 4,
    backgroundColor: '#e2e8f0',
    borderRadius: 2,
    marginLeft: 12,
  },
  offlineStats: {
    marginTop: 16,
  },
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
});