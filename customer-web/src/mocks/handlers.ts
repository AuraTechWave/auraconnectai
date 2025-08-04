import { http, HttpResponse } from 'msw';
import { mockMenuItems, mockCategories, mockCustomer, mockOrders } from '../services/mockData';

const API_BASE = 'http://localhost:8000/api/v1';

export const handlers = [
  // Auth endpoints
  http.post(`${API_BASE}/customers/auth/login`, async ({ request }) => {
    const { email, password } = await request.json() as { email: string; password: string };
    
    if (email === 'demo@example.com' && password === 'demo123') {
      return HttpResponse.json({
        access_token: 'mock-jwt-token',
        customer: mockCustomer,
      });
    }
    
    return HttpResponse.json(
      { detail: 'Invalid credentials' },
      { status: 401 }
    );
  }),

  http.post(`${API_BASE}/customers/auth/register`, async ({ request }) => {
    const data = await request.json();
    
    return HttpResponse.json({
      access_token: 'mock-jwt-token',
      customer: {
        ...mockCustomer,
        email: data.email,
        first_name: data.first_name,
        last_name: data.last_name,
      },
    });
  }),

  http.post(`${API_BASE}/customers/auth/logout`, () => {
    return HttpResponse.json({ message: 'Logged out successfully' });
  }),

  // Menu endpoints
  http.get(`${API_BASE}/menu/public/categories`, () => {
    return HttpResponse.json({ data: mockCategories });
  }),

  http.get(`${API_BASE}/menu/public/items`, ({ request }) => {
    const url = new URL(request.url);
    const categoryId = url.searchParams.get('category_id');
    const query = url.searchParams.get('query');
    
    let items = [...mockMenuItems];
    
    if (categoryId) {
      items = items.filter(item => item.category.id === parseInt(categoryId));
    }
    
    if (query) {
      const searchQuery = query.toLowerCase();
      items = items.filter(item =>
        item.name.toLowerCase().includes(searchQuery) ||
        item.description?.toLowerCase().includes(searchQuery)
      );
    }
    
    return HttpResponse.json({ data: items });
  }),

  http.get(`${API_BASE}/menu/public/items/:id`, ({ params }) => {
    const { id } = params;
    const item = mockMenuItems.find(i => i.id === parseInt(id as string));
    
    if (!item) {
      return HttpResponse.json(
        { detail: 'Item not found' },
        { status: 404 }
      );
    }
    
    return HttpResponse.json({ data: item });
  }),

  // Order endpoints
  http.post(`${API_BASE}/orders`, async ({ request }) => {
    const data = await request.json();
    
    return HttpResponse.json({
      data: {
        id: Math.floor(Math.random() * 1000) + 1,
        order_number: `ORD-2024-${String(Math.floor(Math.random() * 1000)).padStart(3, '0')}`,
        status: 'pending',
        total_amount: data.items.reduce((sum: number, item: any) => 
          sum + (item.price * item.quantity), 0
        ),
        created_at: new Date().toISOString(),
        items: data.items,
      },
    });
  }),

  http.get(`${API_BASE}/orders/my-orders`, () => {
    return HttpResponse.json({ data: mockOrders });
  }),

  http.get(`${API_BASE}/orders/:id`, ({ params }) => {
    const { id } = params;
    const order = mockOrders.find(o => o.id === parseInt(id as string));
    
    if (!order) {
      return HttpResponse.json(
        { detail: 'Order not found' },
        { status: 404 }
      );
    }
    
    return HttpResponse.json({ data: order });
  }),

  // Reservation endpoints
  http.post(`${API_BASE}/reservations`, async ({ request }) => {
    const data = await request.json();
    
    return HttpResponse.json({
      data: {
        id: Math.floor(Math.random() * 1000) + 1,
        customer_id: 1,
        reservation_date: data.date,
        reservation_time: data.time,
        party_size: data.party_size,
        special_requests: data.special_requests,
        status: 'pending',
        confirmation_code: `RES${Math.random().toString(36).substr(2, 9).toUpperCase()}`,
        created_at: new Date().toISOString(),
      },
    });
  }),

  http.get(`${API_BASE}/reservations/my-reservations`, () => {
    return HttpResponse.json({
      data: {
        reservations: [
          {
            id: 1,
            customer_id: 1,
            reservation_date: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            reservation_time: '19:00:00',
            party_size: 4,
            status: 'confirmed',
            confirmation_code: 'RESABC123',
            created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    });
  }),

  http.get(`${API_BASE}/reservations/availability`, ({ request }) => {
    const url = new URL(request.url);
    const date = url.searchParams.get('date');
    
    const times = [];
    for (let hour = 11; hour <= 21; hour++) {
      for (let min = 0; min < 60; min += 30) {
        if (hour === 21 && min > 30) break;
        times.push(`${hour.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}:00`);
      }
    }
    
    return HttpResponse.json({
      data: {
        date,
        available_times: times,
        is_fully_booked: false,
      },
    });
  }),

  // Customer profile
  http.get(`${API_BASE}/customers/profile`, () => {
    return HttpResponse.json({ data: mockCustomer });
  }),
];