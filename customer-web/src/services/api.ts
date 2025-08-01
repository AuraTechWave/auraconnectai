import axios, { AxiosInstance } from 'axios';
import { toast } from 'react-toastify';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

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

    // Response interceptor to handle errors
    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('customerToken');
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
    const response = await this.api.post('/customers/auth/register', data);
    return response.data;
  }

  async login(email: string, password: string) {
    const response = await this.api.post('/customers/auth/login', { email, password });
    return response.data;
  }

  async logout() {
    const response = await this.api.post('/customers/auth/logout');
    localStorage.removeItem('customerToken');
    return response.data;
  }

  // Menu endpoints
  async getCategories() {
    const response = await this.api.get('/menu/public/categories');
    return response.data;
  }

  async getMenuItems(params?: any) {
    const response = await this.api.get('/menu/public/items', { params });
    return response.data;
  }

  async getMenuItem(id: number) {
    const response = await this.api.get(`/menu/public/items/${id}`);
    return response.data;
  }

  // Order endpoints
  async createOrder(data: any) {
    const response = await this.api.post('/orders', data);
    return response.data;
  }

  async getMyOrders(params?: any) {
    const response = await this.api.get('/orders/my-orders', { params });
    return response.data;
  }

  async getOrder(id: number) {
    const response = await this.api.get(`/orders/${id}`);
    return response.data;
  }

  // Customer profile endpoints
  async getProfile() {
    const response = await this.api.get('/customers/profile');
    return response.data;
  }

  async updateProfile(data: any) {
    const response = await this.api.put('/customers/profile', data);
    return response.data;
  }

  // Reservation endpoints (to be implemented in backend)
  async createReservation(data: any) {
    const response = await this.api.post('/reservations', data);
    return response.data;
  }

  async getMyReservations(params?: any) {
    const response = await this.api.get('/reservations/my-reservations', { params });
    return response.data;
  }

  async cancelReservation(id: number) {
    const response = await this.api.delete(`/reservations/${id}`);
    return response.data;
  }
}

export default new ApiService();