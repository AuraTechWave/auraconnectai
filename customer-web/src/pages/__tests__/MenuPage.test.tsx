import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MenuPage } from '../MenuPage';
import api from '../../services/api';

jest.mock('../../services/api');

const mockMenuItems = [
  {
    id: 1,
    name: 'Test Burger',
    description: 'A test burger',
    price: 12.99,
    category: { id: 1, name: 'Burgers' },
    is_available: true,
  },
  {
    id: 2,
    name: 'Test Salad',
    description: 'A test salad',
    price: 8.99,
    category: { id: 2, name: 'Salads' },
    is_available: true,
  },
];

const mockCategories = [
  { id: 1, name: 'Burgers', display_order: 1 },
  { id: 2, name: 'Salads', display_order: 2 },
];

describe('MenuPage', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    jest.clearAllMocks();
    (api.getCategories as jest.Mock).mockResolvedValue({ data: mockCategories });
    (api.getMenuItems as jest.Mock).mockResolvedValue({ data: mockMenuItems });
    (api.getMenuItem as jest.Mock).mockResolvedValue(mockMenuItems[0]);
  });

  const renderMenuPage = () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MenuPage />
      </QueryClientProvider>
    );
  };

  test('renders menu page with categories and items', async () => {
    renderMenuPage();

    await waitFor(() => {
      expect(screen.getByText('Our Menu')).toBeInTheDocument();
      expect(screen.getByText('Burgers')).toBeInTheDocument();
      expect(screen.getByText('Salads')).toBeInTheDocument();
      expect(screen.getByText('Test Burger')).toBeInTheDocument();
      expect(screen.getByText('Test Salad')).toBeInTheDocument();
    });
  });

  test('filters items by category when category is selected', async () => {
    renderMenuPage();

    await waitFor(() => {
      expect(screen.getByText('Burgers')).toBeInTheDocument();
    });

    // Click on Burgers category
    fireEvent.click(screen.getByText('Burgers'));

    await waitFor(() => {
      expect(api.getMenuItems).toHaveBeenCalledWith({
        category_id: 1,
        query: '',
        limit: 100,
      });
    });
  });

  test('searches items by query', async () => {
    renderMenuPage();

    const searchInput = await screen.findByPlaceholderText(/search menu items/i);
    fireEvent.change(searchInput, { target: { value: 'burger' } });

    await waitFor(() => {
      expect(api.getMenuItems).toHaveBeenCalledWith({
        category_id: null,
        query: 'burger',
        limit: 100,
      });
    });
  });

  test('shows loading state', () => {
    renderMenuPage();
    // Initially shows loading
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  test('shows error state when API fails', async () => {
    (api.getCategories as jest.Mock).mockRejectedValue(new Error('API Error'));

    renderMenuPage();

    await waitFor(() => {
      expect(screen.getByText(/error loading menu/i)).toBeInTheDocument();
    });
  });

  test('opens item details modal when view details is clicked', async () => {
    renderMenuPage();

    await waitFor(() => {
      expect(screen.getByText('Test Burger')).toBeInTheDocument();
    });

    const viewDetailsButtons = screen.getAllByText(/view details/i);
    fireEvent.click(viewDetailsButtons[0]);

    await waitFor(() => {
      expect(api.getMenuItem).toHaveBeenCalledWith(1);
    });
  });
});