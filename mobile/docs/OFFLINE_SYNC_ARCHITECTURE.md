# Offline Sync Architecture

## Overview

The AuraConnect mobile app implements a comprehensive offline-first architecture that allows staff to work seamlessly without internet connectivity. This document outlines the sync strategy, data flow, and conflict resolution mechanisms.

## Core Principles

1. **Offline-First**: All features work offline, with sync happening in the background
2. **Optimistic Updates**: UI updates immediately, with eventual consistency
3. **Conflict Resolution**: Last-write-wins with server authority for critical data
4. **Incremental Sync**: Only changed data is synchronized
5. **Data Integrity**: Transactions ensure consistent state

## Architecture Components

### 1. Local Database (WatermelonDB)

WatermelonDB provides:
- SQLite storage for React Native
- Lazy loading and query observation
- Synchronization adapters
- Migration support

### 2. Sync Engine

The sync engine handles:
- Bidirectional data synchronization
- Conflict detection and resolution
- Queue management for offline changes
- Batch processing for efficiency

### 3. Data Models

#### Syncable Entities
- **Orders**: Create, update, status changes
- **Staff**: Clock in/out, schedules, shifts
- **Menu Items**: Availability, prices, modifiers
- **Inventory**: Stock levels, adjustments
- **Customers**: Basic info, preferences

#### Sync Metadata
Each record includes:
- `localId`: Client-generated ID
- `serverId`: Server-assigned ID
- `lastModified`: Timestamp for conflict detection
- `syncStatus`: pending, syncing, synced, conflict
- `isDeleted`: Soft delete flag

## Sync Strategy

### 1. Pull Strategy (Server → Client)

```
1. Request changes since last sync timestamp
2. Apply remote changes to local database
3. Resolve conflicts if any
4. Update last sync timestamp
```

### 2. Push Strategy (Client → Server)

```
1. Collect all pending local changes
2. Batch changes by entity type
3. Send to server with conflict detection
4. Handle success/failure per record
5. Update sync status
```

### 3. Conflict Resolution

#### Resolution Rules:
1. **Server Authority**: For critical data (payments, inventory)
2. **Last Write Wins**: For non-critical data (notes, preferences)
3. **Merge**: For additive data (tags, categories)
4. **Manual**: For complex conflicts (schedule overlaps)

#### Conflict Types:
- **Update-Update**: Both client and server modified
- **Update-Delete**: One side deleted, other modified
- **Create-Create**: Duplicate creation (use deduplication)

## Implementation Details

### Database Schema

```typescript
// Base sync schema
interface SyncableModel {
  id: string;           // Local ID
  serverId?: string;    // Server ID
  lastModified: Date;
  syncStatus: 'pending' | 'syncing' | 'synced' | 'conflict';
  isDeleted: boolean;
  _raw: any;           // WatermelonDB raw data
}

// Order model example
interface Order extends SyncableModel {
  orderNumber: string;
  customerId?: string;
  items: OrderItem[];
  status: OrderStatus;
  totalAmount: number;
  notes?: string;
  createdAt: Date;
  updatedAt: Date;
}
```

### Sync Flow

```typescript
// Sync process
1. Check network connectivity
2. Authenticate sync request
3. Pull remote changes
   - Fetch changes endpoint: GET /api/sync/pull?since={timestamp}
   - Apply changes to local DB
   - Resolve conflicts
4. Push local changes
   - Collect pending changes
   - Send batch: POST /api/sync/push
   - Process responses
5. Update sync metadata
6. Notify UI of changes
```

### Queue Management

Offline actions are queued with:
- Priority levels (high, normal, low)
- Retry logic with exponential backoff
- Automatic cleanup of old entries
- Size limits to prevent overflow

## Security Considerations

1. **Encryption**: Sensitive data encrypted at rest
2. **Authentication**: Sync requires valid auth token
3. **Data Isolation**: User can only sync their authorized data
4. **Audit Trail**: All sync operations logged
5. **Integrity Checks**: Checksums validate data integrity

## Performance Optimization

1. **Incremental Sync**: Only changed records
2. **Compression**: Gzip for network transfer
3. **Batch Processing**: Group operations
4. **Background Sync**: Non-blocking UI
5. **Smart Scheduling**: Sync when on WiFi

## Error Handling

### Retry Strategy
- Network errors: Exponential backoff
- Server errors: Delayed retry
- Client errors: Mark as failed, notify user

### Recovery Mechanisms
- Automatic conflict resolution
- Manual conflict UI for complex cases
- Rollback capability for failed syncs
- Data validation before sync

## Monitoring & Analytics

Track:
- Sync success/failure rates
- Conflict frequency by type
- Sync duration and data volume
- Offline usage patterns
- Queue sizes and processing times

## Future Enhancements

1. **Real-time Sync**: WebSocket for instant updates
2. **Selective Sync**: Choose data to sync
3. **Compression**: Better algorithms
4. **Predictive Sync**: Pre-fetch likely needed data
5. **P2P Sync**: Direct device-to-device sync