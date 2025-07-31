import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import * as Keychain from 'react-native-keychain';
import NetInfo from '@react-native-community/netinfo';

import { apiClient } from '@services/api.client';
import { AUTH_CONFIG } from '@constants/config';

jest.mock('react-native-keychain');
jest.mock('@react-native-community/netinfo');

describe('API Client', () => {
  let mockAxios: MockAdapter;
  
  beforeEach(() => {
    mockAxios = new MockAdapter(axios);
    jest.clearAllMocks();
    
    // Mock network as connected by default
    (NetInfo.fetch as jest.Mock).mockResolvedValue({ isConnected: true });
  });

  afterEach(() => {
    mockAxios.restore();
  });

  describe('Token Refresh', () => {
    it('should refresh token when receiving 401', async () => {
      const mockToken = 'mock-access-token';
      const mockRefreshToken = 'mock-refresh-token';
      const newMockToken = 'new-mock-access-token';

      // Mock keychain to return tokens
      (Keychain.getInternetCredentials as jest.Mock)
        .mockResolvedValueOnce({
          username: mockRefreshToken,
          password: mockToken,
        })
        .mockResolvedValueOnce({
          username: mockRefreshToken,
          password: mockToken,
        })
        .mockResolvedValueOnce({
          username: mockRefreshToken,
          password: newMockToken,
        });

      // First request returns 401
      mockAxios.onGet('/test').replyOnce(401);

      // Token refresh request
      mockAxios.onPost('/auth/refresh').reply(200, {
        access_token: newMockToken,
        refresh_token: mockRefreshToken,
      });

      // Retry request with new token
      mockAxios.onGet('/test').reply(200, { data: 'success' });

      const response = await apiClient.get('/test');

      expect(response.data).toEqual({ data: 'success' });
      expect(Keychain.setInternetCredentials).toHaveBeenCalledWith(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
        AUTH_CONFIG.TOKEN_KEY,
        newMockToken,
      );
    });

    it('should queue multiple requests during token refresh', async () => {
      const mockToken = 'mock-access-token';
      const mockRefreshToken = 'mock-refresh-token';
      const newMockToken = 'new-mock-access-token';

      (Keychain.getInternetCredentials as jest.Mock)
        .mockResolvedValue({
          username: mockRefreshToken,
          password: mockToken,
        });

      // All requests return 401 initially
      mockAxios.onGet('/test1').replyOnce(401);
      mockAxios.onGet('/test2').replyOnce(401);
      mockAxios.onGet('/test3').replyOnce(401);

      // Token refresh
      mockAxios.onPost('/auth/refresh').reply(200, {
        access_token: newMockToken,
        refresh_token: mockRefreshToken,
      });

      // Retry requests succeed
      mockAxios.onGet('/test1').reply(200, { data: 'test1' });
      mockAxios.onGet('/test2').reply(200, { data: 'test2' });
      mockAxios.onGet('/test3').reply(200, { data: 'test3' });

      // Make multiple concurrent requests
      const [response1, response2, response3] = await Promise.all([
        apiClient.get('/test1'),
        apiClient.get('/test2'),
        apiClient.get('/test3'),
      ]);

      expect(response1.data).toEqual({ data: 'test1' });
      expect(response2.data).toEqual({ data: 'test2' });
      expect(response3.data).toEqual({ data: 'test3' });

      // Token refresh should only be called once
      const refreshCalls = mockAxios.history.post.filter(
        req => req.url === '/auth/refresh',
      );
      expect(refreshCalls).toHaveLength(1);
    });

    it('should clear auth and reject when refresh fails', async () => {
      const mockToken = 'mock-access-token';
      const mockRefreshToken = 'mock-refresh-token';

      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue({
        username: mockRefreshToken,
        password: mockToken,
      });

      // First request returns 401
      mockAxios.onGet('/test').replyOnce(401);

      // Token refresh fails
      mockAxios.onPost('/auth/refresh').reply(401);

      await expect(apiClient.get('/test')).rejects.toThrow();

      expect(Keychain.resetInternetCredentials).toHaveBeenCalledWith(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
      );
    });

    it('should not refresh if refresh token is missing', async () => {
      const mockToken = 'mock-access-token';

      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValueOnce({
        username: null,
        password: mockToken,
      });

      // First request returns 401
      mockAxios.onGet('/test').replyOnce(401);

      await expect(apiClient.get('/test')).rejects.toThrow();

      // Should not attempt refresh
      const refreshCalls = mockAxios.history.post.filter(
        req => req.url === '/auth/refresh',
      );
      expect(refreshCalls).toHaveLength(0);
    });

    it('should add auth token to requests', async () => {
      const mockToken = 'mock-access-token';

      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue({
        password: mockToken,
      });

      mockAxios.onGet('/test').reply(200, { data: 'success' });

      await apiClient.get('/test');

      const request = mockAxios.history.get[0];
      expect(request.headers?.Authorization).toBe(`Bearer ${mockToken}`);
    });

    it('should handle concurrent refresh attempts', async () => {
      const mockToken = 'expired-token';
      const mockRefreshToken = 'mock-refresh-token';
      const newMockToken = 'new-mock-access-token';

      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue({
        username: mockRefreshToken,
        password: mockToken,
      });

      // All requests get 401
      mockAxios.onAny().replyOnce(401);

      // Delay refresh response to simulate concurrent requests
      mockAxios.onPost('/auth/refresh').reply(() => {
        return new Promise(resolve => {
          setTimeout(() => {
            resolve([200, {
              access_token: newMockToken,
              refresh_token: mockRefreshToken,
            }]);
          }, 100);
        });
      });

      // After refresh, all succeed
      mockAxios.onAny().reply(200, { data: 'success' });

      // Make multiple requests that will all get 401
      const promises = Array.from({ length: 5 }, (_, i) =>
        apiClient.get(`/test${i}`),
      );

      const results = await Promise.all(promises);

      // All should succeed
      results.forEach(result => {
        expect(result.data).toEqual({ data: 'success' });
      });

      // Only one refresh call should be made
      const refreshCalls = mockAxios.history.post.filter(
        req => req.url === '/auth/refresh',
      );
      expect(refreshCalls).toHaveLength(1);
    });
  });
});