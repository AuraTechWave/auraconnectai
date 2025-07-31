import React, { useEffect, useState } from 'react';
import {
  Modal,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  ProgressBarAndroid,
  Platform,
} from 'react-native';
import { colors, typography } from '@theme';
import { syncManager, type SyncState } from '@sync';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

interface SyncProgressModalProps {
  visible: boolean;
  onClose: () => void;
}

export const SyncProgressModal: React.FC<SyncProgressModalProps> = ({
  visible,
  onClose,
}) => {
  const [syncState, setSyncState] = useState<SyncState>(syncManager.getState());

  useEffect(() => {
    const handleStateChange = (newState: SyncState) => {
      setSyncState(newState);
    };

    const handleSyncComplete = () => {
      setTimeout(() => {
        onClose();
      }, 1000);
    };

    syncManager.on('stateChange', handleStateChange);
    syncManager.on('syncComplete', handleSyncComplete);

    return () => {
      syncManager.off('stateChange', handleStateChange);
      syncManager.off('syncComplete', handleSyncComplete);
    };
  }, [onClose]);

  const renderProgress = () => {
    if (!syncState.progress) {
      return null;
    }

    const progress = syncState.progress.current / syncState.progress.total;

    if (Platform.OS === 'android') {
      return (
        <ProgressBarAndroid
          styleAttr="Horizontal"
          indeterminate={false}
          progress={progress}
          color={colors.primary}
          style={styles.progressBar}
        />
      );
    }

    // iOS progress bar (custom implementation)
    return (
      <View style={styles.progressBarContainer}>
        <View
          style={[
            styles.progressBarFill,
            { width: `${progress * 100}%` },
          ]}
        />
      </View>
    );
  };

  const renderContent = () => {
    if (syncState.status === 'error') {
      return (
        <>
          <Icon name="alert-circle" size={48} color={colors.error} />
          <Text style={styles.title}>Sync Failed</Text>
          <Text style={styles.message}>
            {syncState.error?.message || 'An error occurred during sync'}
          </Text>
          <TouchableOpacity style={styles.button} onPress={onClose}>
            <Text style={styles.buttonText}>Close</Text>
          </TouchableOpacity>
        </>
      );
    }

    if (syncState.status === 'syncing') {
      return (
        <>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.title}>Syncing...</Text>
          <Text style={styles.message}>
            {syncState.progress?.message || 'Please wait while we sync your data'}
          </Text>
          {renderProgress()}
          <Text style={styles.stats}>
            {syncState.pendingChanges > 0 && `${syncState.pendingChanges} pending changes`}
          </Text>
        </>
      );
    }

    // Success state
    return (
      <>
        <Icon name="check-circle" size={48} color={colors.success} />
        <Text style={styles.title}>Sync Complete</Text>
        <Text style={styles.message}>Your data is up to date</Text>
      </>
    );
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <View style={styles.container}>
          {renderContent()}
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  container: {
    backgroundColor: colors.background,
    borderRadius: 12,
    padding: 24,
    width: '80%',
    maxWidth: 320,
    alignItems: 'center',
  },
  title: {
    ...typography.title,
    marginTop: 16,
    marginBottom: 8,
    textAlign: 'center',
  },
  message: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 16,
  },
  progressBar: {
    width: '100%',
    marginVertical: 16,
  },
  progressBarContainer: {
    width: '100%',
    height: 4,
    backgroundColor: colors.border,
    borderRadius: 2,
    marginVertical: 16,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 2,
  },
  stats: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 8,
  },
  button: {
    backgroundColor: colors.primary,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 16,
  },
  buttonText: {
    ...typography.button,
    color: colors.white,
  },
});