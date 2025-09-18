import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { customerApi } from '../services/customerApi';

const useCustomerStore = create(
  persist(
    (set, get) => ({
      customer: null,
      token: null,
      isAuthenticated: false,
      addresses: [],
      preferences: {},
      selectedAddress: null,
      isLoading: false,
      error: null,

      setCustomer: (customer) => set({ customer, isAuthenticated: !!customer }),
      
      setToken: (token) => {
        localStorage.setItem('authToken', token);
        localStorage.setItem('customerToken', token); // Keep for backward compatibility
        set({ token });
      },

      login: async (credentials) => {
        set({ isLoading: true, error: null });
        try {
          const response = await customerApi.login(credentials);
          const { customer, token, refreshToken } = response.data;
          set({ 
            customer, 
            token, 
            isAuthenticated: true, 
            isLoading: false 
          });
          localStorage.setItem('authToken', token);
          localStorage.setItem('customerToken', token); // Keep for backward compatibility
          if (refreshToken) {
            localStorage.setItem('refreshToken', refreshToken);
          }
          return { success: true };
        } catch (error) {
          set({ 
            error: error.response?.data?.message || 'Login failed', 
            isLoading: false 
          });
          return { success: false, error: error.response?.data?.message };
        }
      },

      register: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await customerApi.register(data);
          const { customer, token } = response.data;
          set({ 
            customer, 
            token, 
            isAuthenticated: true, 
            isLoading: false 
          });
          localStorage.setItem('customerToken', token);
          return { success: true };
        } catch (error) {
          set({ 
            error: error.response?.data?.message || 'Registration failed', 
            isLoading: false 
          });
          return { success: false, error: error.response?.data?.message };
        }
      },

      logout: () => {
        localStorage.removeItem('customerToken');
        set({ 
          customer: null, 
          token: null, 
          isAuthenticated: false,
          addresses: [],
          preferences: {},
          selectedAddress: null 
        });
      },

      fetchProfile: async () => {
        set({ isLoading: true });
        try {
          const response = await customerApi.getProfile();
          set({ customer: response.data, isLoading: false });
        } catch (error) {
          set({ error: error.message, isLoading: false });
        }
      },

      updateProfile: async (data) => {
        set({ isLoading: true });
        try {
          const response = await customerApi.updateProfile(data);
          set({ customer: response.data, isLoading: false });
          return { success: true };
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return { success: false, error: error.message };
        }
      },

      fetchAddresses: async () => {
        try {
          const response = await customerApi.getAddresses();
          set({ addresses: response.data });
        } catch (error) {
          console.error('Failed to fetch addresses:', error);
        }
      },

      addAddress: async (address) => {
        try {
          const response = await customerApi.addAddress(address);
          set((state) => ({ 
            addresses: [...state.addresses, response.data] 
          }));
          return { success: true, address: response.data };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },

      updateAddress: async (id, address) => {
        try {
          const response = await customerApi.updateAddress(id, address);
          set((state) => ({
            addresses: state.addresses.map((a) => 
              a.id === id ? response.data : a
            ),
          }));
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },

      deleteAddress: async (id) => {
        try {
          await customerApi.deleteAddress(id);
          set((state) => ({
            addresses: state.addresses.filter((a) => a.id !== id),
            selectedAddress: state.selectedAddress?.id === id ? null : state.selectedAddress,
          }));
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },

      setSelectedAddress: (address) => set({ selectedAddress: address }),

      fetchPreferences: async () => {
        try {
          const response = await customerApi.getPreferences();
          set({ preferences: response.data });
        } catch (error) {
          console.error('Failed to fetch preferences:', error);
        }
      },

      updatePreferences: async (preferences) => {
        try {
          const response = await customerApi.updatePreferences(preferences);
          set({ preferences: response.data });
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'customer-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        customer: state.customer,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

export default useCustomerStore;