/**
 * Application configuration constants
 */

// API Configuration
export const API_CONFIG = {
  BASE_URL: process.env.API_URL || 'https://api.auraconnect.ai/api',
  TIMEOUT: 30000,
  RETRY_COUNT: 3,
  RETRY_DELAY: 1000,
};

// Authentication
export const AUTH_CONFIG = {
  TOKEN_KEY: 'auraconnect.api',
  REFRESH_TOKEN_KEY: 'auraconnect.api.refresh',
  TOKEN_STORAGE_SERVICE: 'auraconnect.api',
  TOKEN_EXPIRY_BUFFER: 300, // 5 minutes before expiry
};

// Offline Queue
export const OFFLINE_CONFIG = {
  QUEUE_KEY: 'offlineQueue',
  MAX_QUEUE_SIZE: 100,
  MAX_RETRY_COUNT: 3,
  SYNC_BATCH_SIZE: 10,
  ENCRYPT_QUEUE: true,
  QUEUE_SIZE_LIMIT: 1000,
  QUEUE_SIZE_WARNING: 800,
  ENCRYPTED_FIELDS: ['payment_info', 'sensitive_notes'],
  SYNC_RETRY_COUNT: 3,
  SYNC_RETRY_DELAY: 1000,
};

// Sync Configuration
export const SYNC_CONFIG = {
  // Queue management
  MAX_QUEUE_SIZE: 1000,
  QUEUE_SIZE_WARNING_THRESHOLD: 800,
  QUEUE_CLEANUP_THRESHOLD: 900,
  QUEUE_ITEM_TTL: 7 * 24 * 60 * 60 * 1000, // 7 days
  
  // Sync operations
  BATCH_SIZE: 100,
  PULL_URL: '/api/sync/pull',
  PUSH_URL: '/api/sync/push',
  DEFAULT_CONFLICT_STRATEGY: 'last_write_wins' as const,
  
  // Sync timing
  SYNC_INTERVAL: 300000, // 5 minutes
  BACKGROUND_SYNC_INTERVAL: 900000, // 15 minutes
  SYNC_DEBOUNCE_DELAY: 1000, // 1 second
  
  // Retry configuration
  MAX_RETRY_COUNT: 3,
  RETRY_BASE_DELAY: 1000, // 1 second
  RETRY_MAX_DELAY: 60000, // 1 minute
  RETRY_BACKOFF_FACTOR: 2,
  
  // Performance
  SYNC_TIMEOUT: 30000, // 30 seconds
  CONCURRENT_OPERATIONS: 5,
  
  // Security
  ENCRYPT_QUEUE: true,
  ENCRYPT_OFFLINE_DATA: ['payment_info', 'sensitive_notes', 'customer_data'],
};

// Storage Keys
export const STORAGE_KEYS = {
  USER: 'user',
  THEME: 'theme',
  LANGUAGE: 'language',
  NOTIFICATIONS: 'notifications',
  OFFLINE_QUEUE: 'offlineQueue',
  APP_STATE: 'appState',
};

// Cache Configuration
export const CACHE_CONFIG = {
  DEFAULT_STALE_TIME: 5 * 60 * 1000, // 5 minutes
  DEFAULT_CACHE_TIME: 10 * 60 * 1000, // 10 minutes
  LONG_STALE_TIME: 30 * 60 * 1000, // 30 minutes
  LONG_CACHE_TIME: 60 * 60 * 1000, // 1 hour
};

// UI Configuration
export const UI_CONFIG = {
  TOAST_DURATION: 3000,
  TOAST_OFFSET: 50,
  DEBOUNCE_DELAY: 300,
  ANIMATION_DURATION: 300,
  PAGE_SIZE: 20,
};

// Security Configuration
export const SECURITY_CONFIG = {
  MIN_PASSWORD_LENGTH: 8,
  PASSWORD_REGEX: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/,
  SESSION_TIMEOUT: 30 * 60 * 1000, // 30 minutes
  ENABLE_BIOMETRICS: true,
  LOG_SENSITIVE_DATA: false,
};

// Feature Flags
export const FEATURE_FLAGS = {
  ENABLE_OFFLINE_MODE: true,
  ENABLE_PUSH_NOTIFICATIONS: true,
  ENABLE_ANALYTICS: true,
  ENABLE_CRASH_REPORTING: true,
  ENABLE_BIOMETRIC_AUTH: true,
  ENABLE_DARK_MODE: true,
};

// Development Configuration
export const DEV_CONFIG = {
  ENABLE_LOGS: __DEV__,
  LOG_LEVEL: __DEV__ ? 'debug' : 'error',
  SHOW_NETWORK_LOGS: __DEV__,
  MOCK_API_DELAY: 1000,
};

// App Information
export const APP_INFO = {
  NAME: 'AuraConnect',
  VERSION: '1.0.0',
  BUILD_NUMBER: '1',
  BUNDLE_ID: 'com.auraconnect.mobile',
};