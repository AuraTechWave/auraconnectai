// Sync payload types for strong typing

export interface SyncRecord {
  id: string;
  localId?: string;
  serverId?: string;
  [key: string]: any;
}

export interface SyncChanges {
  created: SyncRecord[];
  updated: SyncRecord[];
  deleted: string[];
}

export interface SyncCollectionChanges {
  [collection: string]: SyncChanges;
}

export interface PullRequest {
  lastPulledAt: number;
  schemaVersion: number;
}

export interface PullResponse {
  changes: SyncCollectionChanges;
  timestamp: number;
}

export interface PushRequest {
  changes: SyncCollectionChanges;
  lastPulledAt: number;
}

export interface SyncAcceptedItem {
  collection: string;
  localId: string;
  serverId: string;
}

export interface SyncRejectedItem {
  collection: string;
  localId: string;
  reason: string;
  code?: string;
}

export interface SyncConflictItem {
  collection: string;
  localId: string;
  serverId?: string;
  localData: SyncRecord;
  serverData: SyncRecord;
  suggestedResolution?: 'server_wins' | 'client_wins' | 'merge';
}

export interface PushResponse {
  accepted: SyncAcceptedItem[];
  rejected: SyncRejectedItem[];
  conflicts: SyncConflictItem[];
}

export interface SyncError {
  code: string;
  message: string;
  details?: Record<string, any>;
  retryable: boolean;
  retryAfter?: number;
}

export type SyncErrorCode = 
  | 'SYNC_NETWORK_ERROR'
  | 'SYNC_AUTH_ERROR'
  | 'SYNC_SERVER_ERROR'
  | 'SYNC_CLIENT_ERROR'
  | 'SYNC_CONFLICT_ERROR'
  | 'SYNC_QUEUE_FULL'
  | 'SYNC_INVALID_DATA';

export interface SyncResult {
  success: boolean;
  stats?: {
    pushed: number;
    pulled: number;
    conflicts: number;
    errors: number;
    duration: number;
  };
  error?: SyncError;
}