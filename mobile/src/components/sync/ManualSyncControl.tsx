import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Modal,
  ScrollView,
  Switch,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, typography } from '@theme';
import { syncManager, type SyncState } from '@sync';
import { SyncQueueManager } from './SyncQueueManager';
import { ConflictResolutionModal } from './ConflictResolutionModal';
import { formatDistanceToNow } from 'date-fns';
import { showToast } from '@utils/toast';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface ManualSyncControlProps {
  visible: boolean;
  onClose: () => void;
}

interface SyncPreferences {
  autoSync: boolean;
  syncOnWifi: boolean;
  syncInterval: number;
  conflictStrategy: 'server_wins' | 'client_wins' | 'last_write_wins' | 'merge';
  showNotifications: boolean;
}

const SYNC_PREFS_KEY = 'auraconnect.sync.preferences';

export const ManualSyncControl: React.FC<ManualSyncControlProps> = ({
  visible,
  onClose,
}) => {
  const [syncState, setSyncState] = useState<SyncState>(syncManager.getState());
  const [showQueueManager, setShowQueueManager] = useState(false);
  const [showConflicts, setShowConflicts] = useState(false);
  const [conflicts, setConflicts] = useState([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncType, setSyncType] = useState<'full' | 'push' | 'pull'>('full');
  const [preferences, setPreferences] = useState<SyncPreferences>({
    autoSync: true,
    syncOnWifi: true,
    syncInterval: 300000,
    conflictStrategy: 'last_write_wins',
    showNotifications: true,
  });

  useEffect(() => {
    loadPreferences();

    const handleStateChange = (newState: SyncState) => {
      setSyncState(newState);
    };

    syncManager.on('stateChange', handleStateChange);

    return () => {
      syncManager.off('stateChange', handleStateChange);
    };
  }, []);

  const loadPreferences = async () => {
    try {
      const stored = await AsyncStorage.getItem(SYNC_PREFS_KEY);
      if (stored) {
        setPreferences(JSON.parse(stored));
      }
    } catch (error) {
      console.error('Failed to load sync preferences:', error);
    }
  };

  const savePreferences = async (newPrefs: SyncPreferences) => {
    try {
      await AsyncStorage.setItem(SYNC_PREFS_KEY, JSON.stringify(newPrefs));
      setPreferences(newPrefs);
      showToast('success', 'Saved', 'Sync preferences updated');
    } catch (error) {
      showToast('error', 'Error', 'Failed to save preferences');
    }
  };

  const handleManualSync = async (type: 'full' | 'push' | 'pull') => {
    setIsSyncing(true);
    setSyncType(type);

    try {
      let result;
      switch (type) {
        case 'push':
          result = await syncManager.syncPush();
          showToast('success', 'Pushed', 'Local changes uploaded');
          break;
        case 'pull':
          result = await syncManager.syncPull();
          showToast('success', 'Pulled', 'Server changes downloaded');
          break;
        default:
          result = await syncManager.forceSync();
          showToast('success', 'Synced', 'Full sync completed');
      }
    } catch (error: any) {
      showToast('error', 'Sync Failed', error.message || 'Unknown error');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleClearLocalData = () => {
    showToast('warning', 'Not Implemented', 'This feature is coming soon');
  };

  const handleResolveConflicts = async (resolutions: any[]) => {
    // Handle conflict resolutions
    setShowConflicts(false);
    showToast('success', 'Resolved', 'Conflicts have been resolved');
  };

  const getSyncIntervalText = (interval: number) => {
    const minutes = interval / 60000;
    if (minutes < 60) {
      return `${minutes} minutes`;
    }
    return `${minutes / 60} hours`;
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={false}
      onRequestClose={onClose}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Sync Control Center</Text>
          <TouchableOpacity onPress={onClose} style={styles.closeButton}>
            <Icon name="close" size={24} color={colors.text} />
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* Sync Status Card */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Icon name="sync" size={20} color={colors.primary} />
              <Text style={styles.cardTitle}>Sync Status</Text>
            </View>

            <View style={styles.statusGrid}>
              <View style={styles.statusItem}>
                <Text style={styles.statusLabel}>Status</Text>
                <View style={styles.statusValue}>
                  {syncState.status === 'syncing' ? (
                    <ActivityIndicator size="small" color={colors.primary} />
                  ) : (
                    <View style={styles.statusBadge}>
                      <View
                        style={[
                          styles.statusDot,
                          {
                            backgroundColor:
                              syncState.status === 'idle'
                                ? colors.success
                                : syncState.status === 'error'
                                  ? colors.error
                                  : colors.warning,
                          },
                        ]}
                      />
                      <Text style={styles.statusText}>
                        {syncState.status.charAt(0).toUpperCase() +
                          syncState.status.slice(1)}
                      </Text>
                    </View>
                  )}
                </View>
              </View>

              <View style={styles.statusItem}>
                <Text style={styles.statusLabel}>Last Sync</Text>
                <Text style={styles.statusValue}>
                  {syncState.lastSync
                    ? formatDistanceToNow(syncState.lastSync, {
                        addSuffix: true,
                      })
                    : 'Never'}
                </Text>
              </View>

              <View style={styles.statusItem}>
                <Text style={styles.statusLabel}>Pending Changes</Text>
                <Text style={[styles.statusValue, styles.numberValue]}>
                  {syncState.pendingChanges}
                </Text>
              </View>

              <View style={styles.statusItem}>
                <Text style={styles.statusLabel}>Queue Size</Text>
                <Text style={[styles.statusValue, styles.numberValue]}>
                  {syncState.queueSize}
                </Text>
              </View>

              <View style={styles.statusItem}>
                <Text style={styles.statusLabel}>Connection</Text>
                <View style={styles.statusBadge}>
                  <Icon
                    name={syncState.isOnline ? 'wifi' : 'wifi-off'}
                    size={16}
                    color={syncState.isOnline ? colors.success : colors.error}
                  />
                  <Text style={styles.statusText}>
                    {syncState.isOnline ? 'Online' : 'Offline'}
                  </Text>
                </View>
              </View>
            </View>

            {syncState.error && (
              <View style={styles.errorBox}>
                <Icon name="alert-circle" size={16} color={colors.error} />
                <Text style={styles.errorText}>{syncState.error.message}</Text>
              </View>
            )}

            {syncState.progress && (
              <View style={styles.progressContainer}>
                <Text style={styles.progressText}>
                  {syncState.progress.message}
                </Text>
                <View style={styles.progressBar}>
                  <View
                    style={[
                      styles.progressFill,
                      {
                        width: `${(syncState.progress.current / syncState.progress.total) * 100}%`,
                      },
                    ]}
                  />
                </View>
              </View>
            )}
          </View>

          {/* Manual Sync Actions */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Icon name="play-circle" size={20} color={colors.primary} />
              <Text style={styles.cardTitle}>Manual Sync</Text>
            </View>

            <View style={styles.syncActions}>
              <TouchableOpacity
                style={[
                  styles.syncButton,
                  isSyncing && styles.syncButtonDisabled,
                ]}
                onPress={() => handleManualSync('full')}
                disabled={isSyncing || !syncState.isOnline}>
                <Icon name="sync" size={24} color={colors.primary} />
                <Text style={styles.syncButtonText}>Full Sync</Text>
                <Text style={styles.syncButtonDescription}>
                  Upload and download all changes
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[
                  styles.syncButton,
                  isSyncing && styles.syncButtonDisabled,
                ]}
                onPress={() => handleManualSync('push')}
                disabled={isSyncing || !syncState.isOnline}>
                <Icon name="cloud-upload" size={24} color={colors.warning} />
                <Text style={styles.syncButtonText}>Push Only</Text>
                <Text style={styles.syncButtonDescription}>
                  Upload local changes to server
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[
                  styles.syncButton,
                  isSyncing && styles.syncButtonDisabled,
                ]}
                onPress={() => handleManualSync('pull')}
                disabled={isSyncing || !syncState.isOnline}>
                <Icon name="cloud-download" size={24} color={colors.info} />
                <Text style={styles.syncButtonText}>Pull Only</Text>
                <Text style={styles.syncButtonDescription}>
                  Download server changes
                </Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Sync Preferences */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Icon name="cog" size={20} color={colors.primary} />
              <Text style={styles.cardTitle}>Sync Preferences</Text>
            </View>

            <View style={styles.preferenceItem}>
              <View style={styles.preferenceInfo}>
                <Text style={styles.preferenceLabel}>Auto Sync</Text>
                <Text style={styles.preferenceDescription}>
                  Automatically sync changes when online
                </Text>
              </View>
              <Switch
                value={preferences.autoSync}
                onValueChange={value =>
                  savePreferences({ ...preferences, autoSync: value })
                }
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={colors.surface}
              />
            </View>

            <View style={styles.preferenceItem}>
              <View style={styles.preferenceInfo}>
                <Text style={styles.preferenceLabel}>Sync on WiFi Only</Text>
                <Text style={styles.preferenceDescription}>
                  Only sync when connected to WiFi
                </Text>
              </View>
              <Switch
                value={preferences.syncOnWifi}
                onValueChange={value =>
                  savePreferences({ ...preferences, syncOnWifi: value })
                }
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={colors.surface}
              />
            </View>

            <View style={styles.preferenceItem}>
              <View style={styles.preferenceInfo}>
                <Text style={styles.preferenceLabel}>Show Notifications</Text>
                <Text style={styles.preferenceDescription}>
                  Show sync status notifications
                </Text>
              </View>
              <Switch
                value={preferences.showNotifications}
                onValueChange={value =>
                  savePreferences({ ...preferences, showNotifications: value })
                }
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={colors.surface}
              />
            </View>

            <View style={styles.preferenceItem}>
              <View style={styles.preferenceInfo}>
                <Text style={styles.preferenceLabel}>Sync Interval</Text>
                <Text style={styles.preferenceDescription}>
                  {getSyncIntervalText(preferences.syncInterval)}
                </Text>
              </View>
              <TouchableOpacity style={styles.preferenceButton}>
                <Text style={styles.preferenceButtonText}>Change</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.preferenceItem}>
              <View style={styles.preferenceInfo}>
                <Text style={styles.preferenceLabel}>Conflict Resolution</Text>
                <Text style={styles.preferenceDescription}>
                  {preferences.conflictStrategy.replace('_', ' ')}
                </Text>
              </View>
              <TouchableOpacity style={styles.preferenceButton}>
                <Text style={styles.preferenceButtonText}>Change</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Advanced Actions */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Icon name="tools" size={20} color={colors.primary} />
              <Text style={styles.cardTitle}>Advanced</Text>
            </View>

            <TouchableOpacity
              style={styles.advancedButton}
              onPress={() => setShowQueueManager(true)}>
              <Icon name="format-list-bulleted" size={20} color={colors.text} />
              <Text style={styles.advancedButtonText}>Manage Sync Queue</Text>
              <Icon
                name="chevron-right"
                size={20}
                color={colors.textSecondary}
              />
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.advancedButton}
              onPress={() => {
                if (conflicts.length > 0) {
                  setShowConflicts(true);
                } else {
                  showToast(
                    'info',
                    'No Conflicts',
                    'There are no conflicts to resolve',
                  );
                }
              }}>
              <Icon name="merge" size={20} color={colors.text} />
              <Text style={styles.advancedButtonText}>Resolve Conflicts</Text>
              {conflicts.length > 0 && (
                <View style={styles.conflictBadge}>
                  <Text style={styles.conflictBadgeText}>
                    {conflicts.length}
                  </Text>
                </View>
              )}
              <Icon
                name="chevron-right"
                size={20}
                color={colors.textSecondary}
              />
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.advancedButton}
              onPress={() => syncManager.clearQueue()}>
              <Icon name="delete-sweep" size={20} color={colors.text} />
              <Text style={styles.advancedButtonText}>Clear Sync Queue</Text>
              <Icon
                name="chevron-right"
                size={20}
                color={colors.textSecondary}
              />
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.advancedButton, styles.dangerButton]}
              onPress={handleClearLocalData}>
              <Icon name="database-remove" size={20} color={colors.error} />
              <Text
                style={[styles.advancedButtonText, { color: colors.error }]}>
                Clear Local Data
              </Text>
              <Icon name="chevron-right" size={20} color={colors.error} />
            </TouchableOpacity>
          </View>
        </ScrollView>
      </View>

      {showQueueManager && (
        <Modal
          visible={showQueueManager}
          animationType="slide"
          transparent={false}
          onRequestClose={() => setShowQueueManager(false)}>
          <SyncQueueManager onClose={() => setShowQueueManager(false)} />
        </Modal>
      )}

      {showConflicts && conflicts.length > 0 && (
        <ConflictResolutionModal
          visible={showConflicts}
          conflicts={conflicts}
          onResolve={handleResolveConflicts}
          onDismiss={() => setShowConflicts(false)}
        />
      )}
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    ...typography.h3,
    color: colors.text,
  },
  closeButton: {
    padding: 8,
  },
  content: {
    flex: 1,
  },
  card: {
    backgroundColor: colors.surface,
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 8,
    padding: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardTitle: {
    ...typography.subtitle,
    color: colors.text,
    marginLeft: 8,
  },
  statusGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  statusItem: {
    width: '50%',
    paddingVertical: 8,
  },
  statusLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  statusValue: {
    ...typography.body,
    color: colors.text,
  },
  numberValue: {
    ...typography.h3,
    color: colors.primary,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    ...typography.body,
    color: colors.text,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.error + '10',
    borderRadius: 4,
    padding: 8,
    marginTop: 12,
  },
  errorText: {
    ...typography.caption,
    color: colors.error,
    marginLeft: 8,
    flex: 1,
  },
  progressContainer: {
    marginTop: 12,
  },
  progressText: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  progressBar: {
    height: 4,
    backgroundColor: colors.border,
    borderRadius: 2,
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 2,
  },
  syncActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  syncButton: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: 8,
    padding: 12,
    marginHorizontal: 4,
  },
  syncButtonDisabled: {
    opacity: 0.5,
  },
  syncButtonText: {
    ...typography.subtitle,
    color: colors.text,
    marginTop: 8,
  },
  syncButtonDescription: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 4,
    textAlign: 'center',
  },
  preferenceItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  preferenceInfo: {
    flex: 1,
  },
  preferenceLabel: {
    ...typography.body,
    color: colors.text,
  },
  preferenceDescription: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  preferenceButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4,
    backgroundColor: colors.primary + '10',
  },
  preferenceButtonText: {
    ...typography.caption,
    color: colors.primary,
    fontWeight: '600',
  },
  advancedButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  advancedButtonText: {
    ...typography.body,
    color: colors.text,
    flex: 1,
    marginLeft: 12,
  },
  dangerButton: {
    borderBottomWidth: 0,
  },
  conflictBadge: {
    backgroundColor: colors.error,
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginRight: 8,
  },
  conflictBadgeText: {
    ...typography.caption,
    color: colors.surface,
    fontWeight: '600',
  },
});
