// frontend/components/menu/RecipeManagement.tsx

import React, { useState, useEffect, useCallback } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { useAuth } from '../../hooks/useAuth';
import { useRBAC } from '../../hooks/useRBAC';
import RecipeList from './RecipeList';
import RecipeForm from './RecipeForm';
import RecipeReview from './RecipeReview';
import RecipeHistory from './RecipeHistory';
import Toast from '../ui/Toast';
import SkeletonLoader from '../ui/SkeletonLoader';
import './RecipeManagement.css';

interface Recipe {
  id: number;
  name: string;
  menu_item_id: number;
  status: 'draft' | 'active' | 'inactive' | 'archived';
  complexity: 'simple' | 'moderate' | 'complex' | 'expert';
  total_cost: number | null;
  food_cost_percentage: number | null;
  version: number;
  ingredients: RecipeIngredient[];
  created_at: string;
  updated_at: string;
  approved_by: number | null;
  approved_at: string | null;
}

interface RecipeIngredient {
  id: number;
  inventory_id: number;
  quantity: number;
  unit: string;
  custom_unit: string | null;
  preparation: string | null;
  is_optional: boolean;
  notes: string | null;
  display_order: number;
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
}

const RecipeManagement: React.FC = () => {
  const { hasPermission } = useRBAC();
  const { token } = useAuth();
  const { data: recipesData, loading: loadingRecipes, error: recipesError, refetch: refetchRecipes } = useApiQuery('/api/v1/menu/recipes');
  const { data: menuItemsData, loading: loadingMenuItems } = useApiQuery('/api/v1/menu/items');
  const { data: complianceData, loading: loadingCompliance, refetch: refetchCompliance } = useApiQuery('/api/v1/menu/recipes/compliance/report');

  const [activeTab, setActiveTab] = useState<'list' | 'configure' | 'review' | 'history'>('list');
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
  const [selectedMenuItem, setSelectedMenuItem] = useState<number | null>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastType, setToastType] = useState<'success' | 'error'>('success');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterComplexity, setFilterComplexity] = useState<string>('all');

  // Check permissions
  const canView = hasPermission('menu:read');
  const canCreate = hasPermission('menu:create');
  const canUpdate = hasPermission('menu:update');
  const canDelete = hasPermission('menu:delete');
  const canApprove = hasPermission('manager:recipes') || hasPermission('admin:recipes');

  useEffect(() => {
    if (!canView) {
      setToastMessage('You do not have permission to view recipes');
      setToastType('error');
      setShowToast(true);
    }
  }, [canView]);

  const handleCreateRecipe = useCallback(() => {
    setSelectedRecipe(null);
    setActiveTab('configure');
  }, []);

  const handleEditRecipe = useCallback((recipe: Recipe) => {
    setSelectedRecipe(recipe);
    setActiveTab('configure');
  }, []);

  const handleReviewRecipe = useCallback((recipe: Recipe) => {
    setSelectedRecipe(recipe);
    setActiveTab('review');
  }, []);

  const handleViewHistory = useCallback((recipe: Recipe) => {
    setSelectedRecipe(recipe);
    setActiveTab('history');
  }, []);

  const handleSaveRecipe = useCallback(async (recipeData: any) => {
    try {
      const url = selectedRecipe 
        ? `/api/v1/menu/recipes/${selectedRecipe.id}`
        : '/api/v1/menu/recipes/';
      
      const method = selectedRecipe ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(recipeData)
      });

      if (!response.ok) {
        throw new Error('Failed to save recipe');
      }

      setToastMessage(selectedRecipe ? 'Recipe updated successfully' : 'Recipe created successfully');
      setToastType('success');
      setShowToast(true);
      
      refetchRecipes();
      refetchCompliance();
      setActiveTab('list');
      setSelectedRecipe(null);
    } catch (error) {
      setToastMessage('Failed to save recipe');
      setToastType('error');
      setShowToast(true);
    }
  }, [selectedRecipe, token, refetchRecipes, refetchCompliance]);

  const handleDeleteRecipe = useCallback(async (recipeId: number) => {
    if (!window.confirm('Are you sure you want to delete this recipe?')) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/menu/recipes/${recipeId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to delete recipe');
      }

      setToastMessage('Recipe deleted successfully');
      setToastType('success');
      setShowToast(true);
      
      refetchRecipes();
      refetchCompliance();
    } catch (error) {
      setToastMessage('Failed to delete recipe');
      setToastType('error');
      setShowToast(true);
    }
  }, [token, refetchRecipes, refetchCompliance]);

  const handleApproveRecipe = useCallback(async (recipeId: number, notes?: string) => {
    try {
      const response = await fetch(`/api/v1/menu/recipes/${recipeId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ notes })
      });

      if (!response.ok) {
        throw new Error('Failed to approve recipe');
      }

      setToastMessage('Recipe approved successfully');
      setToastType('success');
      setShowToast(true);
      
      refetchRecipes();
    } catch (error) {
      setToastMessage('Failed to approve recipe');
      setToastType('error');
      setShowToast(true);
    }
  }, [token, refetchRecipes]);

  const handleRecalculateCosts = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/menu/recipes/recalculate-costs', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to recalculate costs');
      }

      const result = await response.json();
      setToastMessage(`Costs recalculated for ${result.updated} recipes`);
      setToastType('success');
      setShowToast(true);
      
      refetchRecipes();
    } catch (error) {
      setToastMessage('Failed to recalculate costs');
      setToastType('error');
      setShowToast(true);
    }
  }, [token, refetchRecipes]);

  // Filter recipes based on search and filters
  const filteredRecipes = React.useMemo(() => {
    if (!recipesData?.recipes) return [];
    
    return recipesData.recipes.filter((recipe: Recipe) => {
      const matchesSearch = !searchQuery || 
        recipe.name.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesStatus = filterStatus === 'all' || recipe.status === filterStatus;
      const matchesComplexity = filterComplexity === 'all' || recipe.complexity === filterComplexity;
      
      return matchesSearch && matchesStatus && matchesComplexity;
    });
  }, [recipesData, searchQuery, filterStatus, filterComplexity]);

  if (loadingRecipes || loadingMenuItems || loadingCompliance) {
    return <SkeletonLoader />;
  }

  if (!canView) {
    return <div className="access-denied">You do not have permission to view recipes</div>;
  }

  return (
    <div className="recipe-management">
      <div className="recipe-management-header">
        <h1>Recipe Management</h1>
        <div className="header-actions">
          {canCreate && (
            <button 
              className="btn btn-primary"
              onClick={handleCreateRecipe}
            >
              Create New Recipe
            </button>
          )}
          {canApprove && (
            <button 
              className="btn btn-secondary"
              onClick={handleRecalculateCosts}
            >
              Recalculate All Costs
            </button>
          )}
        </div>
      </div>

      {complianceData && complianceData.missing_recipes?.length > 0 && (
        <div className="compliance-alert">
          <div className="alert-icon">⚠️</div>
          <div className="alert-content">
            <strong>Missing Recipes:</strong> {complianceData.missing_recipes.length} menu items don't have recipes.
            <button 
              className="btn-link"
              onClick={() => setActiveTab('review')}
            >
              Review Missing Recipes
            </button>
          </div>
        </div>
      )}

      <div className="recipe-tabs">
        <button 
          className={`tab ${activeTab === 'list' ? 'active' : ''}`}
          onClick={() => setActiveTab('list')}
        >
          Recipe List
        </button>
        <button 
          className={`tab ${activeTab === 'configure' ? 'active' : ''}`}
          onClick={() => setActiveTab('configure')}
        >
          Configure Recipe
        </button>
        <button 
          className={`tab ${activeTab === 'review' ? 'active' : ''}`}
          onClick={() => setActiveTab('review')}
        >
          Review & Accuracy
        </button>
        <button 
          className={`tab ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          Version History
        </button>
      </div>

      <div className="recipe-content">
        {activeTab === 'list' && (
          <RecipeList
            recipes={filteredRecipes}
            menuItems={menuItemsData?.items || []}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            filterStatus={filterStatus}
            onFilterStatusChange={setFilterStatus}
            filterComplexity={filterComplexity}
            onFilterComplexityChange={setFilterComplexity}
            onEdit={handleEditRecipe}
            onDelete={handleDeleteRecipe}
            onReview={handleReviewRecipe}
            onViewHistory={handleViewHistory}
            onApprove={handleApproveRecipe}
            canEdit={canUpdate}
            canDelete={canDelete}
            canApprove={canApprove}
          />
        )}

        {activeTab === 'configure' && (
          <RecipeForm
            recipe={selectedRecipe}
            menuItems={menuItemsData?.items || []}
            onSave={handleSaveRecipe}
            onCancel={() => {
              setActiveTab('list');
              setSelectedRecipe(null);
            }}
          />
        )}

        {activeTab === 'review' && (
          <RecipeReview
            recipes={recipesData?.recipes || []}
            menuItems={menuItemsData?.items || []}
            complianceReport={complianceData}
            onEdit={handleEditRecipe}
            onApprove={handleApproveRecipe}
            canEdit={canUpdate}
            canApprove={canApprove}
          />
        )}

        {activeTab === 'history' && selectedRecipe && (
          <RecipeHistory
            recipeId={selectedRecipe.id}
            recipeName={selectedRecipe.name}
            onClose={() => {
              setActiveTab('list');
              setSelectedRecipe(null);
            }}
          />
        )}
      </div>

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

export default RecipeManagement;