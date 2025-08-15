import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  TouchableOpacity,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, typography } from '@theme';
import {
  syncManager,
  networkManager,
  type SyncState,
  type NetworkState,
} from '@sync';

interface SyncStatusIndicatorProps {
  compact?: boolean;
  showDetails?: boolean;
  onPress?: () => void;
}

export const SyncStatusIndicator: React.FC<SyncStatusIndicatorProps> = ({
  compact = false,
  showDetails = true,
  onPress,
}) => {
  const [syncState, setSyncState] = useState<SyncState>(syncManager.getState());
  const [networkState, setNetworkState] = useState<NetworkState>(
    networkManager.getState(),
  );
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const rotateAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const handleSyncStateChange = (newState: SyncState) => {
      setSyncState(newState);
    };

    const handleNetworkStateChange = (newState: NetworkState) => {
      setNetworkState(newState);
    };

    syncManager.on('stateChange', handleSyncStateChange);
    networkManager.on('stateChange', handleNetworkStateChange);

    return () => {
      syncManager.off('stateChange', handleSyncStateChange);
      networkManager.off('stateChange', handleNetworkStateChange);
    };
  }, []);

  useEffect(() => {
    if (syncState.status === 'syncing') {
      // Start rotation animation
      Animated.loop(
        Animated.timing(rotateAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
      ).start();
    } else {
      // Stop rotation
      rotateAnim.setValue(0);
    }
  }, [syncState.status, rotateAnim]);

  useEffect(() => {
    if (!networkState.isConnected) {
      // Pulse animation for offline state
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.2,
            duration: 1000,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 1000,
            useNativeDriver: true,
          }),
        ]),
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [networkState.isConnected, pulseAnim]);

  const getStatusColor = () => {
    if (!networkState.isConnected) return colors.error;
    if (syncState.status === 'error') return colors.error;
    if (syncState.status === 'syncing') return colors.primary;
    if (syncState.pendingChanges > 0) return colors.warning;
    return colors.success;
  };

  const getStatusIcon = () => {
    if (!networkState.isConnected) return 'cloud-off-outline';
    if (syncState.status === 'error') return 'cloud-alert';
    if (syncState.status === 'syncing') return 'cloud-sync';
    if (syncState.pendingChanges > 0) return 'cloud-upload-outline';
    return 'cloud-check-outline';
  };

  const getStatusText = () => {
    if (!networkState.isConnected) return 'Offline';
    if (syncState.status === 'error') return 'Sync Error';
    if (syncState.status === 'syncing') {
      if (syncState.progress) {
        return `${Math.round((syncState.progress.current / syncState.progress.total) * 100)}%`;
      }
      return 'Syncing';
    }
    if (syncState.pendingChanges > 0) {
      return `${syncState.pendingChanges} pending`;
    }
    return 'Synced';
  };

  const getNetworkQualityIcon = () => {
    switch (networkState.quality) {
      case 'excellent':
        return 'signal-cellular-3';
      case 'good':
        return 'signal-cellular-2';
      case 'fair':
        return 'signal-cellular-1';
      case 'poor':
        return 'signal-cellular-outline';
      default:
        return 'signal-cellular-outline';
    }
  };

  const getNetworkQualityColor = () => {
    switch (networkState.quality) {
      case 'excellent':
        return colors.success;
      case 'good':
        return colors.primary;
      case 'fair':
        return colors.warning;
      case 'poor':
        return colors.error;
      default:
        return colors.textSecondary;
    }
  };

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  if (compact) {
    return (
      <TouchableOpacity
        style={styles.compactContainer}
        onPress={onPress}
        activeOpacity={0.7}>
        <Animated.View
          style={[
            styles.compactIconContainer,
            {
              transform: [
                { scale: pulseAnim },
                { rotate: syncState.status === 'syncing' ? spin : '0deg' },
              ],
            },
          ]}>
          <Icon name={getStatusIcon()} size={20} color={getStatusColor()} />
        </Animated.View>
        {syncState.pendingChanges > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{syncState.pendingChanges}</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={onPress}
      activeOpacity={0.7}
      disabled={!onPress}>
      <View style={styles.mainContent}>
        <Animated.View
          style={[
            styles.iconContainer,
            {
              transform: [
                { scale: pulseAnim },
                { rotate: syncState.status === 'syncing' ? spin : '0deg' },
              ],
            },
          ]}>
          <Icon name={getStatusIcon()} size={24} color={getStatusColor()} />
        </Animated.View>

        <View style={styles.textContainer}>
          <Text style={[styles.statusText, { color: getStatusColor() }]}>
            {getStatusText()}
          </Text>
          {showDetails && (
            <View style={styles.details}>
              {networkState.isConnected && (
                <View style={styles.detailItem}>
                  <Icon
                    name={networkState.details.isWifi ? 'wifi' : 'signal'}
                    size={12}
                    color={colors.textSecondary}
                  />
                  <Text style={styles.detailText}>
                    {networkState.details.isWifi ? 'WiFi' : 'Cellular'}
                  </Text>
                </View>
              )}
              {networkState.isConnected && (
                <View style={styles.detailItem}>
                  <Icon
                    name={getNetworkQualityIcon()}
                    size={12}
                    color={getNetworkQualityColor()}
                  />
                  <Text
                    style={[
                      styles.detailText,
                      { color: getNetworkQualityColor() },
                    ]}>
                    {networkState.quality}
                  </Text>
                </View>
              )}
              {syncState.queueSize > 0 && (
                <View style={styles.detailItem}>
                  <Icon
                    name="format-list-bulleted"
                    size={12}
                    color={colors.textSecondary}
                  />
                  <Text style={styles.detailText}>
                    {syncState.queueSize} queued
                  </Text>
                </View>
              )}
            </View>
          )}
        </View>

        {syncState.status === 'syncing' && syncState.progress && (
          <View style={styles.progressContainer}>
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

      {syncState.pendingChanges > 0 && !compact && (
        <View style={[styles.badge, styles.largeBadge]}>
          <Text style={styles.badgeText}>{syncState.pendingChanges}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.surface,
    borderRadius: 8,
    minHeight: 48,
  },
  compactContainer: {
    position: 'relative',
    padding: 8,
  },
  mainContent: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconContainer: {
    marginRight: 12,
  },
  compactIconContainer: {
    width: 32,
    height: 32,
    justifyContent: 'center',
    alignItems: 'center',
  },
  textContainer: {
    flex: 1,
  },
  statusText: {
    ...typography.subtitle,
    fontWeight: '600',
  },
  details: {
    flexDirection: 'row',
    marginTop: 4,
  },
  detailItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 12,
  },
  detailText: {
    ...typography.caption,
    color: colors.textSecondary,
    marginLeft: 4,
  },
  badge: {
    position: 'absolute',
    top: 0,
    right: 0,
    backgroundColor: colors.error,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
  },
  largeBadge: {
    position: 'relative',
    top: 'auto',
    right: 'auto',
    marginLeft: 8,
  },
  badgeText: {
    ...typography.caption,
    color: colors.surface,
    fontWeight: '600',
    fontSize: 11,
  },
  progressContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
  },
  progressBar: {
    height: 2,
    backgroundColor: colors.border,
    borderRadius: 1,
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 1,
  },
});
