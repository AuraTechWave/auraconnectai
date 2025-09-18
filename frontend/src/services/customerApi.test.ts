import api from './api';
import { customerApi } from './customerApi';

// Mock the main api instance
jest.mock('./api');
const mockedApi = api as jest.Mocked<typeof api>;

describe('Customer API Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Authentication', () => {
    describe('login', () => {
      test('sends login request with correct credentials', async () => {
        const credentials = {
          email: 'test@example.com',
          password: 'password123'
        };
        
        const mockResponse = {
          data: {
            user: { id: 1, email: 'test@example.com' },
            token: 'jwt-token',
            refreshToken: 'refresh-token'
          }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.login(credentials);
        
        expect(mockedApi.post).toHaveBeenCalledWith('/api/auth/login', credentials);
        expect(result).toBe(mockResponse);
      });

      test('handles login failure', async () => {
        const credentials = {
          email: 'wrong@example.com',
          password: 'wrongpassword'
        };
        
        const mockError = new Error('Invalid credentials');
        mockedApi.post.mockRejectedValue(mockError);
        
        await expect(customerApi.login(credentials)).rejects.toThrow('Invalid credentials');
        expect(mockedApi.post).toHaveBeenCalledWith('/api/auth/login', credentials);
      });
    });

    describe('register', () => {
      test('sends registration request with user data', async () => {
        const userData = {
          name: 'John Doe',
          email: 'john@example.com',
          password: 'password123',
          phone: '+1234567890'
        };
        
        const mockResponse = {
          data: {
            user: { id: 1, ...userData },
            token: 'jwt-token'
          }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.register(userData);
        
        expect(mockedApi.post).toHaveBeenCalledWith('/api/auth/register', userData);
        expect(result).toBe(mockResponse);
      });

      test('handles registration with existing email', async () => {
        const userData = {
          name: 'John Doe',
          email: 'existing@example.com',
          password: 'password123'
        };
        
        const mockError = {
          response: {
            data: { message: 'Email already exists' }
          }
        };
        
        mockedApi.post.mockRejectedValue(mockError);
        
        await expect(customerApi.register(userData)).rejects.toEqual(mockError);
      });
    });

    describe('logout', () => {
      test('sends logout request', async () => {
        const mockResponse = { data: { message: 'Logged out successfully' } };
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.logout();
        
        expect(mockedApi.post).toHaveBeenCalledWith('/api/auth/logout');
        expect(result).toBe(mockResponse);
      });

      test('handles logout error', async () => {
        const mockError = new Error('Logout failed');
        mockedApi.post.mockRejectedValue(mockError);
        
        await expect(customerApi.logout()).rejects.toThrow('Logout failed');
      });
    });

    describe('refreshToken', () => {
      test('sends refresh token request', async () => {
        const refreshToken = 'refresh-token-123';
        const mockResponse = {
          data: {
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token'
          }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.refreshToken(refreshToken);
        
        expect(mockedApi.post).toHaveBeenCalledWith('/api/auth/refresh', {
          refresh_token: refreshToken
        });
        expect(result).toBe(mockResponse);
      });
    });
  });

  describe('Profile Management', () => {
    describe('getProfile', () => {
      test('fetches user profile', async () => {
        const mockProfile = {
          data: {
            id: 1,
            name: 'John Doe',
            email: 'john@example.com',
            phone: '+1234567890',
            preferences: {
              notifications: true,
              marketing: false
            }
          }
        };
        
        mockedApi.get.mockResolvedValue(mockProfile);
        
        const result = await customerApi.getProfile();
        
        expect(mockedApi.get).toHaveBeenCalledWith('/api/customer/profile');
        expect(result).toBe(mockProfile);
      });
    });

    describe('updateProfile', () => {
      test('updates user profile', async () => {
        const profileData = {
          name: 'Jane Doe',
          phone: '+0987654321'
        };
        
        const mockResponse = {
          data: {
            id: 1,
            name: 'Jane Doe',
            email: 'jane@example.com',
            phone: '+0987654321'
          }
        };
        
        mockedApi.put.mockResolvedValue(mockResponse);
        
        const result = await customerApi.updateProfile(profileData);
        
        expect(mockedApi.put).toHaveBeenCalledWith('/api/customer/profile', profileData);
        expect(result).toBe(mockResponse);
      });
    });

    describe('changePassword', () => {
      test('changes user password', async () => {
        const passwordData = {
          currentPassword: 'oldpassword',
          newPassword: 'newpassword123'
        };
        
        const mockResponse = {
          data: { message: 'Password changed successfully' }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.changePassword(passwordData);
        
        expect(mockedApi.post).toHaveBeenCalledWith('/api/customer/change-password', passwordData);
        expect(result).toBe(mockResponse);
      });

      test('handles incorrect current password', async () => {
        const passwordData = {
          currentPassword: 'wrongpassword',
          newPassword: 'newpassword123'
        };
        
        const mockError = {
          response: {
            status: 400,
            data: { message: 'Current password is incorrect' }
          }
        };
        
        mockedApi.post.mockRejectedValue(mockError);
        
        await expect(customerApi.changePassword(passwordData)).rejects.toEqual(mockError);
      });
    });
  });

  describe('Address Management', () => {
    describe('getAddresses', () => {
      test('fetches user addresses', async () => {
        const mockAddresses = {
          data: [
            {
              id: 1,
              type: 'home',
              street: '123 Main St',
              city: 'Anytown',
              state: 'CA',
              zipCode: '12345',
              isDefault: true
            },
            {
              id: 2,
              type: 'work',
              street: '456 Office Blvd',
              city: 'Business City',
              state: 'NY',
              zipCode: '67890',
              isDefault: false
            }
          ]
        };
        
        mockedApi.get.mockResolvedValue(mockAddresses);
        
        const result = await customerApi.getAddresses();
        
        expect(mockedApi.get).toHaveBeenCalledWith('/api/customer/addresses');
        expect(result).toBe(mockAddresses);
      });
    });

    describe('addAddress', () => {
      test('adds new address', async () => {
        const addressData = {
          type: 'home',
          street: '789 New St',
          city: 'New City',
          state: 'TX',
          zipCode: '54321'
        };
        
        const mockResponse = {
          data: {
            id: 3,
            ...addressData,
            isDefault: false
          }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.addAddress(addressData);
        
        expect(mockedApi.post).toHaveBeenCalledWith('/api/customer/addresses', addressData);
        expect(result).toBe(mockResponse);
      });
    });

    describe('updateAddress', () => {
      test('updates existing address', async () => {
        const addressId = 1;
        const addressData = {
          street: '123 Updated St',
          city: 'Updated City'
        };
        
        const mockResponse = {
          data: {
            id: 1,
            type: 'home',
            street: '123 Updated St',
            city: 'Updated City',
            state: 'CA',
            zipCode: '12345'
          }
        };
        
        mockedApi.put.mockResolvedValue(mockResponse);
        
        const result = await customerApi.updateAddress(addressId, addressData);
        
        expect(mockedApi.put).toHaveBeenCalledWith(`/api/customer/addresses/${addressId}`, addressData);
        expect(result).toBe(mockResponse);
      });
    });

    describe('deleteAddress', () => {
      test('deletes address', async () => {
        const addressId = 1;
        const mockResponse = {
          data: { message: 'Address deleted successfully' }
        };
        
        mockedApi.delete.mockResolvedValue(mockResponse);
        
        const result = await customerApi.deleteAddress(addressId);
        
        expect(mockedApi.delete).toHaveBeenCalledWith(`/api/customer/addresses/${addressId}`);
        expect(result).toBe(mockResponse);
      });
    });

    describe('setDefaultAddress', () => {
      test('sets address as default', async () => {
        const addressId = 2;
        const mockResponse = {
          data: { message: 'Default address updated' }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.setDefaultAddress(addressId);
        
        expect(mockedApi.post).toHaveBeenCalledWith(`/api/customer/addresses/${addressId}/set-default`);
        expect(result).toBe(mockResponse);
      });
    });
  });

  describe('Order History', () => {
    describe('getOrders', () => {
      test('fetches order history without filters', async () => {
        const mockOrders = {
          data: {
            orders: [
              {
                id: 1,
                orderNumber: 'ORD001',
                status: 'completed',
                total: 25.99,
                createdAt: '2024-01-15T10:30:00Z'
              },
              {
                id: 2,
                orderNumber: 'ORD002',
                status: 'pending',
                total: 18.50,
                createdAt: '2024-01-16T14:15:00Z'
              }
            ],
            total: 2,
            page: 1,
            limit: 10
          }
        };
        
        mockedApi.get.mockResolvedValue(mockOrders);
        
        const result = await customerApi.getOrders();
        
        expect(mockedApi.get).toHaveBeenCalledWith('/api/customer/orders');
        expect(result).toBe(mockOrders);
      });

      test('fetches orders with pagination and filters', async () => {
        const params = {
          page: 2,
          limit: 5,
          status: 'completed',
          dateFrom: '2024-01-01',
          dateTo: '2024-01-31'
        };
        
        mockedApi.get.mockResolvedValue({ data: { orders: [] } });
        
        await customerApi.getOrders(params);
        
        expect(mockedApi.get).toHaveBeenCalledWith('/api/customer/orders', { params });
      });
    });

    describe('getOrder', () => {
      test('fetches single order by ID', async () => {
        const orderId = 1;
        const mockOrder = {
          data: {
            id: 1,
            orderNumber: 'ORD001',
            status: 'completed',
            items: [
              { id: 1, name: 'Burger', price: 12.99, quantity: 1 },
              { id: 2, name: 'Fries', price: 4.99, quantity: 1 }
            ],
            total: 19.97,
            createdAt: '2024-01-15T10:30:00Z'
          }
        };
        
        mockedApi.get.mockResolvedValue(mockOrder);
        
        const result = await customerApi.getOrder(orderId);
        
        expect(mockedApi.get).toHaveBeenCalledWith(`/api/customer/orders/${orderId}`);
        expect(result).toBe(mockOrder);
      });
    });

    describe('cancelOrder', () => {
      test('cancels order with reason', async () => {
        const orderId = 1;
        const reason = 'Changed my mind';
        const mockResponse = {
          data: { message: 'Order cancelled successfully' }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.cancelOrder(orderId, reason);
        
        expect(mockedApi.post).toHaveBeenCalledWith(`/api/customer/orders/${orderId}/cancel`, {
          reason
        });
        expect(result).toBe(mockResponse);
      });

      test('cancels order without reason', async () => {
        const orderId = 1;
        const mockResponse = {
          data: { message: 'Order cancelled successfully' }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        await customerApi.cancelOrder(orderId);
        
        expect(mockedApi.post).toHaveBeenCalledWith(`/api/customer/orders/${orderId}/cancel`, {
          reason: undefined
        });
      });
    });

    describe('reorderItems', () => {
      test('reorders items from previous order', async () => {
        const orderId = 1;
        const mockResponse = {
          data: {
            cartItems: [
              { id: 1, name: 'Burger', price: 12.99 },
              { id: 2, name: 'Fries', price: 4.99 }
            ]
          }
        };
        
        mockedApi.post.mockResolvedValue(mockResponse);
        
        const result = await customerApi.reorderItems(orderId);
        
        expect(mockedApi.post).toHaveBeenCalledWith(`/api/customer/orders/${orderId}/reorder`);
        expect(result).toBe(mockResponse);
      });
    });
  });

  describe('Preferences', () => {
    describe('getPreferences', () => {
      test('fetches user preferences', async () => {
        const mockPreferences = {
          data: {
            notifications: {
              email: true,
              sms: false,
              push: true
            },
            dietary: {
              vegetarian: false,
              vegan: true,
              glutenFree: false,
              allergies: ['nuts', 'shellfish']
            },
            marketing: {
              emailOffers: true,
              smsOffers: false
            }
          }
        };
        
        mockedApi.get.mockResolvedValue(mockPreferences);
        
        const result = await customerApi.getPreferences();
        
        expect(mockedApi.get).toHaveBeenCalledWith('/api/customer/preferences');
        expect(result).toBe(mockPreferences);
      });
    });

    describe('updatePreferences', () => {
      test('updates user preferences', async () => {
        const preferencesData = {
          notifications: {
            email: false,
            sms: true
          },
          dietary: {
            vegetarian: true
          }
        };
        
        const mockResponse = {
          data: {
            notifications: {
              email: false,
              sms: true,
              push: true
            },
            dietary: {
              vegetarian: true,
              vegan: true,
              glutenFree: false
            }
          }
        };
        
        mockedApi.put.mockResolvedValue(mockResponse);
        
        const result = await customerApi.updatePreferences(preferencesData);
        
        expect(mockedApi.put).toHaveBeenCalledWith('/api/customer/preferences', preferencesData);
        expect(result).toBe(mockResponse);
      });
    });
  });

  describe('Error Handling', () => {
    test('propagates API errors correctly', async () => {
      const mockError = {
        response: {
          status: 500,
          data: { message: 'Internal server error' }
        }
      };
      
      mockedApi.get.mockRejectedValue(mockError);
      
      await expect(customerApi.getProfile()).rejects.toEqual(mockError);
    });

    test('handles network errors', async () => {
      const networkError = new Error('Network Error');
      mockedApi.post.mockRejectedValue(networkError);
      
      await expect(customerApi.login({
        email: 'test@example.com',
        password: 'password'
      })).rejects.toThrow('Network Error');
    });
  });
});