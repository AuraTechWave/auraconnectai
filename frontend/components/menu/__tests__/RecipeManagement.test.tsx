// frontend/components/menu/__tests__/RecipeManagement.test.tsx

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import RecipeManagement from '../RecipeManagement';
import { useApiQuery } from '../../../hooks/useApiQuery';
import { useAuth } from '../../../hooks/useAuth';
import { useRBAC } from '../../../hooks/useRBAC';

// Mock the hooks
jest.mock('../../../hooks/useApiQuery');
jest.mock('../../../hooks/useAuth');
jest.mock('../../../hooks/useRBAC');

// Mock child components
jest.mock('../RecipeList', () => ({
  __esModule: true,
  default: ({ recipes, onEdit, onDelete, onReview, onViewHistory, onApprove }: any) => (
    <div data-testid="recipe-list">
      {recipes.map((recipe: any) => (
        <div key={recipe.id} data-testid={`recipe-${recipe.id}`}>
          <span>{recipe.name}</span>
          <button onClick={() => onEdit(recipe)}>Edit</button>
          <button onClick={() => onDelete(recipe.id)}>Delete</button>
          <button onClick={() => onReview(recipe)}>Review</button>
          <button onClick={() => onViewHistory(recipe)}>History</button>
          {recipe.status === 'draft' && (
            <button onClick={() => onApprove(recipe.id)}>Approve</button>
          )}
        </div>
      ))}
    </div>
  )
}));

jest.mock('../RecipeForm', () => ({
  __esModule: true,
  default: ({ recipe, onSave, onCancel }: any) => (
    <div data-testid="recipe-form">
      <h2>{recipe ? 'Edit Recipe' : 'Create Recipe'}</h2>
      <button onClick={() => onSave({ name: 'Test Recipe' })}>Save</button>
      <button onClick={onCancel}>Cancel</button>
    </div>
  )
}));

jest.mock('../RecipeReview', () => ({
  __esModule: true,
  default: ({ recipes, onEdit, onApprove }: any) => (
    <div data-testid="recipe-review">
      <h2>Recipe Review</h2>
      {recipes.map((recipe: any) => (
        <div key={recipe.id}>
          <span>{recipe.name}</span>
          <button onClick={() => onEdit(recipe)}>Edit</button>
          <button onClick={() => onApprove(recipe.id)}>Approve</button>
        </div>
      ))}
    </div>
  )
}));

jest.mock('../RecipeHistory', () => ({
  __esModule: true,
  default: ({ recipeId, recipeName, onClose }: any) => (
    <div data-testid="recipe-history">
      <h2>History for {recipeName}</h2>
      <button onClick={onClose}>Close</button>
    </div>
  )
}));

const mockRecipes = [
  {
    id: 1,
    name: 'Margherita Pizza',
    menu_item_id: 101,
    status: 'active',
    complexity: 'simple',
    total_cost: 5.50,
    food_cost_percentage: 25,
    version: 1,
    ingredients: [],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    approved_by: null,
    approved_at: null
  },
  {
    id: 2,
    name: 'Caesar Salad',
    menu_item_id: 102,
    status: 'draft',
    complexity: 'simple',
    total_cost: 3.20,
    food_cost_percentage: 30,
    version: 1,
    ingredients: [],
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
    approved_by: null,
    approved_at: null
  }
];

const mockMenuItems = [
  { id: 101, name: 'Margherita Pizza', category: 'Pizza' },
  { id: 102, name: 'Caesar Salad', category: 'Salads' }
];

const mockComplianceData = {
  total_menu_items: 10,
  items_with_recipes: 8,
  items_without_recipes: 2,
  compliance_percentage: 80,
  missing_recipes: [
    {
      menu_item_id: 103,
      menu_item_name: 'Garlic Bread',
      category: 'Appetizers',
      has_recipe: false,
      recipe_status: null,
      recipe_id: null
    }
  ]
};

describe('RecipeManagement', () => {
  const mockToken = 'test-token';
  const mockFetch = jest.fn();

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockClear();

    (useAuth as jest.Mock).mockReturnValue({ token: mockToken });
    (useRBAC as jest.Mock).mockReturnValue({
      hasPermission: (permission: string) => true
    });
    (useApiQuery as jest.Mock).mockImplementation((endpoint: string) => {
      if (endpoint === '/api/v1/menu/recipes') {
        return {
          data: { recipes: mockRecipes },
          loading: false,
          error: null,
          refetch: jest.fn()
        };
      }
      if (endpoint === '/api/v1/menu/items') {
        return {
          data: { items: mockMenuItems },
          loading: false,
          error: null,
          refetch: jest.fn()
        };
      }
      if (endpoint === '/api/v1/menu/recipes/compliance/report') {
        return {
          data: mockComplianceData,
          loading: false,
          error: null,
          refetch: jest.fn()
        };
      }
      return { data: null, loading: false, error: null, refetch: jest.fn() };
    });
  });

  test('renders recipe management with all tabs', () => {
    render(<RecipeManagement />);
    
    expect(screen.getByText('Recipe Management')).toBeInTheDocument();
    expect(screen.getByText('Recipe List')).toBeInTheDocument();
    expect(screen.getByText('Configure Recipe')).toBeInTheDocument();
    expect(screen.getByText('Review & Accuracy')).toBeInTheDocument();
    expect(screen.getByText('Version History')).toBeInTheDocument();
  });

  test('displays compliance alert when recipes are missing', () => {
    render(<RecipeManagement />);
    
    expect(screen.getByText(/2 menu items don't have recipes/)).toBeInTheDocument();
  });

  test('switches to configure tab when creating new recipe', () => {
    render(<RecipeManagement />);
    
    const createButton = screen.getByText('Create New Recipe');
    fireEvent.click(createButton);
    
    expect(screen.getByTestId('recipe-form')).toBeInTheDocument();
    expect(screen.getByText('Create Recipe')).toBeInTheDocument();
  });

  test('handles recipe edit', () => {
    render(<RecipeManagement />);
    
    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);
    
    expect(screen.getByTestId('recipe-form')).toBeInTheDocument();
    expect(screen.getByText('Edit Recipe')).toBeInTheDocument();
  });

  test('handles recipe save', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 3, name: 'New Recipe' })
    });

    render(<RecipeManagement />);
    
    const createButton = screen.getByText('Create New Recipe');
    fireEvent.click(createButton);
    
    const saveButton = screen.getByText('Save');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/menu/recipes/',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockToken}`
          }
        })
      );
    });
  });

  test('handles recipe delete with confirmation', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    mockFetch.mockResolvedValueOnce({ ok: true });

    render(<RecipeManagement />);
    
    const deleteButtons = screen.getAllByText('Delete');
    fireEvent.click(deleteButtons[0]);
    
    expect(confirmSpy).toHaveBeenCalledWith('Are you sure you want to delete this recipe?');
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/menu/recipes/1',
        expect.objectContaining({
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${mockToken}`
          }
        })
      );
    });

    confirmSpy.mockRestore();
  });

  test('handles recipe approval', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Recipe approved successfully' })
    });

    render(<RecipeManagement />);
    
    const approveButtons = screen.getAllByText('Approve');
    fireEvent.click(approveButtons[0]);
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/menu/recipes/2/approve',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockToken}`
          }
        })
      );
    });
  });

  test('handles cost recalculation', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ updated: 5 })
    });

    render(<RecipeManagement />);
    
    const recalculateButton = screen.getByText('Recalculate All Costs');
    fireEvent.click(recalculateButton);
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/menu/recipes/recalculate-costs',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${mockToken}`
          }
        })
      );
    });
  });

  test('switches to review tab', () => {
    render(<RecipeManagement />);
    
    const reviewTab = screen.getByText('Review & Accuracy');
    fireEvent.click(reviewTab);
    
    expect(screen.getByTestId('recipe-review')).toBeInTheDocument();
  });

  test('switches to history tab for a recipe', () => {
    render(<RecipeManagement />);
    
    const historyButtons = screen.getAllByText('History');
    fireEvent.click(historyButtons[0]);
    
    expect(screen.getByTestId('recipe-history')).toBeInTheDocument();
    expect(screen.getByText('History for Margherita Pizza')).toBeInTheDocument();
  });

  test('handles permission restrictions', () => {
    (useRBAC as jest.Mock).mockReturnValue({
      hasPermission: (permission: string) => permission === 'menu:read'
    });

    render(<RecipeManagement />);
    
    expect(screen.queryByText('Create New Recipe')).not.toBeInTheDocument();
    expect(screen.queryByText('Recalculate All Costs')).not.toBeInTheDocument();
  });

  test('displays access denied when no read permission', () => {
    (useRBAC as jest.Mock).mockReturnValue({
      hasPermission: (permission: string) => false
    });

    render(<RecipeManagement />);
    
    expect(screen.getByText('You do not have permission to view recipes')).toBeInTheDocument();
  });
});