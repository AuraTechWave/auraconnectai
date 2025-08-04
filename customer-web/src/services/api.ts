import axios, { AxiosInstance } from 'axios';
import { toast } from 'react-toastify';
import { mockApi } from './mockData';
import secureStorage from './secureStorage';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
const USE_MOCK_DATA = true; // Always use mock data for now

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.api.interceptors.request.use(
      (config) => {
        const token = secureStorage.getToken();
        if (token && !secureStorage.isTokenExpired()) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor to handle errors
    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          secureStorage.clearAll();
          window.location.href = '/login';
        } else if (error.response?.status >= 500) {
          toast.error('Server error. Please try again later.');
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth endpoints
  async register(data: any) {
    if (USE_MOCK_DATA) {
      return mockApi.register(data);
    }
    const response = await this.api.post('/customers/auth/register', data);
    return response.data;
  }

  async login(email: string, password: string) {
    if (USE_MOCK_DATA) {
      const result = await mockApi.login(email, password);
      if (result.data.access_token) {
        secureStorage.setToken(result.data.access_token);
      }
      return result.data;
    }
    const response = await this.api.post('/customers/auth/login', { email, password });
    if (response.data.access_token) {
      secureStorage.setToken(response.data.access_token);
    }
    return response.data;
  }

  async logout() {
    try {
      const response = await this.api.post('/customers/auth/logout');
      return response.data;
    } finally {
      secureStorage.clearAll();
    }
  }

  // Menu endpoints
  async getCategories() {
    if (USE_MOCK_DATA) {
      return mockApi.getCategories();
    }
    const response = await this.api.get('/menu/public/categories');
    return response.data;
  }

  async getMenuItems(params?: any) {
    if (USE_MOCK_DATA) {
      return mockApi.getMenuItems(params);
    }
    const response = await this.api.get('/menu/public/items', { params });
    return response.data;
  }

  async getMenuItem(id: number) {
    if (USE_MOCK_DATA) {
      const items = await mockApi.getMenuItems();
      const item = items.data.find((i: any) => i.id === id);
      return { data: item };
    }
    const response = await this.api.get(`/menu/public/items/${id}`);
    return response.data;
  }

  // Order endpoints
  async createOrder(data: any) {
    if (USE_MOCK_DATA) {
      return mockApi.createOrder(data.items || []);
    }
    const response = await this.api.post('/orders', data);
    return response.data;
  }

  async getOrderHistory(params?: any) {
    if (USE_MOCK_DATA) {
      return mockApi.getOrderHistory();
    }
    const response = await this.api.get('/orders/my-orders', { params });
    return response.data;
  }

  async getOrder(id: number) {
    if (USE_MOCK_DATA) {
      return mockApi.getOrder(id);
    }
    const response = await this.api.get(`/orders/${id}`);
    return response.data;
  }

  // Customer profile endpoints
  async getProfile() {
    if (USE_MOCK_DATA) {
      const { mockCustomer } = await import('./mockData');
      return { data: mockCustomer };
    }
    const response = await this.api.get('/customers/profile');
    return response.data;
  }

  async updateProfile(data: any) {
    const response = await this.api.put('/customers/profile', data);
    return response.data;
  }

  // Reservation endpoints
  async createReservation(data: any) {
    if (USE_MOCK_DATA) {
      return mockApi.createReservation(data);
    }
    const response = await this.api.post('/reservations', data);
    return response.data;
  }

  async getMyReservations(params?: any) {
    if (USE_MOCK_DATA) {
      return mockApi.getMyReservations();
    }
    const response = await this.api.get('/reservations/my-reservations', { params });
    return response.data;
  }

  async getReservation(id: number) {
    if (USE_MOCK_DATA) {
      return mockApi.getReservation(id);
    }
    const response = await this.api.get(`/reservations/${id}`);
    return response.data;
  }

  async updateReservation(id: number, data: any) {
    if (USE_MOCK_DATA) {
      return mockApi.updateReservation(id, data);
    }
    const response = await this.api.put(`/reservations/${id}`, data);
    return response.data;
  }

  async cancelReservation(id: number, data?: any) {
    if (USE_MOCK_DATA) {
      return mockApi.cancelReservation(id);
    }
    const response = await this.api.post(`/reservations/${id}/cancel`, data || {});
    return response.data;
  }

  async checkReservationAvailability(date: string, partySize: number) {
    if (USE_MOCK_DATA) {
      return mockApi.checkAvailability(date, partySize);
    }
    const response = await this.api.get('/reservations/availability', {
      params: { date, party_size: partySize }
    });
    return response.data;
  }
}

export default new ApiService();