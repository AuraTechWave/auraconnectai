// frontend/components/menu/RecipeForm.tsx

import React, { useState, useEffect } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { useAuth } from '../../hooks/useAuth';
import SkeletonLoader from '../ui/SkeletonLoader';
import './RecipeForm.css';

interface Recipe {
  id: number;
  name: string;
  menu_item_id: number;
  status: 'draft' | 'active' | 'inactive' | 'archived';
  complexity: 'simple' | 'moderate' | 'complex' | 'expert';
  yield_quantity: number;
  yield_unit: string | null;
  portion_size: number | null;
  portion_unit: string | null;
  prep_time_minutes: number | null;
  cook_time_minutes: number | null;
  total_time_minutes: number | null;
  instructions: string[] | null;
  notes: string | null;
  allergen_notes: string | null;
  quality_standards: any | null;
  plating_instructions: string | null;
  image_urls: string[] | null;
  ingredients: RecipeIngredient[];
}

interface RecipeIngredient {
  id?: number;
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
  price?: number;
}

interface InventoryItem {
  id: number;
  item_name: string;
  unit: string;
  cost_per_unit: number;
  category: string;
  vendor_id: number;
}

interface RecipeFormProps {
  recipe: Recipe | null;
  menuItems: MenuItem[];
  onSave: (recipeData: any) => void;
  onCancel: () => void;
}

const UNIT_OPTIONS = [
  { value: 'g', label: 'Grams (g)' },
  { value: 'kg', label: 'Kilograms (kg)' },
  { value: 'oz', label: 'Ounces (oz)' },
  { value: 'lb', label: 'Pounds (lb)' },
  { value: 'ml', label: 'Milliliters (ml)' },
  { value: 'l', label: 'Liters (l)' },
  { value: 'tsp', label: 'Teaspoons (tsp)' },
  { value: 'tbsp', label: 'Tablespoons (tbsp)' },
  { value: 'cup', label: 'Cups' },
  { value: 'fl_oz', label: 'Fluid Ounces (fl oz)' },
  { value: 'pt', label: 'Pints (pt)' },
  { value: 'qt', label: 'Quarts (qt)' },
  { value: 'gal', label: 'Gallons (gal)' },
  { value: 'piece', label: 'Pieces' },
  { value: 'dozen', label: 'Dozen' },
  { value: 'custom', label: 'Custom Unit' }
];

const RecipeForm: React.FC<RecipeFormProps> = ({
  recipe,
  menuItems,
  onSave,
  onCancel
}) => {
  const { token } = useAuth();
  const { data: inventoryData, loading: loadingInventory } = useApiQuery('/api/v1/inventory');
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    menu_item_id: 0,
    status: 'draft' as const,
    complexity: 'simple' as const,
    yield_quantity: 1,
    yield_unit: '',
    portion_size: null as number | null,
    portion_unit: '',
    prep_time_minutes: null as number | null,
    cook_time_minutes: null as number | null,
    total_time_minutes: null as number | null,
    instructions: [''],
    notes: '',
    allergen_notes: '',
    plating_instructions: '',
    image_urls: ['']
  });

  const [ingredients, setIngredients] = useState<RecipeIngredient[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showValidation, setShowValidation] = useState(false);
  const [estimatedCost, setEstimatedCost] = useState<number | null>(null);

  // Initialize form with recipe data
  useEffect(() => {
    if (recipe) {
      setFormData({
        name: recipe.name,
        menu_item_id: recipe.menu_item_id,
        status: recipe.status,
        complexity: recipe.complexity,
        yield_quantity: recipe.yield_quantity,
        yield_unit: recipe.yield_unit || '',
        portion_size: recipe.portion_size,
        portion_unit: recipe.portion_unit || '',
        prep_time_minutes: recipe.prep_time_minutes,
        cook_time_minutes: recipe.cook_time_minutes,
        total_time_minutes: recipe.total_time_minutes,
        instructions: recipe.instructions || [''],
        notes: recipe.notes || '',
        allergen_notes: recipe.allergen_notes || '',
        plating_instructions: recipe.plating_instructions || '',
        image_urls: recipe.image_urls || ['']
      });
      setIngredients(recipe.ingredients.map(ing => ({ ...ing })));
    }
  }, [recipe]);

  // Calculate total time when prep or cook time changes
  useEffect(() => {
    const prep = formData.prep_time_minutes || 0;
    const cook = formData.cook_time_minutes || 0;
    const total = prep + cook;
    
    if (total > 0 && total !== formData.total_time_minutes) {
      setFormData(prev => ({ ...prev, total_time_minutes: total }));
    }
  }, [formData.prep_time_minutes, formData.cook_time_minutes]);

  // Calculate estimated cost
  useEffect(() => {
    if (!inventoryData?.items) return;

    let totalCost = 0;
    ingredients.forEach(ingredient => {
      const inventoryItem = inventoryData.items.find((item: InventoryItem) => 
        item.id === ingredient.inventory_id
      );
      if (inventoryItem) {
        totalCost += ingredient.quantity * (inventoryItem.cost_per_unit || 0);
      }
    });
    setEstimatedCost(totalCost);
  }, [ingredients, inventoryData]);

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error for this field
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const handleInstructionChange = (index: number, value: string) => {
    const newInstructions = [...formData.instructions];
    newInstructions[index] = value;
    setFormData(prev => ({ ...prev, instructions: newInstructions }));
  };

  const addInstruction = () => {
    setFormData(prev => ({ 
      ...prev, 
      instructions: [...prev.instructions, ''] 
    }));
  };

  const removeInstruction = (index: number) => {
    const newInstructions = formData.instructions.filter((_, i) => i !== index);
    setFormData(prev => ({ ...prev, instructions: newInstructions }));
  };

  const handleIngredientChange = (index: number, field: string, value: any) => {
    const newIngredients = [...ingredients];
    newIngredients[index] = { ...newIngredients[index], [field]: value };
    setIngredients(newIngredients);
  };

  const addIngredient = () => {
    setIngredients([...ingredients, {
      inventory_id: 0,
      quantity: 1,
      unit: 'g',
      custom_unit: null,
      preparation: null,
      is_optional: false,
      notes: null,
      display_order: ingredients.length
    }]);
  };

  const removeIngredient = (index: number) => {
    setIngredients(ingredients.filter((_, i) => i !== index));
  };

  const moveIngredient = (index: number, direction: 'up' | 'down') => {
    if (
      (direction === 'up' && index === 0) ||
      (direction === 'down' && index === ingredients.length - 1)
    ) {
      return;
    }

    const newIngredients = [...ingredients];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    
    // Swap ingredients
    [newIngredients[index], newIngredients[targetIndex]] = 
    [newIngredients[targetIndex], newIngredients[index]];
    
    // Update display order
    newIngredients.forEach((ing, i) => {
      ing.display_order = i;
    });
    
    setIngredients(newIngredients);
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Recipe name is required';
    }

    if (!formData.menu_item_id) {
      newErrors.menu_item_id = 'Menu item is required';
    }

    if (formData.yield_quantity <= 0) {
      newErrors.yield_quantity = 'Yield quantity must be positive';
    }

    if (!formData.yield_unit) {
      newErrors.yield_unit = 'Yield unit is required';
    }

    if (ingredients.length === 0) {
      newErrors.ingredients = 'At least one ingredient is required';
    }

    ingredients.forEach((ingredient, index) => {
      if (!ingredient.inventory_id) {
        newErrors[`ingredient_${index}_inventory`] = 'Ingredient is required';
      }
      if (ingredient.quantity <= 0) {
        newErrors[`ingredient_${index}_quantity`] = 'Quantity must be positive';
      }
      if (ingredient.unit === 'custom' && !ingredient.custom_unit) {
        newErrors[`ingredient_${index}_custom_unit`] = 'Custom unit is required';
      }
    });

    const validInstructions = formData.instructions.filter(inst => inst.trim());
    if (validInstructions.length === 0) {
      newErrors.instructions = 'At least one instruction is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setShowValidation(true);

    if (!validateForm()) {
      return;
    }

    // Prepare data for submission
    const submitData = {
      ...formData,
      instructions: formData.instructions.filter(inst => inst.trim()),
      image_urls: formData.image_urls.filter(url => url.trim()),
      ingredients: ingredients.map(ing => ({
        inventory_id: ing.inventory_id,
        quantity: ing.quantity,
        unit: ing.unit,
        custom_unit: ing.custom_unit,
        preparation: ing.preparation,
        is_optional: ing.is_optional,
        notes: ing.notes,
        display_order: ing.display_order
      }))
    };

    onSave(submitData);
  };

  if (loadingInventory) {
    return <SkeletonLoader />;
  }

  const inventoryItems = inventoryData?.items || [];
  const selectedMenuItem = menuItems.find(item => item.id === formData.menu_item_id);
  const foodCostPercentage = selectedMenuItem?.price && estimatedCost
    ? ((estimatedCost / selectedMenuItem.price) * 100).toFixed(1)
    : null;

  return (
    <form className="recipe-form" onSubmit={handleSubmit}>
      <div className="form-header">
        <h2>{recipe ? 'Edit Recipe' : 'Create New Recipe'}</h2>
        {estimatedCost !== null && (
          <div className="cost-summary">
            <span className="cost-label">Estimated Cost:</span>
            <span className="cost-value">${estimatedCost.toFixed(2)}</span>
            {foodCostPercentage && (
              <span className={`cost-percentage ${parseFloat(foodCostPercentage) > 35 ? 'high' : ''}`}>
                ({foodCostPercentage}% of menu price)
              </span>
            )}
          </div>
        )}
      </div>

      <div className="form-section">
        <h3>Basic Information</h3>
        
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="name">Recipe Name *</label>
            <input
              type="text"
              id="name"
              value={formData.name}
              onChange={(e) => handleInputChange('name', e.target.value)}
              className={errors.name ? 'error' : ''}
              placeholder="e.g., Classic Margherita Pizza"
            />
            {errors.name && <span className="error-message">{errors.name}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="menu_item_id">Menu Item *</label>
            <select
              id="menu_item_id"
              value={formData.menu_item_id}
              onChange={(e) => handleInputChange('menu_item_id', parseInt(e.target.value))}
              className={errors.menu_item_id ? 'error' : ''}
            >
              <option value={0}>Select a menu item</option>
              {menuItems.map(item => (
                <option key={item.id} value={item.id}>
                  {item.name} - {item.category}
                </option>
              ))}
            </select>
            {errors.menu_item_id && <span className="error-message">{errors.menu_item_id}</span>}
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="status">Status</label>
            <select
              id="status"
              value={formData.status}
              onChange={(e) => handleInputChange('status', e.target.value)}
            >
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="complexity">Complexity</label>
            <select
              id="complexity"
              value={formData.complexity}
              onChange={(e) => handleInputChange('complexity', e.target.value)}
            >
              <option value="simple">Simple</option>
              <option value="moderate">Moderate</option>
              <option value="complex">Complex</option>
              <option value="expert">Expert</option>
            </select>
          </div>
        </div>
      </div>

      <div className="form-section">
        <h3>Yield & Portions</h3>
        
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="yield_quantity">Yield Quantity *</label>
            <input
              type="number"
              id="yield_quantity"
              value={formData.yield_quantity}
              onChange={(e) => handleInputChange('yield_quantity', parseFloat(e.target.value))}
              className={errors.yield_quantity ? 'error' : ''}
              min="0.01"
              step="0.01"
            />
            {errors.yield_quantity && <span className="error-message">{errors.yield_quantity}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="yield_unit">Yield Unit *</label>
            <input
              type="text"
              id="yield_unit"
              value={formData.yield_unit}
              onChange={(e) => handleInputChange('yield_unit', e.target.value)}
              className={errors.yield_unit ? 'error' : ''}
              placeholder="e.g., servings, portions, pieces"
            />
            {errors.yield_unit && <span className="error-message">{errors.yield_unit}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="portion_size">Portion Size</label>
            <input
              type="number"
              id="portion_size"
              value={formData.portion_size || ''}
              onChange={(e) => handleInputChange('portion_size', e.target.value ? parseFloat(e.target.value) : null)}
              min="0.01"
              step="0.01"
            />
          </div>

          <div className="form-group">
            <label htmlFor="portion_unit">Portion Unit</label>
            <input
              type="text"
              id="portion_unit"
              value={formData.portion_unit}
              onChange={(e) => handleInputChange('portion_unit', e.target.value)}
              placeholder="e.g., grams, ounces"
            />
          </div>
        </div>
      </div>

      <div className="form-section">
        <h3>Preparation Times</h3>
        
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="prep_time">Prep Time (minutes)</label>
            <input
              type="number"
              id="prep_time"
              value={formData.prep_time_minutes || ''}
              onChange={(e) => handleInputChange('prep_time_minutes', e.target.value ? parseInt(e.target.value) : null)}
              min="0"
            />
          </div>

          <div className="form-group">
            <label htmlFor="cook_time">Cook Time (minutes)</label>
            <input
              type="number"
              id="cook_time"
              value={formData.cook_time_minutes || ''}
              onChange={(e) => handleInputChange('cook_time_minutes', e.target.value ? parseInt(e.target.value) : null)}
              min="0"
            />
          </div>

          <div className="form-group">
            <label htmlFor="total_time">Total Time (minutes)</label>
            <input
              type="number"
              id="total_time"
              value={formData.total_time_minutes || ''}
              onChange={(e) => handleInputChange('total_time_minutes', e.target.value ? parseInt(e.target.value) : null)}
              min="0"
            />
          </div>
        </div>
      </div>

      <div className="form-section">
        <h3>Ingredients</h3>
        {errors.ingredients && <span className="error-message">{errors.ingredients}</span>}
        
        <div className="ingredients-list">
          {ingredients.map((ingredient, index) => (
            <div key={index} className="ingredient-row">
              <div className="ingredient-controls">
                <button
                  type="button"
                  className="btn-icon"
                  onClick={() => moveIngredient(index, 'up')}
                  disabled={index === 0}
                  title="Move up"
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="btn-icon"
                  onClick={() => moveIngredient(index, 'down')}
                  disabled={index === ingredients.length - 1}
                  title="Move down"
                >
                  ↓
                </button>
              </div>

              <div className="ingredient-fields">
                <div className="form-group">
                  <label>Ingredient *</label>
                  <select
                    value={ingredient.inventory_id}
                    onChange={(e) => handleIngredientChange(index, 'inventory_id', parseInt(e.target.value))}
                    className={errors[`ingredient_${index}_inventory`] ? 'error' : ''}
                  >
                    <option value={0}>Select ingredient</option>
                    {inventoryItems.map((item: InventoryItem) => (
                      <option key={item.id} value={item.id}>
                        {item.item_name} ({item.unit})
                      </option>
                    ))}
                  </select>
                  {errors[`ingredient_${index}_inventory`] && 
                    <span className="error-message">{errors[`ingredient_${index}_inventory`]}</span>
                  }
                </div>

                <div className="form-group">
                  <label>Quantity *</label>
                  <input
                    type="number"
                    value={ingredient.quantity}
                    onChange={(e) => handleIngredientChange(index, 'quantity', parseFloat(e.target.value))}
                    className={errors[`ingredient_${index}_quantity`] ? 'error' : ''}
                    min="0.001"
                    step="0.001"
                  />
                  {errors[`ingredient_${index}_quantity`] && 
                    <span className="error-message">{errors[`ingredient_${index}_quantity`]}</span>
                  }
                </div>

                <div className="form-group">
                  <label>Unit *</label>
                  <select
                    value={ingredient.unit}
                    onChange={(e) => handleIngredientChange(index, 'unit', e.target.value)}
                  >
                    {UNIT_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                {ingredient.unit === 'custom' && (
                  <div className="form-group">
                    <label>Custom Unit *</label>
                    <input
                      type="text"
                      value={ingredient.custom_unit || ''}
                      onChange={(e) => handleIngredientChange(index, 'custom_unit', e.target.value)}
                      className={errors[`ingredient_${index}_custom_unit`] ? 'error' : ''}
                      placeholder="e.g., pinch, dash"
                    />
                    {errors[`ingredient_${index}_custom_unit`] && 
                      <span className="error-message">{errors[`ingredient_${index}_custom_unit`]}</span>
                    }
                  </div>
                )}

                <div className="form-group">
                  <label>Preparation</label>
                  <input
                    type="text"
                    value={ingredient.preparation || ''}
                    onChange={(e) => handleIngredientChange(index, 'preparation', e.target.value)}
                    placeholder="e.g., diced, minced, julienned"
                  />
                </div>

                <div className="form-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={ingredient.is_optional}
                      onChange={(e) => handleIngredientChange(index, 'is_optional', e.target.checked)}
                    />
                    Optional
                  </label>
                </div>

                <div className="form-group">
                  <label>Notes</label>
                  <input
                    type="text"
                    value={ingredient.notes || ''}
                    onChange={(e) => handleIngredientChange(index, 'notes', e.target.value)}
                    placeholder="Any special notes"
                  />
                </div>
              </div>

              <button
                type="button"
                className="btn-remove"
                onClick={() => removeIngredient(index)}
                title="Remove ingredient"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <button
          type="button"
          className="btn btn-secondary add-ingredient"
          onClick={addIngredient}
        >
          + Add Ingredient
        </button>
      </div>

      <div className="form-section">
        <h3>Instructions</h3>
        {errors.instructions && <span className="error-message">{errors.instructions}</span>}
        
        <div className="instructions-list">
          {formData.instructions.map((instruction, index) => (
            <div key={index} className="instruction-row">
              <span className="step-number">Step {index + 1}</span>
              <textarea
                value={instruction}
                onChange={(e) => handleInstructionChange(index, e.target.value)}
                placeholder="Enter instruction step..."
                rows={2}
              />
              {formData.instructions.length > 1 && (
                <button
                  type="button"
                  className="btn-remove"
                  onClick={() => removeInstruction(index)}
                  title="Remove instruction"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={addInstruction}
        >
          + Add Instruction
        </button>
      </div>

      <div className="form-section">
        <h3>Additional Information</h3>
        
        <div className="form-group">
          <label htmlFor="notes">Recipe Notes</label>
          <textarea
            id="notes"
            value={formData.notes}
            onChange={(e) => handleInputChange('notes', e.target.value)}
            rows={3}
            placeholder="Any additional notes about this recipe..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="allergen_notes">Allergen Notes</label>
          <textarea
            id="allergen_notes"
            value={formData.allergen_notes}
            onChange={(e) => handleInputChange('allergen_notes', e.target.value)}
            rows={2}
            placeholder="List any allergens or dietary restrictions..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="plating_instructions">Plating Instructions</label>
          <textarea
            id="plating_instructions"
            value={formData.plating_instructions}
            onChange={(e) => handleInputChange('plating_instructions', e.target.value)}
            rows={3}
            placeholder="Describe how to plate and present this dish..."
          />
        </div>
      </div>

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary">
          {recipe ? 'Update Recipe' : 'Create Recipe'}
        </button>
      </div>
    </form>
  );
};

export default RecipeForm;