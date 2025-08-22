import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('customerToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('customerToken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const menuApi = {
  getCategories: () => api.get('/api/menu/categories?active_only=true'),
  getCategoryItems: (categoryId) => api.get(`/api/menu/categories/${categoryId}`),
  getMenuItems: (params) => api.get('/api/menu/items', { params }),
  getMenuItem: (itemId) => api.get(`/api/menu/items/${itemId}`),
  searchMenu: (query) => api.get('/api/menu/search', { params: { q: query } }),
};

export const orderApi = {
  createOrder: (orderData) => api.post('/api/orders', orderData),
  getOrder: (orderId) => api.get(`/api/orders/${orderId}`),
  getMyOrders: () => api.get('/api/orders/my-orders'),
  trackOrder: (orderId) => api.get(`/api/orders/${orderId}/track`),
  cancelOrder: (orderId) => api.post(`/api/orders/${orderId}/cancel`),
};

export const customerApi = {
  register: (data) => api.post('/api/customers/register', data),
  login: (credentials) => api.post('/api/customers/login', credentials),
  getProfile: () => api.get('/api/customers/profile'),
  updateProfile: (data) => api.put('/api/customers/profile', data),
  getAddresses: () => api.get('/api/customers/addresses'),
  addAddress: (address) => api.post('/api/customers/addresses', address),
  updateAddress: (id, address) => api.put(`/api/customers/addresses/${id}`, address),
  deleteAddress: (id) => api.delete(`/api/customers/addresses/${id}`),
  getPreferences: () => api.get('/api/customers/preferences'),
  updatePreferences: (preferences) => api.put('/api/customers/preferences', preferences),
};

export const paymentApi = {
  processPayment: (paymentData) => api.post('/api/payments/process', paymentData),
  getPaymentMethods: () => api.get('/api/payments/methods'),
  addPaymentMethod: (method) => api.post('/api/payments/methods', method),
  deletePaymentMethod: (id) => api.delete(`/api/payments/methods/${id}`),
  calculateTip: (amount, percentage) => api.post('/api/payments/calculate-tip', { amount, percentage }),
};

export const loyaltyApi = {
  getPoints: () => api.get('/api/loyalty/points'),
  getRewards: () => api.get('/api/loyalty/rewards'),
  redeemReward: (rewardId) => api.post(`/api/loyalty/rewards/${rewardId}/redeem`),
  getHistory: () => api.get('/api/loyalty/history'),
};

export const promotionsApi = {
  getActivePromotions: () => api.get('/api/promotions/active'),
  applyPromoCode: (code) => api.post('/api/promotions/apply', { code }),
  validatePromoCode: (code) => api.get(`/api/promotions/validate/${code}`),
};

export const feedbackApi = {
  submitFeedback: (feedback) => api.post('/api/feedback', feedback),
  getMyFeedback: () => api.get('/api/feedback/my-feedback'),
};

export default api;