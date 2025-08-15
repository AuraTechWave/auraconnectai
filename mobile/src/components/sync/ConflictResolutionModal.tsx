import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Modal,
  ActivityIndicator,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, typography } from '@theme';
import { ConflictInfo } from '@sync/ConflictResolver';
import { format } from 'date-fns';
import { showToast } from '@utils/toast';

interface ConflictResolutionModalProps {
  visible: boolean;
  conflicts: ConflictInfo[];
  onResolve: (resolutions: ConflictResolution[]) => Promise<void>;
  onDismiss: () => void;
}

export interface ConflictResolution {
  conflictIndex: number;
  strategy: 'server_wins' | 'client_wins' | 'merge' | 'skip';
  customData?: any;
}

export const ConflictResolutionModal: React.FC<
  ConflictResolutionModalProps
> = ({ visible, conflicts, onResolve, onDismiss }) => {
  const [resolutions, setResolutions] = useState<ConflictResolution[]>([]);
  const [isResolving, setIsResolving] = useState(false);
  const [selectedConflictIndex, setSelectedConflictIndex] = useState(0);
  const [showDetails, setShowDetails] = useState(false);

  const currentConflict = conflicts[selectedConflictIndex];

  const handleStrategySelect = (strategy: ConflictResolution['strategy']) => {
    const newResolution: ConflictResolution = {
      conflictIndex: selectedConflictIndex,
      strategy,
    };

    setResolutions(prev => {
      const updated = [...prev];
      const existingIndex = updated.findIndex(
        r => r.conflictIndex === selectedConflictIndex,
      );
      if (existingIndex >= 0) {
        updated[existingIndex] = newResolution;
      } else {
        updated.push(newResolution);
      }
      return updated;
    });

    // Auto-advance to next conflict
    if (selectedConflictIndex < conflicts.length - 1) {
      setSelectedConflictIndex(prev => prev + 1);
    }
  };

  const handleResolveAll = async () => {
    if (resolutions.length !== conflicts.length) {
      showToast('warning', 'Incomplete', 'Please resolve all conflicts');
      return;
    }

    setIsResolving(true);
    try {
      await onResolve(resolutions);
      showToast('success', 'Resolved', 'All conflicts have been resolved');
      onDismiss();
    } catch (error) {
      showToast('error', 'Failed', 'Failed to resolve conflicts');
    } finally {
      setIsResolving(false);
    }
  };

  const handleApplyToAll = (strategy: ConflictResolution['strategy']) => {
    const allResolutions = conflicts.map((_, index) => ({
      conflictIndex: index,
      strategy,
    }));
    setResolutions(allResolutions);
    showToast(
      'info',
      'Applied',
      `${strategy.replace('_', ' ')} applied to all conflicts`,
    );
  };

  const formatValue = (value: any): string => {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  };

  const getStrategyIcon = (strategy: string) => {
    switch (strategy) {
      case 'server_wins':
        return 'cloud-download';
      case 'client_wins':
        return 'cellphone-arrow-down';
      case 'merge':
        return 'merge';
      case 'skip':
        return 'skip-next';
      default:
        return 'help-circle';
    }
  };

  const getStrategyColor = (strategy: string) => {
    switch (strategy) {
      case 'server_wins':
        return colors.info;
      case 'client_wins':
        return colors.warning;
      case 'merge':
        return colors.success;
      case 'skip':
        return colors.textSecondary;
      default:
        return colors.text;
    }
  };

  if (!currentConflict) {
    return null;
  }

  const currentResolution = resolutions.find(
    r => r.conflictIndex === selectedConflictIndex,
  );

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={false}
      onRequestClose={onDismiss}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Resolve Sync Conflicts</Text>
          <TouchableOpacity onPress={onDismiss} style={styles.closeButton}>
            <Icon name="close" size={24} color={colors.text} />
          </TouchableOpacity>
        </View>

        <View style={styles.progressBar}>
          <View
            style={[
              styles.progressFill,
              {
                width: `${((selectedConflictIndex + 1) / conflicts.length) * 100}%`,
              },
            ]}
          />
        </View>

        <Text style={styles.progressText}>
          Conflict {selectedConflictIndex + 1} of {conflicts.length}
        </Text>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          <View style={styles.conflictInfo}>
            <View style={styles.conflictHeader}>
              <Icon name="database" size={20} color={colors.primary} />
              <Text style={styles.conflictCollection}>
                {currentConflict.collection}
              </Text>
              <View style={styles.conflictTypeBadge}>
                <Text style={styles.conflictTypeText}>
                  {currentConflict.type}
                </Text>
              </View>
            </View>

            <TouchableOpacity
              style={styles.detailsToggle}
              onPress={() => setShowDetails(!showDetails)}>
              <Text style={styles.detailsToggleText}>
                {showDetails ? 'Hide' : 'Show'} Details
              </Text>
              <Icon
                name={showDetails ? 'chevron-up' : 'chevron-down'}
                size={20}
                color={colors.primary}
              />
            </TouchableOpacity>

            {showDetails && (
              <View style={styles.dataComparison}>
                <View style={styles.dataColumn}>
                  <View style={styles.dataHeader}>
                    <Icon name="cellphone" size={16} color={colors.warning} />
                    <Text style={styles.dataHeaderText}>Local Version</Text>
                  </View>
                  <ScrollView style={styles.dataContent} nestedScrollEnabled>
                    <Text style={styles.dataText}>
                      {formatValue(currentConflict.localData)}
                    </Text>
                  </ScrollView>
                  {currentConflict.localData?.lastModified && (
                    <Text style={styles.timestamp}>
                      {format(currentConflict.localData.lastModified, 'PPpp')}
                    </Text>
                  )}
                </View>

                <View style={styles.dataDivider} />

                <View style={styles.dataColumn}>
                  <View style={styles.dataHeader}>
                    <Icon name="cloud" size={16} color={colors.info} />
                    <Text style={styles.dataHeaderText}>Server Version</Text>
                  </View>
                  <ScrollView style={styles.dataContent} nestedScrollEnabled>
                    <Text style={styles.dataText}>
                      {formatValue(currentConflict.serverData)}
                    </Text>
                  </ScrollView>
                  {currentConflict.serverData?.updated_at && (
                    <Text style={styles.timestamp}>
                      {format(
                        new Date(currentConflict.serverData.updated_at),
                        'PPpp',
                      )}
                    </Text>
                  )}
                </View>
              </View>
            )}
          </View>

          <View style={styles.strategySection}>
            <Text style={styles.sectionTitle}>Choose Resolution Strategy</Text>

            <TouchableOpacity
              style={[
                styles.strategyOption,
                currentResolution?.strategy === 'server_wins' &&
                  styles.selectedStrategy,
              ]}
              onPress={() => handleStrategySelect('server_wins')}>
              <Icon
                name={getStrategyIcon('server_wins')}
                size={24}
                color={getStrategyColor('server_wins')}
              />
              <View style={styles.strategyContent}>
                <Text style={styles.strategyTitle}>Use Server Version</Text>
                <Text style={styles.strategyDescription}>
                  Keep the version from the server, discarding local changes
                </Text>
              </View>
              {currentResolution?.strategy === 'server_wins' && (
                <Icon name="check-circle" size={20} color={colors.success} />
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.strategyOption,
                currentResolution?.strategy === 'client_wins' &&
                  styles.selectedStrategy,
              ]}
              onPress={() => handleStrategySelect('client_wins')}>
              <Icon
                name={getStrategyIcon('client_wins')}
                size={24}
                color={getStrategyColor('client_wins')}
              />
              <View style={styles.strategyContent}>
                <Text style={styles.strategyTitle}>Use Local Version</Text>
                <Text style={styles.strategyDescription}>
                  Keep your local changes, overwriting the server version
                </Text>
              </View>
              {currentResolution?.strategy === 'client_wins' && (
                <Icon name="check-circle" size={20} color={colors.success} />
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.strategyOption,
                currentResolution?.strategy === 'merge' &&
                  styles.selectedStrategy,
              ]}
              onPress={() => handleStrategySelect('merge')}>
              <Icon
                name={getStrategyIcon('merge')}
                size={24}
                color={getStrategyColor('merge')}
              />
              <View style={styles.strategyContent}>
                <Text style={styles.strategyTitle}>Merge Changes</Text>
                <Text style={styles.strategyDescription}>
                  Attempt to combine both versions intelligently
                </Text>
              </View>
              {currentResolution?.strategy === 'merge' && (
                <Icon name="check-circle" size={20} color={colors.success} />
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.strategyOption,
                currentResolution?.strategy === 'skip' &&
                  styles.selectedStrategy,
              ]}
              onPress={() => handleStrategySelect('skip')}>
              <Icon
                name={getStrategyIcon('skip')}
                size={24}
                color={getStrategyColor('skip')}
              />
              <View style={styles.strategyContent}>
                <Text style={styles.strategyTitle}>Skip This Conflict</Text>
                <Text style={styles.strategyDescription}>
                  Resolve this conflict later
                </Text>
              </View>
              {currentResolution?.strategy === 'skip' && (
                <Icon name="check-circle" size={20} color={colors.success} />
              )}
            </TouchableOpacity>
          </View>

          <View style={styles.bulkActions}>
            <Text style={styles.bulkActionsTitle}>Bulk Actions</Text>
            <View style={styles.bulkButtonsRow}>
              <TouchableOpacity
                style={styles.bulkButton}
                onPress={() => handleApplyToAll('server_wins')}>
                <Text style={styles.bulkButtonText}>All Server</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.bulkButton}
                onPress={() => handleApplyToAll('client_wins')}>
                <Text style={styles.bulkButtonText}>All Local</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.bulkButton}
                onPress={() => handleApplyToAll('merge')}>
                <Text style={styles.bulkButtonText}>All Merge</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>

        <View style={styles.footer}>
          <View style={styles.navigation}>
            <TouchableOpacity
              style={[
                styles.navButton,
                selectedConflictIndex === 0 && styles.navButtonDisabled,
              ]}
              onPress={() =>
                setSelectedConflictIndex(prev => Math.max(0, prev - 1))
              }
              disabled={selectedConflictIndex === 0}>
              <Icon name="chevron-left" size={24} color={colors.text} />
              <Text style={styles.navButtonText}>Previous</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.navButton,
                selectedConflictIndex === conflicts.length - 1 &&
                  styles.navButtonDisabled,
              ]}
              onPress={() =>
                setSelectedConflictIndex(prev =>
                  Math.min(conflicts.length - 1, prev + 1),
                )
              }
              disabled={selectedConflictIndex === conflicts.length - 1}>
              <Text style={styles.navButtonText}>Next</Text>
              <Icon name="chevron-right" size={24} color={colors.text} />
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            style={[
              styles.resolveButton,
              resolutions.length !== conflicts.length &&
                styles.resolveButtonDisabled,
            ]}
            onPress={handleResolveAll}
            disabled={resolutions.length !== conflicts.length || isResolving}>
            {isResolving ? (
              <ActivityIndicator size="small" color={colors.surface} />
            ) : (
              <>
                <Icon name="check-all" size={20} color={colors.surface} />
                <Text style={styles.resolveButtonText}>
                  Resolve All Conflicts
                </Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </View>
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
  progressBar: {
    height: 4,
    backgroundColor: colors.border,
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.primary,
  },
  progressText: {
    ...typography.caption,
    color: colors.textSecondary,
    textAlign: 'center',
    marginVertical: 8,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  conflictInfo: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
  },
  conflictHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  conflictCollection: {
    ...typography.subtitle,
    color: colors.text,
    marginLeft: 8,
    flex: 1,
  },
  conflictTypeBadge: {
    backgroundColor: colors.primary + '20',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  conflictTypeText: {
    ...typography.caption,
    color: colors.primary,
    textTransform: 'uppercase',
  },
  detailsToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
  },
  detailsToggleText: {
    ...typography.body,
    color: colors.primary,
    marginRight: 4,
  },
  dataComparison: {
    marginTop: 12,
  },
  dataColumn: {
    marginBottom: 16,
  },
  dataHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  dataHeaderText: {
    ...typography.subtitle,
    color: colors.text,
    marginLeft: 8,
  },
  dataContent: {
    backgroundColor: colors.background,
    borderRadius: 4,
    padding: 12,
    maxHeight: 150,
  },
  dataText: {
    ...typography.mono,
    color: colors.text,
    fontSize: 12,
  },
  timestamp: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 4,
  },
  dataDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 8,
  },
  strategySection: {
    marginBottom: 16,
  },
  sectionTitle: {
    ...typography.subtitle,
    color: colors.text,
    marginBottom: 12,
  },
  strategyOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  selectedStrategy: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  strategyContent: {
    flex: 1,
    marginLeft: 12,
  },
  strategyTitle: {
    ...typography.subtitle,
    color: colors.text,
    marginBottom: 4,
  },
  strategyDescription: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  bulkActions: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  bulkActionsTitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: 8,
  },
  bulkButtonsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  bulkButton: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 4,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginHorizontal: 4,
    alignItems: 'center',
  },
  bulkButtonText: {
    ...typography.caption,
    color: colors.primary,
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    padding: 16,
  },
  navigation: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  navButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  navButtonDisabled: {
    opacity: 0.3,
  },
  navButtonText: {
    ...typography.body,
    color: colors.text,
    marginHorizontal: 4,
  },
  resolveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 24,
  },
  resolveButtonDisabled: {
    backgroundColor: colors.textSecondary,
    opacity: 0.5,
  },
  resolveButtonText: {
    ...typography.subtitle,
    color: colors.surface,
    marginLeft: 8,
  },
});
