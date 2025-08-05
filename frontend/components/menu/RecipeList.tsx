// frontend/components/menu/RecipeList.tsx

import React, { useState } from 'react';
import './RecipeList.css';

interface Recipe {
  id: number;
  name: string;
  menu_item_id: number;
  status: 'draft' | 'active' | 'inactive' | 'archived';
  complexity: 'simple' | 'moderate' | 'complex' | 'expert';
  total_cost: number | null;
  food_cost_percentage: number | null;
  version: number;
  created_at: string;
  updated_at: string;
  approved_by: number | null;
  approved_at: string | null;
}

interface MenuItem {
  id: number;
  name: string;
  category: string;
  price?: number;
}

interface RecipeListProps {
  recipes: Recipe[];
  menuItems: MenuItem[];
  searchQuery: string;
  onSearchChange: (query: string) => void;
  filterStatus: string;
  onFilterStatusChange: (status: string) => void;
  filterComplexity: string;
  onFilterComplexityChange: (complexity: string) => void;
  onEdit: (recipe: Recipe) => void;
  onDelete: (recipeId: number) => void;
  onReview: (recipe: Recipe) => void;
  onViewHistory: (recipe: Recipe) => void;
  onApprove: (recipeId: number, notes?: string) => void;
  canEdit: boolean;
  canDelete: boolean;
  canApprove: boolean;
}

const RecipeList: React.FC<RecipeListProps> = ({
  recipes,
  menuItems,
  searchQuery,
  onSearchChange,
  filterStatus,
  onFilterStatusChange,
  filterComplexity,
  onFilterComplexityChange,
  onEdit,
  onDelete,
  onReview,
  onViewHistory,
  onApprove,
  canEdit,
  canDelete,
  canApprove
}) => {
  const [sortBy, setSortBy] = useState<'name' | 'cost' | 'updated'>('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [selectedRecipes, setSelectedRecipes] = useState<Set<number>>(new Set());
  const [showBulkActions, setShowBulkActions] = useState(false);

  // Create menu item lookup map
  const menuItemMap = React.useMemo(() => {
    const map = new Map<number, MenuItem>();
    menuItems.forEach(item => map.set(item.id, item));
    return map;
  }, [menuItems]);

  // Sort recipes
  const sortedRecipes = React.useMemo(() => {
    return [...recipes].sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'cost':
          const aCost = a.total_cost || 0;
          const bCost = b.total_cost || 0;
          comparison = aCost - bCost;
          break;
        case 'updated':
          comparison = new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
          break;
      }
      
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [recipes, sortBy, sortOrder]);

  const handleSort = (field: 'name' | 'cost' | 'updated') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const handleSelectRecipe = (recipeId: number) => {
    const newSelected = new Set(selectedRecipes);
    if (newSelected.has(recipeId)) {
      newSelected.delete(recipeId);
    } else {
      newSelected.add(recipeId);
    }
    setSelectedRecipes(newSelected);
    setShowBulkActions(newSelected.size > 0);
  };

  const handleSelectAll = () => {
    if (selectedRecipes.size === sortedRecipes.length) {
      setSelectedRecipes(new Set());
      setShowBulkActions(false);
    } else {
      setSelectedRecipes(new Set(sortedRecipes.map(r => r.id)));
      setShowBulkActions(true);
    }
  };

  const handleBulkActivate = async () => {
    // Implementation would call the bulk activate API
    console.log('Bulk activate:', Array.from(selectedRecipes));
  };

  const handleBulkDeactivate = async () => {
    // Implementation would call the bulk deactivate API
    console.log('Bulk deactivate:', Array.from(selectedRecipes));
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'active':
        return 'badge-success';
      case 'draft':
        return 'badge-warning';
      case 'inactive':
        return 'badge-secondary';
      case 'archived':
        return 'badge-dark';
      default:
        return 'badge-secondary';
    }
  };

  const getComplexityBadgeClass = (complexity: string) => {
    switch (complexity) {
      case 'simple':
        return 'badge-info';
      case 'moderate':
        return 'badge-primary';
      case 'complex':
        return 'badge-warning';
      case 'expert':
        return 'badge-danger';
      default:
        return 'badge-secondary';
    }
  };

  const formatCurrency = (amount: number | null) => {
    if (amount === null) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <div className="recipe-list">
      <div className="list-controls">
        <div className="search-filter-group">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search recipes..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="form-control"
            />
            <span className="search-icon">🔍</span>
          </div>
          
          <select 
            value={filterStatus} 
            onChange={(e) => onFilterStatusChange(e.target.value)}
            className="form-select"
          >
            <option value="all">All Status</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="archived">Archived</option>
          </select>
          
          <select 
            value={filterComplexity} 
            onChange={(e) => onFilterComplexityChange(e.target.value)}
            className="form-select"
          >
            <option value="all">All Complexity</option>
            <option value="simple">Simple</option>
            <option value="moderate">Moderate</option>
            <option value="complex">Complex</option>
            <option value="expert">Expert</option>
          </select>
        </div>

        {showBulkActions && canEdit && (
          <div className="bulk-actions">
            <span className="selected-count">{selectedRecipes.size} selected</span>
            <button 
              className="btn btn-sm btn-outline-primary"
              onClick={handleBulkActivate}
            >
              Activate
            </button>
            <button 
              className="btn btn-sm btn-outline-secondary"
              onClick={handleBulkDeactivate}
            >
              Deactivate
            </button>
          </div>
        )}
      </div>

      <div className="recipe-table-container">
        <table className="recipe-table">
          <thead>
            <tr>
              <th className="checkbox-column">
                <input
                  type="checkbox"
                  checked={selectedRecipes.size === sortedRecipes.length && sortedRecipes.length > 0}
                  onChange={handleSelectAll}
                />
              </th>
              <th 
                className="sortable"
                onClick={() => handleSort('name')}
              >
                Recipe Name {sortBy === 'name' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th>Menu Item</th>
              <th>Status</th>
              <th>Complexity</th>
              <th 
                className="sortable"
                onClick={() => handleSort('cost')}
              >
                Cost {sortBy === 'cost' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th>Food Cost %</th>
              <th>Version</th>
              <th 
                className="sortable"
                onClick={() => handleSort('updated')}
              >
                Last Updated {sortBy === 'updated' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedRecipes.map(recipe => {
              const menuItem = menuItemMap.get(recipe.menu_item_id);
              const foodCostPercentage = menuItem?.price && recipe.total_cost
                ? ((recipe.total_cost / menuItem.price) * 100).toFixed(1)
                : recipe.food_cost_percentage?.toFixed(1);

              return (
                <tr key={recipe.id}>
                  <td className="checkbox-column">
                    <input
                      type="checkbox"
                      checked={selectedRecipes.has(recipe.id)}
                      onChange={() => handleSelectRecipe(recipe.id)}
                    />
                  </td>
                  <td className="recipe-name">
                    <strong>{recipe.name}</strong>
                    {recipe.approved_at && (
                      <span className="approved-indicator" title={`Approved on ${formatDate(recipe.approved_at)}`}>
                        ✓
                      </span>
                    )}
                  </td>
                  <td>
                    {menuItem ? (
                      <div>
                        <div>{menuItem.name}</div>
                        <small className="text-muted">{menuItem.category}</small>
                      </div>
                    ) : (
                      <span className="text-muted">-</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${getStatusBadgeClass(recipe.status)}`}>
                      {recipe.status}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${getComplexityBadgeClass(recipe.complexity)}`}>
                      {recipe.complexity}
                    </span>
                  </td>
                  <td>{formatCurrency(recipe.total_cost)}</td>
                  <td>
                    {foodCostPercentage ? `${foodCostPercentage}%` : '-'}
                    {foodCostPercentage && parseFloat(foodCostPercentage) > 35 && (
                      <span className="warning-icon" title="Food cost is high">⚠️</span>
                    )}
                  </td>
                  <td>v{recipe.version}</td>
                  <td>{formatDate(recipe.updated_at)}</td>
                  <td className="actions-column">
                    <div className="action-buttons">
                      {canEdit && (
                        <button
                          className="btn-icon"
                          onClick={() => onEdit(recipe)}
                          title="Edit Recipe"
                        >
                          ✏️
                        </button>
                      )}
                      <button
                        className="btn-icon"
                        onClick={() => onReview(recipe)}
                        title="Review Recipe"
                      >
                        👁️
                      </button>
                      <button
                        className="btn-icon"
                        onClick={() => onViewHistory(recipe)}
                        title="View History"
                      >
                        📊
                      </button>
                      {canApprove && recipe.status === 'draft' && (
                        <button
                          className="btn-icon"
                          onClick={() => onApprove(recipe.id)}
                          title="Approve Recipe"
                        >
                          ✅
                        </button>
                      )}
                      {canDelete && (
                        <button
                          className="btn-icon btn-danger"
                          onClick={() => onDelete(recipe.id)}
                          title="Delete Recipe"
                        >
                          🗑️
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {sortedRecipes.length === 0 && (
          <div className="empty-state">
            <p>No recipes found matching your criteria.</p>
            {searchQuery || filterStatus !== 'all' || filterComplexity !== 'all' ? (
              <button 
                className="btn btn-link"
                onClick={() => {
                  onSearchChange('');
                  onFilterStatusChange('all');
                  onFilterComplexityChange('all');
                }}
              >
                Clear filters
              </button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};

export default RecipeList;