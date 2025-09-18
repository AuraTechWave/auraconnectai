import api from './api';

interface LoginCredentials {
  email: string;
  password: string;
}

interface RegisterData {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  phone?: string;
}

interface AuthResponse {
  customer: {
    id: string;
    email: string;
    firstName: string;
    lastName: string;
    phone?: string;
  };
  token: string;
  refreshToken?: string;
}

export const customerApi = {
  // Auth endpoints
  login: (credentials: LoginCredentials) => 
    api.post<AuthResponse>('/api/v1/auth/login', credentials),
    
  register: (data: RegisterData) => 
    api.post<AuthResponse>('/api/v1/auth/register', data),
    
  logout: () => 
    api.post('/api/v1/auth/logout'),
    
  refreshToken: (refreshToken: string) => 
    api.post('/api/v1/auth/refresh', { refresh_token: refreshToken }),
    
  // Profile endpoints
  getProfile: () => 
    api.get('/api/v1/customers/profile'),
    
  updateProfile: (data: Partial<RegisterData>) => 
    api.put('/api/v1/customers/profile', data),
    
  // Address endpoints
  getAddresses: () => 
    api.get('/api/v1/customers/addresses'),
    
  addAddress: (address: any) => 
    api.post('/api/v1/customers/addresses', address),
    
  updateAddress: (id: string, address: any) => 
    api.put(`/api/v1/customers/addresses/${id}`, address),
    
  deleteAddress: (id: string) => 
    api.delete(`/api/v1/customers/addresses/${id}`),
    
  // Order endpoints
  getOrders: () => 
    api.get('/api/v1/customers/orders'),
    
  getOrder: (orderId: string) => 
    api.get(`/api/v1/customers/orders/${orderId}`),
    
  // Loyalty endpoints
  getLoyaltyPoints: () => 
    api.get('/api/v1/customers/loyalty'),
    
  getRewards: () => 
    api.get('/api/v1/customers/rewards'),
};

export default customerApi;