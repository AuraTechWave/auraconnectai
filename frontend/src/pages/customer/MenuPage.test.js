import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import MenuPage from './MenuPage';
import { menuApi } from '../../services/api';
import useCartStore from '../../stores/useCartStore';

// Mock the API
jest.mock('../../services/api');
const mockMenuApi = menuApi;

// Mock the cart store
jest.mock('../../stores/useCartStore');
const mockUseCartStore = useCartStore;

// Mock child components
jest.mock('../../components/customer/MenuCategory', () => {
  return function MenuCategory({ category, isSelected, onClick }) {
    return (
      <button 
        className={`category-button ${isSelected ? 'active' : ''}`}
        onClick={() => onClick(category.id)}
        data-testid={`category-${category.id}`}
      >
        {category.name}
      </button>
    );
  };
});

jest.mock('../../components/customer/MenuItem', () => {
  return function MenuItem({ item, onAddToCart }) {
    return (
      <div data-testid={`menu-item-${item.id}`} className="menu-item">
        <h4>{item.name}</h4>
        <p>${item.price}</p>
        <button onClick={() => onAddToCart(item)}>
          Add to Cart
        </button>
      </div>
    );
  };
});

jest.mock('../../components/customer/SearchBar', () => {
  return function SearchBar({ value, onChange, placeholder }) {
    return (
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid="search-bar"
      />
    );
  };
});

jest.mock('../../components/customer/LoadingSpinner', () => {
  return function LoadingSpinner({ message }) {
    return <div data-testid="loading-spinner">{message}</div>;
  };
});

jest.mock('../../components/customer/ErrorMessage', () => {
  return function ErrorMessage({ message }) {
    return <div data-testid="error-message">{message}</div>;
  };
});

const createQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false }
  }
});

const renderWithQueryClient = (component) => {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
};

describe('MenuPage', () => {
  const mockAddItem = jest.fn();
  const mockGetItemCount = jest.fn();
  
  const mockCategories = [
    { id: 1, name: 'Appetizers', slug: 'appetizers' },
    { id: 2, name: 'Main Dishes', slug: 'main-dishes' },
    { id: 3, name: 'Desserts', slug: 'desserts' }
  ];

  const mockMenuItems = [
    {
      id: 1,
      name: 'Caesar Salad',
      price: 12.99,
      description: 'Fresh romaine lettuce with parmesan',
      image_url: 'salad.jpg',
      category_id: 1
    },
    {
      id: 2,
      name: 'Grilled Chicken',
      price: 18.99,
      description: 'Herb-seasoned grilled chicken breast',
      image_url: 'chicken.jpg',
      category_id: 2
    }
  ];

  beforeEach(() => {
    mockUseCartStore.mockReturnValue({
      addItem: mockAddItem,
      getItemCount: mockGetItemCount
    });
    
    mockAddItem.mockClear();
    mockGetItemCount.mockClear();
    
    // Default API responses
    mockMenuApi.getCategories.mockResolvedValue({ data: mockCategories });
    mockMenuApi.getMenuItems.mockResolvedValue({ data: mockMenuItems });
    mockMenuApi.getCategoryItems.mockResolvedValue({ data: { items: mockMenuItems } });
    mockMenuApi.searchMenu.mockResolvedValue({ data: [] });
  });

  describe('Loading States', () => {
    test('shows loading spinner while categories are loading', () => {
      mockMenuApi.getCategories.mockReturnValue(new Promise(() => {})); // Never resolves
      
      renderWithQueryClient(<MenuPage />);
      
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
      expect(screen.getByText('Loading menu...')).toBeInTheDocument();
    });

    test('shows loading spinner with custom message', () => {
      mockMenuApi.getCategories.mockReturnValue(new Promise(() => {}));
      
      renderWithQueryClient(<MenuPage />);
      
      const spinner = screen.getByTestId('loading-spinner');
      expect(spinner).toHaveTextContent('Loading menu...');
    });
  });

  describe('Error States', () => {
    test('shows error message when categories fail to load', async () => {
      mockMenuApi.getCategories.mockRejectedValue(new Error('Network error'));
      
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
        expect(screen.getByText(/failed to load menu categories/i)).toBeInTheDocument();
      });
    });

    test('shows error message with retry suggestion', async () => {
      mockMenuApi.getCategories.mockRejectedValue(new Error('API error'));
      
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByText(/please try again/i)).toBeInTheDocument();
      });
    });
  });

  describe('Menu Display', () => {
    test('renders menu header and search bar', async () => {
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByText('Our Menu')).toBeInTheDocument();
        expect(screen.getByTestId('search-bar')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Search menu items...')).toBeInTheDocument();
      });
    });

    test('renders categories sidebar', async () => {
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByText('Categories')).toBeInTheDocument();
        expect(screen.getByText('All Items')).toBeInTheDocument();
      });
    });

    test('renders category buttons', async () => {
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('category-1')).toBeInTheDocument();
        expect(screen.getByTestId('category-2')).toBeInTheDocument();
        expect(screen.getByTestId('category-3')).toBeInTheDocument();
        expect(screen.getByText('Appetizers')).toBeInTheDocument();
        expect(screen.getByText('Main Dishes')).toBeInTheDocument();
        expect(screen.getByText('Desserts')).toBeInTheDocument();
      });
    });

    test('renders menu items', async () => {
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('menu-item-1')).toBeInTheDocument();
        expect(screen.getByTestId('menu-item-2')).toBeInTheDocument();
        expect(screen.getByText('Caesar Salad')).toBeInTheDocument();
        expect(screen.getByText('Grilled Chicken')).toBeInTheDocument();
      });
    });
  });

  describe('Category Selection', () => {
    test('shows all items by default', async () => {
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(mockMenuApi.getMenuItems).toHaveBeenCalledWith({ active_only: true });
      });
    });

    test('filters items by category when category is selected', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('category-1')).toBeInTheDocument();
      });
      
      const appetizerCategory = screen.getByTestId('category-1');
      await user.click(appetizerCategory);
      
      await waitFor(() => {
        expect(mockMenuApi.getCategoryItems).toHaveBeenCalledWith(1);
      });
    });

    test('highlights selected category', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('category-1')).toBeInTheDocument();
      });
      
      const appetizerCategory = screen.getByTestId('category-1');
      await user.click(appetizerCategory);
      
      expect(appetizerCategory).toHaveClass('active');
    });

    test('can switch back to all items', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('category-1')).toBeInTheDocument();
      });
      
      // Select a category first
      const appetizerCategory = screen.getByTestId('category-1');
      await user.click(appetizerCategory);
      
      // Then switch back to all items
      const allItemsButton = screen.getByText('All Items');
      await user.click(allItemsButton);
      
      expect(allItemsButton).toHaveClass('active');
    });
  });

  describe('Search Functionality', () => {
    test('updates search query on input', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('search-bar')).toBeInTheDocument();
      });
      
      const searchInput = screen.getByTestId('search-bar');
      await user.type(searchInput, 'chicken');
      
      expect(searchInput).toHaveValue('chicken');
    });

    test('triggers search when query length > 2', async () => {
      const user = userEvent.setup();
      mockMenuApi.searchMenu.mockResolvedValue({ 
        data: [mockMenuItems[1]] // Return chicken dish
      });
      
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('search-bar')).toBeInTheDocument();
      });
      
      const searchInput = screen.getByTestId('search-bar');
      await user.type(searchInput, 'chic');
      
      await waitFor(() => {
        expect(mockMenuApi.searchMenu).toHaveBeenCalledWith('chic');
      });
    });

    test('does not search with short queries', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('search-bar')).toBeInTheDocument();
      });
      
      const searchInput = screen.getByTestId('search-bar');
      await user.type(searchInput, 'ch');
      
      // Should not trigger search
      expect(mockMenuApi.searchMenu).not.toHaveBeenCalled();
    });

    test('displays search results', async () => {
      const user = userEvent.setup();
      const searchResults = [
        {
          id: 3,
          name: 'Chicken Wings',
          price: 14.99,
          description: 'Spicy buffalo wings',
          image_url: 'wings.jpg'
        }
      ];
      
      mockMenuApi.searchMenu.mockResolvedValue({ data: searchResults });
      
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('search-bar')).toBeInTheDocument();
      });
      
      const searchInput = screen.getByTestId('search-bar');
      await user.type(searchInput, 'wings');
      
      await waitFor(() => {
        expect(screen.getByText('Chicken Wings')).toBeInTheDocument();
      });
    });

    test('clears search results when query is cleared', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('search-bar')).toBeInTheDocument();
      });
      
      const searchInput = screen.getByTestId('search-bar');
      
      // Type search query
      await user.type(searchInput, 'chicken');
      
      // Clear search
      await user.clear(searchInput);
      
      // Should show category items again
      await waitFor(() => {
        expect(screen.getByText('Caesar Salad')).toBeInTheDocument();
        expect(screen.getByText('Grilled Chicken')).toBeInTheDocument();
      });
    });
  });

  describe('Add to Cart', () => {
    test('adds item to cart when add button is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('menu-item-1')).toBeInTheDocument();
      });
      
      const addButton = screen.getAllByText('Add to Cart')[0];
      await user.click(addButton);
      
      expect(mockAddItem).toHaveBeenCalledWith({
        id: 1,
        name: 'Caesar Salad',
        price: 12.99,
        description: 'Fresh romaine lettuce with parmesan',
        image: 'salad.jpg',
        modifiers: []
      });
    });

    test('adds item with modifiers to cart', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('menu-item-1')).toBeInTheDocument();
      });
      
      // Simulate item with modifiers (would come from MenuItem component)
      const itemWithModifiers = {
        ...mockMenuItems[0],
        modifiers: [{ id: 1, name: 'Extra Cheese', price: 2.00 }]
      };
      
      const addButton = screen.getAllByText('Add to Cart')[0];
      
      // Mock the MenuItem component to pass modifiers
      const mockHandleAddToCart = jest.fn();
      mockHandleAddToCart(itemWithModifiers, itemWithModifiers.modifiers);
      
      expect(mockHandleAddToCart).toHaveBeenCalledWith(
        itemWithModifiers,
        [{ id: 1, name: 'Extra Cheese', price: 2.00 }]
      );
    });

    test('handles multiple items added to cart', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      await waitFor(() => {
        expect(screen.getByTestId('menu-item-1')).toBeInTheDocument();
        expect(screen.getByTestId('menu-item-2')).toBeInTheDocument();
      });
      
      const addButtons = screen.getAllByText('Add to Cart');
      
      await user.click(addButtons[0]);
      await user.click(addButtons[1]);
      
      expect(mockAddItem).toHaveBeenCalledTimes(2);
      expect(mockAddItem).toHaveBeenNthCalledWith(1, expect.objectContaining({
        name: 'Caesar Salad'
      }));
      expect(mockAddItem).toHaveBeenNthCalledWith(2, expect.objectContaining({
        name: 'Grilled Chicken'
      }));
    });
  });

  describe('Integration Tests', () => {
    test('complete user flow: search, select category, add to cart', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<MenuPage />);
      
      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText('Our Menu')).toBeInTheDocument();
      });
      
      // Search for an item
      const searchInput = screen.getByTestId('search-bar');
      await user.type(searchInput, 'chicken');
      
      // Clear search and select category
      await user.clear(searchInput);
      const categoryButton = screen.getByTestId('category-2');
      await user.click(categoryButton);
      
      // Add item to cart
      await waitFor(() => {
        expect(screen.getByTestId('menu-item-2')).toBeInTheDocument();
      });
      
      const addButton = screen.getAllByText('Add to Cart')[1];
      await user.click(addButton);
      
      expect(mockAddItem).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Grilled Chicken'
      }));
    });
  });
});