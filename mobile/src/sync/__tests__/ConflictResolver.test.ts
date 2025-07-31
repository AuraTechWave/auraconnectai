import { ConflictResolver } from '../ConflictResolver';
import database from '@database/index';
import { Q } from '@nozbe/watermelondb';

// Mock dependencies
jest.mock('@database/index');
jest.mock('@utils/logger');

describe('ConflictResolver', () => {
  let resolver: ConflictResolver;
  let mockCollection: any;

  beforeEach(() => {
    resolver = new ConflictResolver();
    mockCollection = {
      find: jest.fn(),
      query: jest.fn(),
    };
    (database.collections.get as jest.Mock).mockReturnValue(mockCollection);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('detectConflicts', () => {
    it('should detect update conflicts when local record has pending changes', async () => {
      const mockLocalRecord = {
        id: 'local123',
        syncStatus: 'pending',
        lastModified: Date.now(),
        _raw: { name: 'Local Item', price: 10 },
      };

      mockCollection.find.mockResolvedValue(mockLocalRecord);

      const changes = {
        menu_items: {
          updated: [{
            id: 'server123',
            localId: 'local123',
            name: 'Server Item',
            price: 15,
          }],
          created: [],
          deleted: [],
        },
      };

      const result = await resolver.detectConflicts(changes);

      expect(result.conflicts).toHaveLength(1);
      expect(result.conflicts[0]).toMatchObject({
        collection: 'menu_items',
        localId: 'local123',
        type: 'update',
      });
    });

    it('should not detect conflicts for synced records', async () => {
      const mockLocalRecord = {
        id: 'local123',
        syncStatus: 'synced',
        lastModified: Date.now() - 10000,
      };

      mockCollection.find.mockResolvedValue(mockLocalRecord);

      const changes = {
        menu_items: {
          updated: [{
            id: 'server123',
            localId: 'local123',
            name: 'Server Item',
          }],
          created: [],
          deleted: [],
        },
      };

      const result = await resolver.detectConflicts(changes);

      expect(result.conflicts).toHaveLength(0);
    });

    it('should handle delete conflicts', async () => {
      const mockLocalRecord = {
        id: 'local123',
        serverId: 'server123',
        syncStatus: 'pending',
      };

      mockCollection.query.mockReturnValue({
        fetch: jest.fn().mockResolvedValue([mockLocalRecord]),
      });

      const changes = {
        menu_items: {
          created: [],
          updated: [],
          deleted: ['server123'],
        },
      };

      const result = await resolver.detectConflicts(changes);

      expect(result.conflicts).toHaveLength(1);
      expect(result.conflicts[0].type).toBe('delete');
    });
  });

  describe('conflict resolution strategies', () => {
    const createConflict = (overrides = {}) => ({
      collection: 'orders',
      localId: 'local123',
      serverId: 'server123',
      localData: {
        status: 'preparing',
        totalAmount: 50,
        lastModified: Date.now(),
      },
      serverData: {
        status: 'completed',
        totalAmount: 55,
        updated_at: Date.now() - 5000,
      },
      type: 'update' as const,
      ...overrides,
    });

    it('should apply server wins strategy', async () => {
      resolver.setDefaultStrategy('server_wins');
      const conflict = createConflict();
      
      const resolved = await resolver['resolveConflict'](conflict);
      
      expect(resolved).toEqual(conflict.serverData);
    });

    it('should apply client wins strategy', async () => {
      resolver.setDefaultStrategy('client_wins');
      const conflict = createConflict();
      
      const resolved = await resolver['resolveConflict'](conflict);
      
      expect(resolved).toEqual(conflict.localData);
    });

    it('should apply last write wins strategy', async () => {
      resolver.setDefaultStrategy('last_write_wins');
      
      // Test when local is newer
      const localNewer = createConflict({
        localData: { lastModified: Date.now() },
        serverData: { updated_at: Date.now() - 10000 },
      });
      
      let resolved = await resolver['resolveConflict'](localNewer);
      expect(resolved).toEqual(localNewer.localData);
      
      // Test when server is newer
      const serverNewer = createConflict({
        localData: { lastModified: Date.now() - 10000 },
        serverData: { updated_at: Date.now() },
      });
      
      resolved = await resolver['resolveConflict'](serverNewer);
      expect(resolved).toEqual(serverNewer.serverData);
    });
  });

  describe('collection-specific merge strategies', () => {
    it('should merge order conflicts correctly', async () => {
      const conflict = {
        collection: 'orders',
        localId: 'local123',
        localData: {
          status: 'preparing',
          notes: 'Extra spicy',
          lastModified: Date.now(),
          items: [{ menuItemId: '1', quantity: 2 }],
        },
        serverData: {
          status: 'ready',
          notes: 'No onions',
          updated_at: Date.now() - 1000,
          items: [{ menuItemId: '1', quantity: 1 }],
        },
        type: 'update' as const,
        strategy: 'merge' as const,
      };

      const resolved = await resolver['resolveConflict'](conflict);
      
      // Server status should win
      expect(resolved.status).toBe('ready');
      // Local notes should be preserved (newer)
      expect(resolved.notes).toBe('Extra spicy');
    });

    it('should merge menu item conflicts correctly', async () => {
      const conflict = {
        collection: 'menu_items',
        localId: 'local123',
        localData: {
          name: 'Burger Deluxe',
          price: 12.99,
          isAvailable: true,
          customizations: ['extra cheese', 'no pickles'],
        },
        serverData: {
          name: 'Burger Deluxe',
          price: 13.99,
          isAvailable: false,
          customizations: [],
        },
        type: 'update' as const,
        strategy: 'merge' as const,
      };

      const resolved = await resolver['resolveConflict'](conflict);
      
      // Server price and availability are authoritative
      expect(resolved.price).toBe(13.99);
      expect(resolved.isAvailable).toBe(false);
      // Local customizations preserved
      expect(resolved.customizations).toEqual(['extra cheese', 'no pickles']);
    });

    it('should merge customer conflicts correctly', async () => {
      const conflict = {
        collection: 'customers',
        localId: 'local123',
        localData: {
          preferences: {
            dietary: ['vegetarian'],
            favoriteItems: ['item1', 'item2'],
          },
          loyaltyPoints: 100,
          notes: 'Prefers window seat',
          lastModified: Date.now(),
        },
        serverData: {
          preferences: {
            dietary: ['vegan'],
            allergies: ['nuts'],
          },
          loyaltyPoints: 150,
          notes: 'VIP customer',
          updated_at: Date.now() - 5000,
        },
        type: 'update' as const,
        strategy: 'merge' as const,
      };

      const resolved = await resolver['resolveConflict'](conflict);
      
      // Server loyalty points are authoritative
      expect(resolved.loyaltyPoints).toBe(150);
      // Preferences should be merged
      expect(resolved.preferences).toEqual({
        dietary: ['vegetarian'],
        favoriteItems: ['item1', 'item2'],
        allergies: ['nuts'],
      });
      // Newer notes preserved
      expect(resolved.notes).toBe('Prefers window seat');
    });
  });

  describe('edge cases', () => {
    it('should handle missing local records gracefully', async () => {
      mockCollection.find.mockRejectedValue(new Error('Record not found'));

      const changes = {
        orders: {
          updated: [{ id: 'server123', localId: 'local123' }],
          created: [],
          deleted: [],
        },
      };

      const result = await resolver.detectConflicts(changes);
      
      expect(result.conflicts).toHaveLength(0);
      expect(result.resolved.orders.updated).toHaveLength(1);
    });

    it('should handle null/undefined values in merge', async () => {
      const conflict = {
        collection: 'generic',
        localId: 'local123',
        localData: {
          field1: 'value1',
          field2: null,
          field3: undefined,
          field4: '',
        },
        serverData: {
          field1: null,
          field2: 'value2',
          field3: 'value3',
          field4: 'value4',
        },
        type: 'update' as const,
        strategy: 'merge' as const,
      };

      const resolved = await resolver['resolveConflict'](conflict);
      
      // Non-null local values should be preserved
      expect(resolved.field1).toBe('value1');
      // Server non-null values should fill in
      expect(resolved.field2).toBe('value2');
      expect(resolved.field3).toBe('value3');
      expect(resolved.field4).toBe('value4');
    });
  });
});