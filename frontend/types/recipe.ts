// frontend/types/recipe.ts

export interface Recipe {
  id: number;
  name: string;
  menu_item_id: number;
  status: RecipeStatus;
  complexity: RecipeComplexity;
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
  total_cost: number | null;
  food_cost_percentage: number | null;
  last_cost_update: string | null;
  version: number;
  created_by: number;
  approved_by: number | null;
  approved_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  ingredients: RecipeIngredient[];
  sub_recipes?: RecipeSubRecipe[];
}

export interface RecipeIngredient {
  id: number;
  recipe_id: number;
  inventory_id: number;
  quantity: number;
  unit: UnitType;
  custom_unit: string | null;
  preparation: string | null;
  is_optional: boolean;
  notes: string | null;
  display_order: number;
  unit_cost: number | null;
  total_cost: number | null;
  created_at: string;
  updated_at: string;
  inventory_item?: InventoryItem;
}

export interface RecipeSubRecipe {
  id: number;
  parent_recipe_id: number;
  sub_recipe_id: number;
  quantity: number;
  unit: string | null;
  display_order: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
  sub_recipe?: Recipe;
}

export interface InventoryItem {
  id: number;
  item_name: string;
  unit: string;
  cost_per_unit: number;
  category: string;
  vendor_id: number;
}

export interface RecipeValidation {
  recipe_id: number;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

export interface RecipeCostAnalysis {
  recipe_id: number;
  total_cost: number;
  cost_per_portion: number;
  food_cost_percentage: number;
  ingredient_costs: IngredientCost[];
  last_updated: string;
}

export interface IngredientCost {
  inventory_id: number;
  item_name: string;
  quantity: number;
  unit: string;
  unit_cost: number;
  total_cost: number;
  percentage_of_total: number;
}

export interface RecipeComplianceReport {
  total_menu_items: number;
  items_with_recipes: number;
  items_without_recipes: number;
  compliance_percentage: number;
  missing_recipes: MenuItemRecipeStatus[];
  draft_recipes: MenuItemRecipeStatus[];
  last_updated: string;
}

export interface MenuItemRecipeStatus {
  menu_item_id: number;
  menu_item_name: string;
  category: string;
  has_recipe: boolean;
  recipe_status: string | null;
  recipe_id: number | null;
}

export interface RecipeHistoryEntry {
  id: number;
  recipe_id: number;
  version: number;
  change_type: string;
  changes: any;
  changed_by: number;
  changed_at: string;
  notes: string | null;
  user_name?: string;
}

export enum RecipeStatus {
  DRAFT = 'draft',
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  ARCHIVED = 'archived'
}

export enum RecipeComplexity {
  SIMPLE = 'simple',
  MODERATE = 'moderate',
  COMPLEX = 'complex',
  EXPERT = 'expert'
}

export enum UnitType {
  // Weight
  GRAM = 'g',
  KILOGRAM = 'kg',
  OUNCE = 'oz',
  POUND = 'lb',
  
  // Volume
  MILLILITER = 'ml',
  LITER = 'l',
  TEASPOON = 'tsp',
  TABLESPOON = 'tbsp',
  CUP = 'cup',
  FLUID_OUNCE = 'fl_oz',
  PINT = 'pt',
  QUART = 'qt',
  GALLON = 'gal',
  
  // Count
  PIECE = 'piece',
  DOZEN = 'dozen',
  
  // Other
  CUSTOM = 'custom'
}

// Request/Response interfaces
export interface RecipeCreateRequest {
  name: string;
  menu_item_id: number;
  status?: RecipeStatus;
  complexity?: RecipeComplexity;
  yield_quantity: number;
  yield_unit: string;
  portion_size?: number;
  portion_unit?: string;
  prep_time_minutes?: number;
  cook_time_minutes?: number;
  total_time_minutes?: number;
  instructions?: string[];
  notes?: string;
  allergen_notes?: string;
  quality_standards?: any;
  plating_instructions?: string;
  image_urls?: string[];
  ingredients: RecipeIngredientCreate[];
  sub_recipes?: RecipeSubRecipeCreate[];
}

export interface RecipeIngredientCreate {
  inventory_id: number;
  quantity: number;
  unit: UnitType;
  custom_unit?: string;
  preparation?: string;
  is_optional?: boolean;
  notes?: string;
  display_order?: number;
}

export interface RecipeSubRecipeCreate {
  sub_recipe_id: number;
  quantity: number;
  unit?: string;
  display_order?: number;
  notes?: string;
}

export interface RecipeSearchParams {
  query?: string;
  menu_item_id?: number;
  status?: string;
  complexity?: string;
  min_cost?: number;
  max_cost?: number;
  ingredient_id?: number;
  limit?: number;
  offset?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface BulkRecipeUpdate {
  recipe_ids: number[];
  updates: Partial<Recipe>;
}