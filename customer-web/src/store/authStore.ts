import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Customer } from '../types';
import api from '../services/api';

interface AuthState {
  customer: Customer | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (data: any) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (data: any) => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      customer: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.login(email, password);
          const { access_token, customer } = response;
          
          localStorage.setItem('customerToken', access_token);
          set({
            customer,
            token: access_token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Login failed',
            isLoading: false,
          });
          throw error;
        }
      },

      register: async (data: any) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.register(data);
          const { access_token, customer } = response;
          
          localStorage.setItem('customerToken', access_token);
          set({
            customer,
            token: access_token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Registration failed',
            isLoading: false,
          });
          throw error;
        }
      },

      logout: async () => {
        try {
          await api.logout();
        } catch (error) {
          // Ignore logout errors
        } finally {
          localStorage.removeItem('customerToken');
          set({
            customer: null,
            token: null,
            isAuthenticated: false,
            error: null,
          });
        }
      },

      updateProfile: async (data: any) => {
        set({ isLoading: true, error: null });
        try {
          const customer = await api.updateProfile(data);
          set({ customer, isLoading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Update failed',
            isLoading: false,
          });
          throw error;
        }
      },

      checkAuth: async () => {
        const token = localStorage.getItem('customerToken');
        if (!token) {
          set({ isAuthenticated: false });
          return;
        }

        try {
          const customer = await api.getProfile();
          set({
            customer,
            token,
            isAuthenticated: true,
          });
        } catch (error) {
          localStorage.removeItem('customerToken');
          set({
            customer: null,
            token: null,
            isAuthenticated: false,
          });
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        customer: state.customer,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);