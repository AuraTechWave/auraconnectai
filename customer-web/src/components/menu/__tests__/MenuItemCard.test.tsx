import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MenuItemCard } from '../MenuItemCard';
import { MenuItem } from '../../../types';
import { useCartStore } from '../../../store/cartStore';

// Mock the cart store
jest.mock('../../../store/cartStore');

// Mock react-toastify
jest.mock('react-toastify', () => ({
  toast: {
    success: jest.fn(),
  },
}));

const mockMenuItem: MenuItem = {
  id: 1,
  category_id: 1,
  name: 'Test Burger',
  description: 'A delicious test burger',
  price: 12.99,
  image_url: 'https://example.com/burger.jpg',
  is_active: true,
  is_available: true,
  display_order: 1,
  dietary_tags: ['Gluten-Free'],
};

const mockAddItem = jest.fn();
const mockGetItem = jest.fn();
const mockUpdateItemQuantity = jest.fn();
const mockOnViewDetails = jest.fn();

describe('MenuItemCard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetItem.mockReturnValue(null);
    (useCartStore as unknown as jest.Mock).mockReturnValue({
      addItem: mockAddItem,
      getItem: mockGetItem,
      updateItemQuantity: mockUpdateItemQuantity,
    });
  });

  test('renders menu item information', () => {
    render(<MenuItemCard item={mockMenuItem} onViewDetails={mockOnViewDetails} />);

    expect(screen.getByText('Test Burger')).toBeInTheDocument();
    expect(screen.getByText('A delicious test burger')).toBeInTheDocument();
    expect(screen.getByText('$12.99')).toBeInTheDocument();
  });

  test('renders dietary tags', () => {
    render(<MenuItemCard item={mockMenuItem} onViewDetails={mockOnViewDetails} />);

    expect(screen.getByText('Gluten-Free')).toBeInTheDocument();
  });

  test('shows unavailable state', () => {
    const unavailableItem = { ...mockMenuItem, is_available: false };
    render(<MenuItemCard item={unavailableItem} onViewDetails={mockOnViewDetails} />);

    expect(screen.getByText('Unavailable')).toBeInTheDocument();
  });

  test('calls onViewDetails when view details is clicked', () => {
    render(<MenuItemCard item={mockMenuItem} onViewDetails={mockOnViewDetails} />);

    const viewDetailsButton = screen.getByText('View Details');
    fireEvent.click(viewDetailsButton);

    expect(mockOnViewDetails).toHaveBeenCalledWith(mockMenuItem);
  });

  test('adds item to cart when add to cart is clicked', () => {
    render(<MenuItemCard item={mockMenuItem} onViewDetails={mockOnViewDetails} />);

    const addToCartButton = screen.getByLabelText('add to cart');
    fireEvent.click(addToCartButton);

    expect(mockAddItem).toHaveBeenCalledWith(mockMenuItem, 1, [], '');
  });

  test('disables add to cart when item is unavailable', () => {
    const unavailableItem = { ...mockMenuItem, is_available: false };
    render(<MenuItemCard item={unavailableItem} onViewDetails={mockOnViewDetails} />);

    const addToCartButton = screen.getByLabelText('add to cart');
    expect(addToCartButton).toBeDisabled();
  });

  test('renders with placeholder image when no image provided', () => {
    const itemWithoutImage = { ...mockMenuItem, image_url: undefined };
    render(<MenuItemCard item={itemWithoutImage} onViewDetails={mockOnViewDetails} />);

    const image = screen.getByAltText('Test Burger') as HTMLImageElement;
    expect(image.src).toContain('placeholder');
  });

  test('truncates long descriptions', () => {
    const longDescription = 'A'.repeat(200);
    const itemWithLongDesc = { ...mockMenuItem, description: longDescription };
    render(<MenuItemCard item={itemWithLongDesc} onViewDetails={mockOnViewDetails} />);

    const description = screen.getByText(/A+\.\.\.$/);
    expect(description.textContent?.length).toBeLessThan(200);
  });
});