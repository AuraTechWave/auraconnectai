import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
  RefreshControl,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, typography } from '@theme';
import { SyncQueue, QueueItem } from '@sync/SyncQueue';
import { formatDistanceToNow } from 'date-fns';
import { showToast } from '@utils/toast';
import { SwipeListView } from 'react-native-swipe-list-view';

interface SyncQueueManagerProps {
  onClose?: () => void;
}

export const SyncQueueManager: React.FC<SyncQueueManagerProps> = ({
  onClose,
}) => {
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [stats, setStats] = useState<ReturnType<SyncQueue['getStats']> | null>(
    null,
  );
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [isSelectionMode, setIsSelectionMode] = useState(false);

  const syncQueue = new SyncQueue();

  useEffect(() => {
    loadQueueData();
  }, []);

  const loadQueueData = async () => {
    setIsRefreshing(true);
    try {
      const items = syncQueue.getQueueItems();
      const queueStats = syncQueue.getStats();
      setQueueItems(items);
      setStats(queueStats);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleClearQueue = () => {
    Alert.alert(
      'Clear Sync Queue',
      'Are you sure you want to clear all pending sync operations? This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            await syncQueue.clear();
            await loadQueueData();
            showToast(
              'success',
              'Queue Cleared',
              'All pending operations removed',
            );
          },
        },
      ],
    );
  };

  const handleRemoveItem = async (itemId: string) => {
    await syncQueue.removeItem(itemId);
    await loadQueueData();
    showToast('info', 'Removed', 'Item removed from queue');
  };

  const handlePrioritizeItem = async (itemId: string) => {
    await syncQueue.prioritizeItem(itemId);
    await loadQueueData();
    showToast('success', 'Prioritized', 'Item moved to high priority');
  };

  const handleRetryNow = async () => {
    setIsRefreshing(true);
    try {
      await syncQueue.processQueue();
      await loadQueueData();
      showToast('success', 'Processing', 'Queue processing started');
    } catch (error) {
      showToast('error', 'Failed', 'Failed to process queue');
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleBulkRemove = async () => {
    if (selectedItems.size === 0) return;

    Alert.alert(
      'Remove Selected Items',
      `Remove ${selectedItems.size} selected items from the queue?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            for (const itemId of selectedItems) {
              await syncQueue.removeItem(itemId);
            }
            setSelectedItems(new Set());
            setIsSelectionMode(false);
            await loadQueueData();
            showToast(
              'success',
              'Removed',
              `${selectedItems.size} items removed`,
            );
          },
        },
      ],
    );
  };

  const toggleItemSelection = (itemId: string) => {
    const newSelection = new Set(selectedItems);
    if (newSelection.has(itemId)) {
      newSelection.delete(itemId);
    } else {
      newSelection.add(itemId);
    }
    setSelectedItems(newSelection);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return colors.error;
      case 'normal':
        return colors.warning;
      case 'low':
        return colors.info;
      default:
        return colors.textSecondary;
    }
  };

  const getOperationIcon = (operation: string) => {
    switch (operation) {
      case 'create':
        return 'plus-circle';
      case 'update':
        return 'pencil';
      case 'delete':
        return 'delete';
      default:
        return 'help-circle';
    }
  };

  const renderQueueItem = ({ item }: { item: QueueItem }) => (
    <TouchableOpacity
      style={[
        styles.queueItem,
        selectedItems.has(item.id) && styles.selectedItem,
      ]}
      onPress={() => {
        if (isSelectionMode) {
          toggleItemSelection(item.id);
        }
      }}
      onLongPress={() => {
        if (!isSelectionMode) {
          setIsSelectionMode(true);
          toggleItemSelection(item.id);
        }
      }}>
      {isSelectionMode && (
        <TouchableOpacity
          style={styles.checkbox}
          onPress={() => toggleItemSelection(item.id)}>
          <Icon
            name={
              selectedItems.has(item.id)
                ? 'checkbox-marked'
                : 'checkbox-blank-outline'
            }
            size={24}
            color={colors.primary}
          />
        </TouchableOpacity>
      )}

      <View style={styles.itemContent}>
        <View style={styles.itemHeader}>
          <Icon
            name={getOperationIcon(item.operation)}
            size={20}
            color={colors.text}
          />
          <Text style={styles.itemCollection}>{item.collection}</Text>
          <View
            style={[
              styles.priorityBadge,
              { backgroundColor: getPriorityColor(item.priority) + '20' },
            ]}>
            <Text
              style={[
                styles.priorityText,
                { color: getPriorityColor(item.priority) },
              ]}>
              {item.priority}
            </Text>
          </View>
        </View>

        <View style={styles.itemDetails}>
          <Text style={styles.itemOperation}>
            {item.operation.charAt(0).toUpperCase() + item.operation.slice(1)}{' '}
            operation
          </Text>
          <Text style={styles.itemTimestamp}>
            {formatDistanceToNow(item.timestamp, { addSuffix: true })}
          </Text>
        </View>

        {item.retryCount > 0 && (
          <View style={styles.retryInfo}>
            <Icon name="refresh" size={14} color={colors.warning} />
            <Text style={styles.retryText}>
              Retry attempt: {item.retryCount}
            </Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );

  const renderHiddenItem = ({ item }: { item: QueueItem }) => (
    <View style={styles.hiddenItem}>
      <TouchableOpacity
        style={[styles.hiddenButton, styles.prioritizeButton]}
        onPress={() => handlePrioritizeItem(item.id)}>
        <Icon name="arrow-up-bold" size={20} color={colors.surface} />
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.hiddenButton, styles.deleteButton]}
        onPress={() => handleRemoveItem(item.id)}>
        <Icon name="delete" size={20} color={colors.surface} />
      </TouchableOpacity>
    </View>
  );

  const renderHeader = () => (
    <View style={styles.statsContainer}>
      <Text style={styles.statsTitle}>Queue Statistics</Text>

      {stats && (
        <>
          <View style={styles.statsGrid}>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>{stats.total}</Text>
              <Text style={styles.statLabel}>Total Items</Text>
            </View>

            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.error }]}>
                {stats.byPriority.high || 0}
              </Text>
              <Text style={styles.statLabel}>High Priority</Text>
            </View>

            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.warning }]}>
                {stats.byPriority.normal || 0}
              </Text>
              <Text style={styles.statLabel}>Normal Priority</Text>
            </View>

            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.info }]}>
                {stats.byPriority.low || 0}
              </Text>
              <Text style={styles.statLabel}>Low Priority</Text>
            </View>
          </View>

          <View style={styles.operationStats}>
            <Text style={styles.operationStatsTitle}>Operations</Text>
            <View style={styles.operationBars}>
              {Object.entries(stats.byOperation).map(([operation, count]) => (
                <View key={operation} style={styles.operationBar}>
                  <View style={styles.operationBarLabel}>
                    <Icon
                      name={getOperationIcon(operation)}
                      size={16}
                      color={colors.text}
                    />
                    <Text style={styles.operationBarText}>
                      {operation}: {count}
                    </Text>
                  </View>
                  <View style={styles.operationBarContainer}>
                    <View
                      style={[
                        styles.operationBarFill,
                        { width: `${(count / stats.total) * 100}%` },
                      ]}
                    />
                  </View>
                </View>
              ))}
            </View>
          </View>

          {stats.oldestItem && (
            <View style={styles.oldestItemInfo}>
              <Icon name="clock-alert" size={16} color={colors.warning} />
              <Text style={styles.oldestItemText}>
                Oldest item:{' '}
                {formatDistanceToNow(stats.oldestItem, { addSuffix: true })}
              </Text>
            </View>
          )}
        </>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Sync Queue Manager</Text>
        {onClose && (
          <TouchableOpacity onPress={onClose} style={styles.closeButton}>
            <Icon name="close" size={24} color={colors.text} />
          </TouchableOpacity>
        )}
      </View>

      {isSelectionMode && (
        <View style={styles.selectionBar}>
          <Text style={styles.selectionText}>
            {selectedItems.size} selected
          </Text>
          <View style={styles.selectionActions}>
            <TouchableOpacity
              style={styles.selectionButton}
              onPress={() => {
                setSelectedItems(new Set(queueItems.map(item => item.id)));
              }}>
              <Text style={styles.selectionButtonText}>Select All</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.selectionButton}
              onPress={handleBulkRemove}
              disabled={selectedItems.size === 0}>
              <Text style={styles.selectionButtonText}>Remove</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.selectionButton}
              onPress={() => {
                setIsSelectionMode(false);
                setSelectedItems(new Set());
              }}>
              <Text style={styles.selectionButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      <SwipeListView
        data={queueItems}
        renderItem={renderQueueItem}
        renderHiddenItem={renderHiddenItem}
        leftOpenValue={75}
        rightOpenValue={-75}
        keyExtractor={item => item.id}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="inbox" size={48} color={colors.textSecondary} />
            <Text style={styles.emptyText}>No items in sync queue</Text>
            <Text style={styles.emptySubtext}>
              All operations have been synchronized
            </Text>
          </View>
        }
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={loadQueueData}
            colors={[colors.primary]}
          />
        }
        contentContainerStyle={styles.listContent}
      />

      <View style={styles.footer}>
        <TouchableOpacity
          style={styles.footerButton}
          onPress={handleClearQueue}
          disabled={queueItems.length === 0}>
          <Icon name="delete-sweep" size={20} color={colors.error} />
          <Text style={[styles.footerButtonText, { color: colors.error }]}>
            Clear Queue
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.footerButton, styles.primaryButton]}
          onPress={handleRetryNow}
          disabled={queueItems.length === 0 || isRefreshing}>
          <Icon name="play-circle" size={20} color={colors.surface} />
          <Text style={[styles.footerButtonText, { color: colors.surface }]}>
            Process Now
          </Text>
        </TouchableOpacity>
      </View>
    </View>
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
  selectionBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.primary + '10',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  selectionText: {
    ...typography.body,
    color: colors.primary,
  },
  selectionActions: {
    flexDirection: 'row',
  },
  selectionButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginLeft: 8,
  },
  selectionButtonText: {
    ...typography.caption,
    color: colors.primary,
    fontWeight: '600',
  },
  listContent: {
    flexGrow: 1,
  },
  statsContainer: {
    backgroundColor: colors.surface,
    margin: 16,
    padding: 16,
    borderRadius: 8,
  },
  statsTitle: {
    ...typography.subtitle,
    color: colors.text,
    marginBottom: 12,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: 16,
  },
  statItem: {
    width: '50%',
    paddingVertical: 8,
  },
  statValue: {
    ...typography.h2,
    color: colors.text,
  },
  statLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 4,
  },
  operationStats: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  operationStatsTitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: 8,
  },
  operationBars: {
    marginTop: 8,
  },
  operationBar: {
    marginBottom: 8,
  },
  operationBarLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  operationBarText: {
    ...typography.caption,
    color: colors.text,
    marginLeft: 4,
  },
  operationBarContainer: {
    height: 4,
    backgroundColor: colors.border,
    borderRadius: 2,
  },
  operationBarFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 2,
  },
  oldestItemInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  oldestItemText: {
    ...typography.caption,
    color: colors.warning,
    marginLeft: 8,
  },
  queueItem: {
    backgroundColor: colors.surface,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 8,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
  },
  selectedItem: {
    backgroundColor: colors.primary + '10',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  checkbox: {
    marginRight: 12,
  },
  itemContent: {
    flex: 1,
  },
  itemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  itemCollection: {
    ...typography.subtitle,
    color: colors.text,
    marginLeft: 8,
    flex: 1,
  },
  priorityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  priorityText: {
    ...typography.caption,
    fontWeight: '600',
  },
  itemDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  itemOperation: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  itemTimestamp: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  retryInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  retryText: {
    ...typography.caption,
    color: colors.warning,
    marginLeft: 4,
  },
  hiddenItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flex: 1,
    marginHorizontal: 16,
    marginBottom: 8,
  },
  hiddenButton: {
    justifyContent: 'center',
    alignItems: 'center',
    width: 75,
    height: '100%',
    borderRadius: 8,
  },
  prioritizeButton: {
    backgroundColor: colors.success,
  },
  deleteButton: {
    backgroundColor: colors.error,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 48,
  },
  emptyText: {
    ...typography.subtitle,
    color: colors.textSecondary,
    marginTop: 16,
  },
  emptySubtext: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 4,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  footerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  primaryButton: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  footerButtonText: {
    ...typography.body,
    marginLeft: 8,
    fontWeight: '600',
  },
});
