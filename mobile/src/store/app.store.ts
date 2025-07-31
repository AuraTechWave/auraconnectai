import { create } from 'zustand';
import { MMKV } from 'react-native-mmkv';

const storage = new MMKV();

interface AppState {
  // UI State
  isLoading: boolean;
  error: string | null;
  
  // Settings
  theme: 'light' | 'dark' | 'auto';
  language: string;
  notifications: boolean;
  
  // Actions
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setTheme: (theme: 'light' | 'dark' | 'auto') => void;
  setLanguage: (language: string) => void;
  setNotifications: (enabled: boolean) => void;
  
  // Persistence
  hydrate: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  isLoading: false,
  error: null,
  theme: 'auto',
  language: 'en',
  notifications: true,
  
  // Actions
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  
  setTheme: (theme) => {
    set({ theme });
    storage.set('theme', theme);
  },
  
  setLanguage: (language) => {
    set({ language });
    storage.set('language', language);
  },
  
  setNotifications: (enabled) => {
    set({ notifications: enabled });
    storage.set('notifications', enabled.toString());
  },
  
  // Load persisted state
  hydrate: () => {
    const theme = storage.getString('theme') as 'light' | 'dark' | 'auto';
    const language = storage.getString('language');
    const notifications = storage.getString('notifications');
    
    set({
      theme: theme || 'auto',
      language: language || 'en',
      notifications: notifications !== 'false',
    });
  },
}));