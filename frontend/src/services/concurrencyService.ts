import api from './api';

export interface VersionedEntity {
  id: string | number;
  version: number;
  updatedAt: string;
  etag?: string;
}

export interface ConflictResolution<T> {
  strategy: 'merge' | 'overwrite' | 'cancel';
  resolvedData?: T;
}

export class ConcurrencyError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public conflictData?: any
  ) {
    super(message);
    this.name = 'ConcurrencyError';
  }
}

class ConcurrencyService {
  /**
   * Add version headers to request
   */
  addVersionHeaders(config: any, entity: VersionedEntity): any {
    return {
      ...config,
      headers: {
        ...config.headers,
        'If-Match': entity.etag || entity.version.toString(),
        'X-Entity-Version': entity.version.toString(),
      },
    };
  }

  /**
   * Extract version info from response
   */
  extractVersionInfo(response: any): Partial<VersionedEntity> {
    return {
      version: parseInt(response.headers['x-entity-version'] || '0'),
      etag: response.headers['etag'],
      updatedAt: response.headers['last-modified'] || new Date().toISOString(),
    };
  }

  /**
   * Handle optimistic update with retry
   */
  async optimisticUpdate<T extends VersionedEntity>(
    url: string,
    entity: T,
    updateFn: (current: T) => T,
    maxRetries: number = 3
  ): Promise<T> {
    let retries = 0;
    let currentEntity = { ...entity };

    while (retries < maxRetries) {
      try {
        // Apply update function
        const updatedEntity = updateFn(currentEntity);

        // Send update with version
        const config = this.addVersionHeaders({}, currentEntity);
        const response = await api.put(url, updatedEntity, config);

        // Extract new version info
        const versionInfo = this.extractVersionInfo(response);
        
        return {
          ...response.data,
          ...versionInfo,
        };
      } catch (error: any) {
        if (error.response?.status === 409) {
          // Conflict detected
          retries++;
          
          if (retries >= maxRetries) {
            throw new ConcurrencyError(
              'Maximum retry attempts reached',
              409,
              error.response.data
            );
          }

          // Fetch latest version
          const latestResponse = await api.get(url);
          currentEntity = {
            ...latestResponse.data,
            ...this.extractVersionInfo(latestResponse),
          };

          // Continue loop to retry with latest version
          continue;
        }

        // Other errors, throw immediately
        throw error;
      }
    }

    throw new ConcurrencyError('Failed to complete optimistic update', 500);
  }

  /**
   * Detect conflicts between entities
   */
  detectConflicts<T extends VersionedEntity>(
    local: T,
    remote: T
  ): boolean {
    return local.version !== remote.version || 
           local.updatedAt !== remote.updatedAt;
  }

  /**
   * Merge changes from remote entity
   */
  mergeChanges<T extends Record<string, any>>(
    local: T,
    remote: T,
    conflictFields: string[] = []
  ): T {
    const merged = { ...remote };

    // Preserve local changes for non-conflicting fields
    for (const key in local) {
      if (!conflictFields.includes(key) && local[key] !== remote[key]) {
        merged[key] = local[key];
      }
    }

    return merged;
  }

  /**
   * Create a conflict resolver
   */
  createConflictResolver<T extends VersionedEntity>() {
    return {
      resolve: async (
        local: T,
        remote: T,
        strategy: ConflictResolution<T>['strategy'] = 'merge'
      ): Promise<T> => {
        switch (strategy) {
          case 'overwrite':
            return local;
          
          case 'cancel':
            return remote;
          
          case 'merge':
          default:
            return this.mergeChanges(local, remote) as T;
        }
      },
    };
  }

  /**
   * Batch update with conflict detection
   */
  async batchUpdate<T extends VersionedEntity>(
    items: T[],
    updateUrl: string,
    conflictHandler?: (conflicts: T[]) => Promise<T[]>
  ): Promise<{ successful: T[]; conflicts: T[] }> {
    const successful: T[] = [];
    const conflicts: T[] = [];

    const updatePromises = items.map(async (item) => {
      try {
        const config = this.addVersionHeaders({}, item);
        const response = await api.put(`${updateUrl}/${item.id}`, item, config);
        
        successful.push({
          ...response.data,
          ...this.extractVersionInfo(response),
        });
      } catch (error: any) {
        if (error.response?.status === 409) {
          conflicts.push(item);
        } else {
          throw error;
        }
      }
    });

    await Promise.all(updatePromises);

    // Handle conflicts if handler provided
    if (conflicts.length > 0 && conflictHandler) {
      const resolved = await conflictHandler(conflicts);
      
      // Retry resolved conflicts
      const retryResult = await this.batchUpdate(resolved, updateUrl);
      successful.push(...retryResult.successful);
      
      return {
        successful,
        conflicts: retryResult.conflicts,
      };
    }

    return { successful, conflicts };
  }

  /**
   * Subscribe to entity changes
   */
  subscribeToChanges(
    entityType: string,
    entityId: string | number,
    callback: (update: any) => void
  ): () => void {
    // This would connect to WebSocket/SSE for real-time updates
    const eventName = `${entityType}:${entityId}:changed`;
    
    const handler = (event: CustomEvent) => {
      callback(event.detail);
    };

    window.addEventListener(eventName as any, handler);

    return () => {
      window.removeEventListener(eventName as any, handler);
    };
  }
}

export const concurrencyService = new ConcurrencyService();
export default concurrencyService;