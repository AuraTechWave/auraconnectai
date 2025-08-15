import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, typography } from '@theme';
import { syncManager, type SyncState } from '@sync';
import { formatDistanceToNow } from 'date-fns';

interface SyncStatusBarProps {
  onPress?: () => void;
}

export const SyncStatusBar: React.FC<SyncStatusBarProps> = ({ onPress }) => {
  const [syncState, setSyncState] = useState<SyncState>(syncManager.getState());

  useEffect(() => {
    const handleStateChange = (newState: SyncState) => {
      setSyncState(newState);
    };

    syncManager.on('stateChange', handleStateChange);

    return () => {
      syncManager.off('stateChange', handleStateChange);
    };
  }, []);

  const getStatusIcon = () => {
    switch (syncState.status) {
      case 'syncing':
        return <ActivityIndicator size="small" color={colors.primary} />;
      case 'error':
        return <Icon name="alert-circle" size={20} color={colors.error} />;
      case 'offline':
        return (
          <Icon
            name="cloud-off-outline"
            size={20}
            color={colors.textSecondary}
          />
        );
      default:
        if (syncState.pendingChanges > 0) {
          return (
            <Icon
              name="cloud-upload-outline"
              size={20}
              color={colors.warning}
            />
          );
        }
        return (
          <Icon name="cloud-check-outline" size={20} color={colors.success} />
        );
    }
  };

  const getStatusText = () => {
    switch (syncState.status) {
      case 'syncing':
        if (syncState.progress) {
          return syncState.progress.message;
        }
        return 'Syncing...';
      case 'error':
        return 'Sync failed';
      case 'offline':
        return 'Offline';
      default:
        if (syncState.pendingChanges > 0) {
          return `${syncState.pendingChanges} pending changes`;
        }
        if (syncState.lastSync) {
          return `Last sync ${formatDistanceToNow(syncState.lastSync, { addSuffix: true })}`;
        }
        return 'Never synced';
    }
  };

  const getSubtext = () => {
    if (syncState.status === 'error' && syncState.error) {
      return syncState.error.message;
    }
    if (syncState.queueSize > 0) {
      return `${syncState.queueSize} items in queue`;
    }
    return null;
  };

  const handlePress = () => {
    if (onPress) {
      onPress();
    } else if (syncState.status === 'idle' && syncState.isOnline) {
      syncManager.forceSync();
    }
  };

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={handlePress}
      activeOpacity={0.7}
      disabled={syncState.status === 'syncing'}>
      <View style={styles.statusIcon}>{getStatusIcon()}</View>
      <View style={styles.textContainer}>
        <Text style={styles.statusText}>{getStatusText()}</Text>
        {getSubtext() && (
          <Text style={styles.subText} numberOfLines={1}>
            {getSubtext()}
          </Text>
        )}
      </View>
      {syncState.status === 'idle' && syncState.isOnline && (
        <Icon name="refresh" size={20} color={colors.textSecondary} />
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  statusIcon: {
    marginRight: 12,
    width: 20,
    alignItems: 'center',
  },
  textContainer: {
    flex: 1,
  },
  statusText: {
    ...typography.body,
    color: colors.text,
  },
  subText: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
