import NetInfo, {
  NetInfoState,
  NetInfoSubscription,
} from '@react-native-community/netinfo';
import { EventEmitter } from 'events';
import { logger } from '@utils/logger';
import { showToast } from '@utils/toast';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SYNC_CONFIG } from '@constants/config';

export type NetworkType = 'wifi' | 'cellular' | 'none' | 'unknown';
export type NetworkQuality = 'excellent' | 'good' | 'fair' | 'poor' | 'offline';

export interface NetworkState {
  isConnected: boolean;
  isInternetReachable: boolean;
  type: NetworkType;
  quality: NetworkQuality;
  details: {
    isWifi: boolean;
    isCellular: boolean;
    isConnectionExpensive: boolean;
    cellularGeneration?: '2g' | '3g' | '4g' | '5g';
    strength?: number;
    frequency?: number;
  };
  lastOnline: number | null;
  lastOffline: number | null;
  offlineDuration: number;
}

interface NetworkHistory {
  timestamp: number;
  state: NetworkState;
  duration?: number;
}

const NETWORK_STATE_KEY = 'auraconnect.network.state';
const NETWORK_HISTORY_KEY = 'auraconnect.network.history';
const MAX_HISTORY_ITEMS = 100;

export class NetworkStateManager extends EventEmitter {
  private static instance: NetworkStateManager;
  private subscription: NetInfoSubscription | null = null;
  private currentState: NetworkState;
  private history: NetworkHistory[] = [];
  private reconnectTimer: NodeJS.Timeout | null = null;
  private qualityCheckTimer: NodeJS.Timeout | null = null;
  private isMonitoring = false;

  private constructor() {
    super();
    this.currentState = this.getDefaultState();
    this.loadState();
  }

  static getInstance(): NetworkStateManager {
    if (!NetworkStateManager.instance) {
      NetworkStateManager.instance = new NetworkStateManager();
    }
    return NetworkStateManager.instance;
  }

  async initialize(): Promise<void> {
    logger.info('Initializing network state manager');

    // Get initial state
    const netState = await NetInfo.fetch();
    this.updateState(this.parseNetInfoState(netState));

    // Start monitoring
    this.startMonitoring();

    // Start quality checks
    this.startQualityChecks();
  }

  private startMonitoring(): void {
    if (this.isMonitoring) return;

    this.subscription = NetInfo.addEventListener(state => {
      const previousState = { ...this.currentState };
      const newState = this.parseNetInfoState(state);

      this.updateState(newState);

      // Handle connection state changes
      if (!previousState.isConnected && newState.isConnected) {
        this.handleReconnection(previousState, newState);
      } else if (previousState.isConnected && !newState.isConnected) {
        this.handleDisconnection(previousState, newState);
      }

      // Handle network type changes
      if (previousState.type !== newState.type) {
        this.handleNetworkTypeChange(previousState, newState);
      }
    });

    this.isMonitoring = true;
  }

  private stopMonitoring(): void {
    if (this.subscription) {
      this.subscription();
      this.subscription = null;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.qualityCheckTimer) {
      clearInterval(this.qualityCheckTimer);
      this.qualityCheckTimer = null;
    }

    this.isMonitoring = false;
  }

  private startQualityChecks(): void {
    // Check network quality every 30 seconds when online
    this.qualityCheckTimer = setInterval(async () => {
      if (this.currentState.isConnected) {
        const quality = await this.checkNetworkQuality();
        if (quality !== this.currentState.quality) {
          this.updateState({ ...this.currentState, quality });
          this.emit('qualityChange', quality, this.currentState.quality);
        }
      }
    }, 30000);
  }

  private async checkNetworkQuality(): Promise<NetworkQuality> {
    if (!this.currentState.isConnected) {
      return 'offline';
    }

    try {
      // Ping test to measure latency
      const startTime = Date.now();
      const response = await fetch(`${SYNC_CONFIG.PULL_URL}/health`, {
        method: 'HEAD',
        signal: AbortSignal.timeout(5000),
      });
      const latency = Date.now() - startTime;

      // Determine quality based on latency and network type
      if (this.currentState.details.isWifi) {
        if (latency < 50) return 'excellent';
        if (latency < 150) return 'good';
        if (latency < 300) return 'fair';
        return 'poor';
      } else if (this.currentState.details.isCellular) {
        if (latency < 100) return 'excellent';
        if (latency < 250) return 'good';
        if (latency < 500) return 'fair';
        return 'poor';
      }

      return 'fair';
    } catch (error) {
      logger.warn('Network quality check failed', error);
      return 'poor';
    }
  }

  private parseNetInfoState(state: NetInfoState): NetworkState {
    const isConnected = state.isConnected ?? false;
    const isInternetReachable = state.isInternetReachable ?? false;

    let type: NetworkType = 'unknown';
    let isWifi = false;
    let isCellular = false;
    let cellularGeneration: '2g' | '3g' | '4g' | '5g' | undefined;

    switch (state.type) {
      case 'wifi':
        type = 'wifi';
        isWifi = true;
        break;
      case 'cellular':
        type = 'cellular';
        isCellular = true;
        cellularGeneration = this.getCellularGeneration(state);
        break;
      case 'none':
        type = 'none';
        break;
      default:
        type = 'unknown';
    }

    const now = Date.now();
    const offlineDuration =
      !isConnected && this.currentState.lastOffline
        ? now - this.currentState.lastOffline
        : 0;

    return {
      isConnected,
      isInternetReachable,
      type,
      quality: this.currentState.quality || 'fair',
      details: {
        isWifi,
        isCellular,
        isConnectionExpensive: state.details?.isConnectionExpensive ?? false,
        cellularGeneration,
        strength: state.details?.strength,
        frequency: state.details?.frequency,
      },
      lastOnline: isConnected ? now : this.currentState.lastOnline,
      lastOffline: !isConnected ? now : this.currentState.lastOffline,
      offlineDuration,
    };
  }

  private getCellularGeneration(
    state: NetInfoState,
  ): '2g' | '3g' | '4g' | '5g' | undefined {
    const cellularGeneration = state.details?.cellularGeneration;
    if (typeof cellularGeneration === 'string') {
      if (cellularGeneration.includes('5g')) return '5g';
      if (
        cellularGeneration.includes('4g') ||
        cellularGeneration.includes('lte')
      )
        return '4g';
      if (cellularGeneration.includes('3g')) return '3g';
      if (cellularGeneration.includes('2g')) return '2g';
    }
    return undefined;
  }

  private handleReconnection(
    previousState: NetworkState,
    newState: NetworkState,
  ): void {
    const offlineDuration = previousState.lastOffline
      ? Date.now() - previousState.lastOffline
      : 0;

    logger.info('Network reconnected', {
      type: newState.type,
      offlineDuration,
    });

    // Add to history
    this.addToHistory({
      ...previousState,
      offlineDuration,
    });

    // Show notification
    if (offlineDuration > 5000) {
      showToast(
        'success',
        'Back Online',
        `Connected via ${newState.type}. Syncing changes...`,
      );
    }

    // Emit reconnection event
    this.emit('reconnected', {
      newState,
      previousState,
      offlineDuration,
    });

    // Schedule sync after a short delay to ensure stable connection
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectTimer = setTimeout(() => {
      this.emit('stableConnection');
    }, 3000);
  }

  private handleDisconnection(
    previousState: NetworkState,
    newState: NetworkState,
  ): void {
    logger.warn('Network disconnected', {
      previousType: previousState.type,
    });

    // Show notification
    showToast(
      'warning',
      'Connection Lost',
      'Working in offline mode. Changes will sync when reconnected.',
    );

    // Emit disconnection event
    this.emit('disconnected', {
      newState,
      previousState,
    });
  }

  private handleNetworkTypeChange(
    previousState: NetworkState,
    newState: NetworkState,
  ): void {
    logger.info('Network type changed', {
      from: previousState.type,
      to: newState.type,
    });

    // Check if switching from cellular to wifi or vice versa
    if (previousState.details.isCellular && newState.details.isWifi) {
      showToast('info', 'Network Changed', 'Now connected via WiFi');
      this.emit('switchedToWifi');
    } else if (previousState.details.isWifi && newState.details.isCellular) {
      showToast('info', 'Network Changed', 'Now connected via cellular');
      this.emit('switchedToCellular');
    }

    this.emit('typeChanged', {
      from: previousState.type,
      to: newState.type,
    });
  }

  private updateState(newState: NetworkState): void {
    const previousState = { ...this.currentState };
    this.currentState = newState;

    // Save state
    this.saveState();

    // Emit state change
    this.emit('stateChange', newState, previousState);
  }

  private addToHistory(state: NetworkState, duration?: number): void {
    const historyItem: NetworkHistory = {
      timestamp: Date.now(),
      state: { ...state },
      duration,
    };

    this.history.unshift(historyItem);

    // Limit history size
    if (this.history.length > MAX_HISTORY_ITEMS) {
      this.history = this.history.slice(0, MAX_HISTORY_ITEMS);
    }

    this.saveHistory();
  }

  private async saveState(): Promise<void> {
    try {
      await AsyncStorage.setItem(
        NETWORK_STATE_KEY,
        JSON.stringify(this.currentState),
      );
    } catch (error) {
      logger.error('Failed to save network state', error);
    }
  }

  private async loadState(): Promise<void> {
    try {
      const stored = await AsyncStorage.getItem(NETWORK_STATE_KEY);
      if (stored) {
        const state = JSON.parse(stored);
        this.currentState = { ...this.getDefaultState(), ...state };
      }
    } catch (error) {
      logger.error('Failed to load network state', error);
    }
  }

  private async saveHistory(): Promise<void> {
    try {
      await AsyncStorage.setItem(
        NETWORK_HISTORY_KEY,
        JSON.stringify(this.history),
      );
    } catch (error) {
      logger.error('Failed to save network history', error);
    }
  }

  private async loadHistory(): Promise<void> {
    try {
      const stored = await AsyncStorage.getItem(NETWORK_HISTORY_KEY);
      if (stored) {
        this.history = JSON.parse(stored);
      }
    } catch (error) {
      logger.error('Failed to load network history', error);
    }
  }

  private getDefaultState(): NetworkState {
    return {
      isConnected: false,
      isInternetReachable: false,
      type: 'unknown',
      quality: 'offline',
      details: {
        isWifi: false,
        isCellular: false,
        isConnectionExpensive: false,
      },
      lastOnline: null,
      lastOffline: null,
      offlineDuration: 0,
    };
  }

  // Public methods
  getState(): NetworkState {
    return { ...this.currentState };
  }

  getHistory(): NetworkHistory[] {
    return [...this.history];
  }

  isOnline(): boolean {
    return (
      this.currentState.isConnected && this.currentState.isInternetReachable
    );
  }

  isWifi(): boolean {
    return this.currentState.details.isWifi;
  }

  isCellular(): boolean {
    return this.currentState.details.isCellular;
  }

  isConnectionExpensive(): boolean {
    return this.currentState.details.isConnectionExpensive;
  }

  getQuality(): NetworkQuality {
    return this.currentState.quality;
  }

  getOfflineDuration(): number {
    if (!this.currentState.isConnected && this.currentState.lastOffline) {
      return Date.now() - this.currentState.lastOffline;
    }
    return 0;
  }

  async waitForConnection(timeout = 30000): Promise<boolean> {
    if (this.isOnline()) {
      return true;
    }

    return new Promise(resolve => {
      const timer = setTimeout(() => {
        this.off('reconnected', handleReconnection);
        resolve(false);
      }, timeout);

      const handleReconnection = () => {
        clearTimeout(timer);
        resolve(true);
      };

      this.once('reconnected', handleReconnection);
    });
  }

  async testConnectivity(url?: string): Promise<boolean> {
    try {
      const testUrl = url || `${SYNC_CONFIG.PULL_URL}/health`;
      const response = await fetch(testUrl, {
        method: 'HEAD',
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  }

  destroy(): void {
    this.stopMonitoring();
    this.removeAllListeners();
  }

  // Event emitter methods are inherited
  // Events: 'stateChange', 'reconnected', 'disconnected', 'typeChanged',
  //         'qualityChange', 'switchedToWifi', 'switchedToCellular', 'stableConnection'
}
