// frontend/components/menu/RecipeReview.tsx

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useApiQuery } from '../../hooks/useApiQuery';
import SkeletonLoader from '../ui/SkeletonLoader';
import Toast from '../ui/Toast';
import './RecipeReview.css';

interface Recipe {
  id: number;
  name: string;
  menu_item_id: number;
  status: string;
  complexity: string;
  total_cost: number | null;
  food_cost_percentage: number | null;
  version: number;
  ingredients: RecipeIngredient[];
  created_at: string;
  updated_at: string;
  approved_by: number | null;
  approved_at: string | null;
  instructions: string[] | null;
  allergen_notes: string | null;
  prep_time_minutes: number | null;
  cook_time_minutes: number | null;
  total_time_minutes: number | null;
}

interface RecipeIngredient {
  id: number;
  inventory_id: number;
  quantity: number;
  unit: string;
  preparation: string | null;
  is_optional: boolean;
  inventory_item?: {
    id: number;
    item_name: string;
    unit: string;
    cost_per_unit: number;
  };
}

interface MenuItem {
  id: number;
  name: string;
  category: string;
  price?: number;
}

interface ComplianceReport {
  total_menu_items: number;
  items_with_recipes: number;
  items_without_recipes: number;
  compliance_percentage: number;
  missing_recipes: MenuItemRecipeStatus[];
  draft_recipes: MenuItemRecipeStatus[];
  last_updated: string;
}

interface MenuItemRecipeStatus {
  menu_item_id: number;
  menu_item_name: string;
  category: string;
  has_recipe: boolean;
  recipe_status: string | null;
  recipe_id: number | null;
}

interface RecipeValidation {
  recipe_id: number;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

interface RecipeReviewProps {
  recipes: Recipe[];
  menuItems: MenuItem[];
  complianceReport: ComplianceReport | null;
  onEdit: (recipe: Recipe) => void;
  onApprove: (recipeId: number, notes?: string) => void;
  canEdit: boolean;
  canApprove: boolean;
}

const RecipeReview: React.FC<RecipeReviewProps> = ({
  recipes,
  menuItems,
  complianceReport,
  onEdit,
  onApprove,
  canEdit,
  canApprove
}) => {
  const { token } = useAuth();
  const [selectedRecipeId, setSelectedRecipeId] = useState<number | null>(null);
  const [validationResults, setValidationResults] = useState<Map<number, RecipeValidation>>(new Map());
  const [costAnalysis, setCostAnalysis] = useState<Map<number, any>>(new Map());
  const [loadingValidation, setLoadingValidation] = useState<Set<number>>(new Set());
  const [approvalNotes, setApprovalNotes] = useState<string>('');
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [selectedApprovalId, setSelectedApprovalId] = useState<number | null>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastType, setToastType] = useState<'success' | 'error'>('success');
  const [filterCategory, setFilterCategory] = useState<string>('all');

  // Create menu item lookup map
  const menuItemMap = React.useMemo(() => {
    const map = new Map<number, MenuItem>();
    menuItems.forEach(item => map.set(item.id, item));
    return map;
  }, [menuItems]);

  // Get unique categories
  const categories = React.useMemo(() => {
    const cats = new Set<string>();
    menuItems.forEach(item => cats.add(item.category));
    return Array.from(cats).sort();
  }, [menuItems]);

  // Filter missing recipes by category
  const filteredMissingRecipes = React.useMemo(() => {
    if (!complianceReport) return [];
    
    return complianceReport.missing_recipes.filter(item => 
      filterCategory === 'all' || item.category === filterCategory
    );
  }, [complianceReport, filterCategory]);

  const validateRecipe = async (recipeId: number) => {
    setLoadingValidation(prev => new Set(prev).add(recipeId));
    
    try {
      const response = await fetch(`/api/v1/menu/recipes/${recipeId}/validate`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to validate recipe');
      
      const validation = await response.json();
      setValidationResults(prev => new Map(prev).set(recipeId, validation));

      // Also fetch cost analysis
      const costResponse = await fetch(`/api/v1/menu/recipes/${recipeId}/cost-analysis`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (costResponse.ok) {
        const cost = await costResponse.json();
        setCostAnalysis(prev => new Map(prev).set(recipeId, cost));
      }
    } catch (error) {
      console.error('Error validating recipe:', error);
    } finally {
      setLoadingValidation(prev => {
        const newSet = new Set(prev);
        newSet.delete(recipeId);
        return newSet;
      });
    }
  };

  const handleApprove = (recipeId: number) => {
    setSelectedApprovalId(recipeId);
    setShowApprovalDialog(true);
  };

  const confirmApproval = () => {
    if (selectedApprovalId) {
      onApprove(selectedApprovalId, approvalNotes);
      setShowApprovalDialog(false);
      setApprovalNotes('');
      setSelectedApprovalId(null);
    }
  };

  const createRecipeForMenuItem = (menuItemId: number) => {
    const menuItem = menuItemMap.get(menuItemId);
    if (menuItem) {
      // Create a new recipe with menu item pre-selected
      const newRecipe: Partial<Recipe> = {
        menu_item_id: menuItemId,
        name: `${menuItem.name} Recipe`,
        status: 'draft',
        complexity: 'simple',
        ingredients: []
      };
      onEdit(newRecipe as Recipe);
    }
  };

  const getIssueIcon = (type: 'error' | 'warning' | 'suggestion') => {
    switch (type) {
      case 'error': return '❌';
      case 'warning': return '⚠️';
      case 'suggestion': return '💡';
    }
  };

  const formatCurrency = (amount: number | null) => {
    if (amount === null) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  return (
    <div className="recipe-review">
      <div className="review-header">
        <h2>Recipe Review & Accuracy</h2>
        <div className="compliance-summary">
          {complianceReport && (
            <>
              <div className="compliance-stat">
                <span className="stat-value">{complianceReport.total_menu_items}</span>
                <span className="stat-label">Total Menu Items</span>
              </div>
              <div className="compliance-stat">
                <span className="stat-value">{complianceReport.items_with_recipes}</span>
                <span className="stat-label">With Recipes</span>
              </div>
              <div className="compliance-stat">
                <span className="stat-value error">{complianceReport.items_without_recipes}</span>
                <span className="stat-label">Missing Recipes</span>
              </div>
              <div className="compliance-stat">
                <span className={`stat-value ${complianceReport.compliance_percentage >= 90 ? 'success' : 'warning'}`}>
                  {complianceReport.compliance_percentage.toFixed(1)}%
                </span>
                <span className="stat-label">Compliance</span>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="review-tabs">
        <button 
          className={`tab ${selectedRecipeId === null ? 'active' : ''}`}
          onClick={() => setSelectedRecipeId(null)}
        >
          Missing Recipes ({filteredMissingRecipes.length})
        </button>
        <button 
          className={`tab ${selectedRecipeId === -1 ? 'active' : ''}`}
          onClick={() => setSelectedRecipeId(-1)}
        >
          Draft Recipes ({complianceReport?.draft_recipes.length || 0})
        </button>
        <button 
          className={`tab ${selectedRecipeId === -2 ? 'active' : ''}`}
          onClick={() => setSelectedRecipeId(-2)}
        >
          All Recipes ({recipes.length})
        </button>
      </div>

      <div className="review-content">
        {selectedRecipeId === null && (
          <div className="missing-recipes-section">
            <div className="section-header">
              <h3>Menu Items Without Recipes</h3>
              <select 
                value={filterCategory} 
                onChange={(e) => setFilterCategory(e.target.value)}
                className="category-filter"
              >
                <option value="all">All Categories</option>
                {categories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>

            {filteredMissingRecipes.length === 0 ? (
              <div className="empty-state">
                <p>🎉 All menu items in this category have recipes!</p>
              </div>
            ) : (
              <div className="missing-items-grid">
                {filteredMissingRecipes.map(item => (
                  <div key={item.menu_item_id} className="missing-item-card">
                    <h4>{item.menu_item_name}</h4>
                    <span className="item-category">{item.category}</span>
                    {canEdit && (
                      <button 
                        className="btn btn-primary btn-sm"
                        onClick={() => createRecipeForMenuItem(item.menu_item_id)}
                      >
                        Create Recipe
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {selectedRecipeId === -1 && (
          <div className="draft-recipes-section">
            <h3>Draft Recipes Requiring Review</h3>
            <div className="recipes-list">
              {recipes.filter(r => r.status === 'draft').map(recipe => {
                const validation = validationResults.get(recipe.id);
                const cost = costAnalysis.get(recipe.id);
                const menuItem = menuItemMap.get(recipe.menu_item_id);
                const isLoading = loadingValidation.has(recipe.id);

                return (
                  <div key={recipe.id} className="recipe-review-card">
                    <div className="recipe-header">
                      <div>
                        <h4>{recipe.name}</h4>
                        <span className="menu-item-name">
                          {menuItem?.name} - {menuItem?.category}
                        </span>
                      </div>
                      <div className="recipe-actions">
                        {!validation && !isLoading && (
                          <button 
                            className="btn btn-sm btn-outline"
                            onClick={() => validateRecipe(recipe.id)}
                          >
                            Validate
                          </button>
                        )}
                        {canEdit && (
                          <button 
                            className="btn btn-sm btn-primary"
                            onClick={() => onEdit(recipe)}
                          >
                            Edit
                          </button>
                        )}
                        {canApprove && validation?.is_valid && (
                          <button 
                            className="btn btn-sm btn-success"
                            onClick={() => handleApprove(recipe.id)}
                          >
                            Approve
                          </button>
                        )}
                      </div>
                    </div>

                    {isLoading && <SkeletonLoader />}

                    {validation && (
                      <div className="validation-results">
                        <div className={`validation-status ${validation.is_valid ? 'valid' : 'invalid'}`}>
                          {validation.is_valid ? '✅ Recipe is valid' : '❌ Recipe has issues'}
                        </div>

                        {validation.errors.length > 0 && (
                          <div className="issues-section">
                            <h5>Errors</h5>
                            {validation.errors.map((error, index) => (
                              <div key={index} className="issue-item error">
                                {getIssueIcon('error')} {error}
                              </div>
                            ))}
                          </div>
                        )}

                        {validation.warnings.length > 0 && (
                          <div className="issues-section">
                            <h5>Warnings</h5>
                            {validation.warnings.map((warning, index) => (
                              <div key={index} className="issue-item warning">
                                {getIssueIcon('warning')} {warning}
                              </div>
                            ))}
                          </div>
                        )}

                        {validation.suggestions.length > 0 && (
                          <div className="issues-section">
                            <h5>Suggestions</h5>
                            {validation.suggestions.map((suggestion, index) => (
                              <div key={index} className="issue-item suggestion">
                                {getIssueIcon('suggestion')} {suggestion}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {cost && (
                      <div className="cost-analysis">
                        <h5>Cost Analysis</h5>
                        <div className="cost-details">
                          <div className="cost-item">
                            <span>Total Cost:</span>
                            <span className="cost-value">{formatCurrency(cost.total_cost)}</span>
                          </div>
                          <div className="cost-item">
                            <span>Cost per Portion:</span>
                            <span className="cost-value">{formatCurrency(cost.cost_per_portion)}</span>
                          </div>
                          {menuItem?.price && (
                            <div className="cost-item">
                              <span>Food Cost %:</span>
                              <span className={`cost-value ${cost.food_cost_percentage > 35 ? 'high' : ''}`}>
                                {cost.food_cost_percentage.toFixed(1)}%
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="recipe-details">
                      <div className="detail-item">
                        <span className="label">Complexity:</span>
                        <span className="value">{recipe.complexity}</span>
                      </div>
                      <div className="detail-item">
                        <span className="label">Prep Time:</span>
                        <span className="value">{recipe.prep_time_minutes || '-'} min</span>
                      </div>
                      <div className="detail-item">
                        <span className="label">Cook Time:</span>
                        <span className="value">{recipe.cook_time_minutes || '-'} min</span>
                      </div>
                      <div className="detail-item">
                        <span className="label">Ingredients:</span>
                        <span className="value">{recipe.ingredients.length}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {selectedRecipeId === -2 && (
          <div className="all-recipes-section">
            <h3>All Recipes Review</h3>
            <div className="recipes-grid">
              {recipes.map(recipe => {
                const menuItem = menuItemMap.get(recipe.menu_item_id);
                const validation = validationResults.get(recipe.id);
                
                return (
                  <div key={recipe.id} className="recipe-summary-card">
                    <div className="recipe-status-indicator">
                      <span className={`status-badge ${recipe.status}`}>
                        {recipe.status}
                      </span>
                      {recipe.approved_at && <span className="approved-check">✓</span>}
                    </div>
                    
                    <h4>{recipe.name}</h4>
                    <p className="menu-item-ref">{menuItem?.name}</p>
                    
                    <div className="recipe-metrics">
                      <div className="metric">
                        <span className="metric-value">{formatCurrency(recipe.total_cost)}</span>
                        <span className="metric-label">Cost</span>
                      </div>
                      <div className="metric">
                        <span className="metric-value">{recipe.food_cost_percentage?.toFixed(1) || '-'}%</span>
                        <span className="metric-label">Food Cost</span>
                      </div>
                      <div className="metric">
                        <span className="metric-value">v{recipe.version}</span>
                        <span className="metric-label">Version</span>
                      </div>
                    </div>

                    <div className="card-actions">
                      {!validation && (
                        <button 
                          className="btn-icon"
                          onClick={() => validateRecipe(recipe.id)}
                          title="Validate Recipe"
                        >
                          🔍
                        </button>
                      )}
                      {validation && (
                        <span 
                          className={`validation-indicator ${validation.is_valid ? 'valid' : 'invalid'}`}
                          title={validation.is_valid ? 'Valid' : `${validation.errors.length} errors`}
                        >
                          {validation.is_valid ? '✅' : '❌'}
                        </span>
                      )}
                      {canEdit && (
                        <button 
                          className="btn-icon"
                          onClick={() => onEdit(recipe)}
                          title="Edit Recipe"
                        >
                          ✏️
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Approval Dialog */}
      {showApprovalDialog && (
        <div className="modal-overlay" onClick={() => setShowApprovalDialog(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Approve Recipe</h3>
            <p>Are you sure you want to approve this recipe?</p>
            <div className="form-group">
              <label>Approval Notes (Optional)</label>
              <textarea
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                rows={3}
                placeholder="Add any notes about this approval..."
              />
            </div>
            <div className="modal-actions">
              <button 
                className="btn btn-secondary"
                onClick={() => setShowApprovalDialog(false)}
              >
                Cancel
              </button>
              <button 
                className="btn btn-primary"
                onClick={confirmApproval}
              >
                Approve Recipe
              </button>
            </div>
          </div>
        </div>
      )}

      {showToast && (
        <Toast
          message={toastMessage}
          type={toastType}
          onClose={() => setShowToast(false)}
        />
      )}
    </div>
  );
};

export default RecipeReview;