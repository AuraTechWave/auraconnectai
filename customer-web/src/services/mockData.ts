// Mock data for development without backend

export const mockMenuItems = [
  {
    id: 1,
    name: "Classic Burger",
    description: "Juicy beef patty with lettuce, tomato, onion, and our special sauce",
    price: 12.99,
    category: { id: 1, name: "Burgers" },
    image_url: "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400",
    is_available: true,
    is_featured: true,
    tags: ["Popular", "Chef's Special"],
    dietary_info: {
      calories: 650,
      is_vegetarian: false,
      is_vegan: false,
      is_gluten_free: false,
      allergens: ["Gluten", "Dairy"]
    }
  },
  {
    id: 2,
    name: "Veggie Delight Burger",
    description: "House-made black bean patty with avocado, sprouts, and tahini sauce",
    price: 11.99,
    category: { id: 1, name: "Burgers" },
    image_url: "https://images.unsplash.com/photo-1520072959219-c595dc870360?w=400",
    is_available: true,
    is_featured: false,
    tags: ["Vegetarian", "Healthy"],
    dietary_info: {
      calories: 480,
      is_vegetarian: true,
      is_vegan: true,
      is_gluten_free: false,
      allergens: ["Gluten", "Sesame"]
    }
  },
  {
    id: 3,
    name: "Caesar Salad",
    description: "Crisp romaine lettuce, parmesan cheese, croutons, and our signature Caesar dressing",
    price: 9.99,
    category: { id: 2, name: "Salads" },
    image_url: "https://images.unsplash.com/photo-1550304943-4f24f54ddde9?w=400",
    is_available: true,
    is_featured: false,
    tags: ["Light", "Classic"],
    dietary_info: {
      calories: 350,
      is_vegetarian: true,
      is_vegan: false,
      is_gluten_free: false,
      allergens: ["Dairy", "Eggs", "Fish", "Gluten"]
    }
  },
  {
    id: 4,
    name: "Margherita Pizza",
    description: "Fresh mozzarella, tomatoes, basil on our signature thin crust",
    price: 14.99,
    category: { id: 3, name: "Pizza" },
    image_url: "https://images.unsplash.com/photo-1574126154517-d1e0d89ef734?w=400",
    is_available: true,
    is_featured: true,
    tags: ["Italian", "Vegetarian"],
    dietary_info: {
      calories: 850,
      is_vegetarian: true,
      is_vegan: false,
      is_gluten_free: false,
      allergens: ["Gluten", "Dairy"]
    }
  },
  {
    id: 5,
    name: "Grilled Salmon",
    description: "Atlantic salmon with lemon herb butter, served with seasonal vegetables",
    price: 18.99,
    category: { id: 4, name: "Main Courses" },
    image_url: "https://images.unsplash.com/photo-1485921325833-c519f76c4927?w=400",
    is_available: true,
    is_featured: true,
    tags: ["Healthy", "Gluten-Free"],
    dietary_info: {
      calories: 520,
      is_vegetarian: false,
      is_vegan: false,
      is_gluten_free: true,
      allergens: ["Fish"]
    }
  },
  {
    id: 6,
    name: "Chocolate Lava Cake",
    description: "Warm chocolate cake with a molten center, served with vanilla ice cream",
    price: 7.99,
    category: { id: 5, name: "Desserts" },
    image_url: "https://images.unsplash.com/photo-1624353365286-3f8d62daad51?w=400",
    is_available: true,
    is_featured: false,
    tags: ["Sweet", "Indulgent"],
    dietary_info: {
      calories: 450,
      is_vegetarian: true,
      is_vegan: false,
      is_gluten_free: false,
      allergens: ["Gluten", "Dairy", "Eggs"]
    }
  },
  {
    id: 7,
    name: "Fresh Orange Juice",
    description: "Freshly squeezed orange juice",
    price: 4.99,
    category: { id: 6, name: "Beverages" },
    image_url: "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=400",
    is_available: true,
    is_featured: false,
    tags: ["Fresh", "Healthy"],
    dietary_info: {
      calories: 120,
      is_vegetarian: true,
      is_vegan: true,
      is_gluten_free: true,
      allergens: []
    }
  },
  {
    id: 8,
    name: "Chicken Wings",
    description: "Crispy wings tossed in your choice of buffalo, BBQ, or honey garlic sauce",
    price: 10.99,
    category: { id: 7, name: "Appetizers" },
    image_url: "https://images.unsplash.com/photo-1608039829572-78524f79c4c7?w=400",
    is_available: true,
    is_featured: true,
    tags: ["Spicy", "Party Favorite"],
    dietary_info: {
      calories: 580,
      is_vegetarian: false,
      is_vegan: false,
      is_gluten_free: true,
      allergens: ["Dairy"]
    }
  }
];

export const mockCategories = [
  { id: 1, name: "Burgers", description: "Our signature burgers", display_order: 1 },
  { id: 2, name: "Salads", description: "Fresh and healthy salads", display_order: 2 },
  { id: 3, name: "Pizza", description: "Wood-fired pizzas", display_order: 3 },
  { id: 4, name: "Main Courses", description: "Hearty main dishes", display_order: 4 },
  { id: 5, name: "Desserts", description: "Sweet treats", display_order: 5 },
  { id: 6, name: "Beverages", description: "Refreshing drinks", display_order: 6 },
  { id: 7, name: "Appetizers", description: "Start your meal right", display_order: 7 }
];

export const mockCustomer = {
  id: 1,
  email: "demo@example.com",
  first_name: "Demo",
  last_name: "User",
  phone: "+1234567890",
  created_at: new Date().toISOString()
};

export const mockOrders = [
  {
    id: 1,
    order_number: "ORD-2024-001",
    customer_id: 1,
    status: "delivered",
    order_type: "pickup",
    payment_status: "paid",
    total_amount: 45.97,
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    items: [
      { 
        id: 1, 
        menu_item: mockMenuItems[0], 
        quantity: 2, 
        price: mockMenuItems[0].price,
        special_instructions: "No pickles please"
      },
      { 
        id: 2, 
        menu_item: mockMenuItems[2], 
        quantity: 1, 
        price: mockMenuItems[2].price 
      }
    ]
  },
  {
    id: 2,
    order_number: "ORD-2024-002",
    customer_id: 1,
    status: "preparing",
    order_type: "delivery",
    payment_status: "paid",
    total_amount: 18.99,
    created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    items: [
      { 
        id: 3, 
        menu_item: mockMenuItems[4], 
        quantity: 1, 
        price: mockMenuItems[4].price 
      }
    ]
  },
  {
    id: 3,
    order_number: "ORD-2024-003",
    customer_id: 1,
    status: "confirmed",
    order_type: "pickup",
    payment_status: "paid",
    total_amount: 32.50,
    created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    items: [
      { 
        id: 4, 
        menu_item: mockMenuItems[3], 
        quantity: 1, 
        price: mockMenuItems[3].price 
      },
      { 
        id: 5, 
        menu_item: mockMenuItems[5], 
        quantity: 2, 
        price: mockMenuItems[5].price 
      }
    ]
  }
];

// Mock API responses with delay to simulate network
export const mockApi = {
  delay: (ms: number = 500) => new Promise(resolve => setTimeout(resolve, ms)),
  
  async getMenuItems(params?: any) {
    await this.delay();
    let items = [...mockMenuItems];
    
    // Filter by category if provided
    if (params?.category_id) {
      items = items.filter(item => item.category.id === params.category_id);
    }
    
    // Filter by search query if provided
    if (params?.query) {
      const query = params.query.toLowerCase();
      items = items.filter(item => 
        item.name.toLowerCase().includes(query) ||
        item.description?.toLowerCase().includes(query)
      );
    }
    
    return { data: items };
  },
  
  async getCategories() {
    await this.delay(300);
    return { data: mockCategories };
  },
  
  async login(email: string, password: string) {
    await this.delay();
    if (email === "demo@example.com" && password === "demo123") {
      return {
        data: {
          access_token: "mock-jwt-token",
          customer: mockCustomer
        }
      };
    }
    throw new Error("Invalid credentials");
  },
  
  async register(data: any) {
    await this.delay();
    return {
      data: {
        access_token: "mock-jwt-token",
        customer: {
          ...mockCustomer,
          email: data.email,
          first_name: data.first_name,
          last_name: data.last_name
        }
      }
    };
  },
  
  async getOrderHistory() {
    await this.delay();
    return { data: mockOrders };
  },

  async getOrder(orderId: number) {
    await this.delay();
    const order = mockOrders.find(o => o.id === orderId);
    if (!order) {
      throw new Error('Order not found');
    }
    return { data: order };
  },
  
  async createOrder(items: any[]) {
    await this.delay();
    const total = items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    return {
      data: {
        id: mockOrders.length + 1,
        order_number: `ORD-2024-${String(mockOrders.length + 1).padStart(3, '0')}`,
        status: "pending",
        total_amount: total,
        created_at: new Date().toISOString(),
        items
      }
    };
  },

  async createReservation(data: any) {
    await this.delay();
    return {
      data: {
        id: Math.floor(Math.random() * 1000) + 1,
        customer_id: 1,
        reservation_date: data.date,
        reservation_time: data.time,
        party_size: data.party_size,
        special_requests: data.special_requests,
        status: "pending",
        confirmation_code: `RES${Math.random().toString(36).substr(2, 9).toUpperCase()}`,
        created_at: new Date().toISOString()
      }
    };
  },

  async getMyReservations() {
    await this.delay();
    return {
      data: {
        reservations: [
          {
            id: 1,
            customer_id: 1,
            reservation_date: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            reservation_time: "19:00:00",
            party_size: 4,
            status: "confirmed",
            confirmation_code: "RESABC123",
            created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString()
          },
          {
            id: 2,
            customer_id: 1,
            reservation_date: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            reservation_time: "20:00:00",
            party_size: 2,
            status: "completed",
            confirmation_code: "RESXYZ789",
            created_at: new Date(Date.now() - 15 * 24 * 60 * 60 * 1000).toISOString()
          }
        ],
        total: 2,
        page: 1,
        page_size: 20
      }
    };
  },

  async getReservation(id: number) {
    await this.delay();
    return {
      data: {
        id,
        customer_id: 1,
        reservation_date: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        reservation_time: "19:00:00",
        party_size: 4,
        status: "confirmed",
        confirmation_code: "RESABC123",
        created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
        customer_name: "Demo User",
        customer_email: "demo@example.com",
        customer_phone: "+1234567890"
      }
    };
  },

  async updateReservation(id: number, data: any) {
    await this.delay();
    return {
      data: {
        id,
        ...data,
        updated_at: new Date().toISOString()
      }
    };
  },

  async cancelReservation(id: number) {
    await this.delay();
    return {
      data: {
        id,
        status: "cancelled",
        updated_at: new Date().toISOString()
      }
    };
  },

  async checkAvailability(date: string, partySize: number) {
    await this.delay();
    const times = [];
    for (let hour = 11; hour <= 21; hour++) {
      for (let min = 0; min < 60; min += 30) {
        if (hour === 21 && min > 30) break;
        times.push(`${hour.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}:00`);
      }
    }
    return {
      data: {
        date,
        available_times: times,
        is_fully_booked: false
      }
    };
  }
};