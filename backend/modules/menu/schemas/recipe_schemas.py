# backend/modules/menu/schemas/recipe_schemas.py

from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class RecipeStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class RecipeComplexity(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


class UnitType(str, Enum):
    # Weight
    GRAM = "g"
    KILOGRAM = "kg"
    OUNCE = "oz"
    POUND = "lb"

    # Volume
    MILLILITER = "ml"
    LITER = "l"
    TEASPOON = "tsp"
    TABLESPOON = "tbsp"
    CUP = "cup"
    FLUID_OUNCE = "fl_oz"
    PINT = "pt"
    QUART = "qt"
    GALLON = "gal"

    # Count
    PIECE = "piece"
    DOZEN = "dozen"

    # Other
    CUSTOM = "custom"


# Base schemas
class RecipeIngredientBase(BaseModel):
    inventory_id: int
    quantity: float = Field(..., gt=0, description="Quantity must be positive")
    unit: UnitType
    custom_unit: Optional[str] = None
    preparation: Optional[str] = Field(None, max_length=200)
    is_optional: bool = False
    notes: Optional[str] = None
    display_order: int = 0

    @validator("custom_unit")
    def validate_custom_unit(cls, v, values):
        if values.get("unit") == UnitType.CUSTOM and not v:
            raise ValueError("custom_unit is required when unit is CUSTOM")
        return v


class RecipeIngredientCreate(RecipeIngredientBase):
    pass


class RecipeIngredientUpdate(BaseModel):
    quantity: Optional[float] = Field(None, gt=0)
    unit: Optional[UnitType] = None
    custom_unit: Optional[str] = None
    preparation: Optional[str] = Field(None, max_length=200)
    is_optional: Optional[bool] = None
    notes: Optional[str] = None
    display_order: Optional[int] = None


class RecipeIngredientResponse(RecipeIngredientBase):
    id: int
    recipe_id: int
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    # Include inventory item details
    inventory_item: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class RecipeSubRecipeBase(BaseModel):
    sub_recipe_id: int = Field(..., gt=0, description="ID of the sub-recipe to link")
    quantity: float = Field(1.0, gt=0, description="Quantity of sub-recipe to use")
    unit: Optional[str] = Field(
        None, max_length=50, description="Unit for quantity (optional)"
    )
    display_order: int = Field(0, ge=0, description="Display order in recipe")
    notes: Optional[str] = Field(
        None, max_length=500, description="Notes about this sub-recipe usage"
    )

    @validator("sub_recipe_id")
    def validate_sub_recipe_id(cls, v):
        """Ensure sub_recipe_id is a valid positive integer"""
        if v <= 0:
            raise ValueError("sub_recipe_id must be a positive integer")
        return v

    @validator("unit")
    def validate_unit(cls, v):
        """Validate unit if provided"""
        if v and len(v.strip()) == 0:
            return None
        return v.strip() if v else None


class RecipeSubRecipeCreate(RecipeSubRecipeBase):
    pass


class RecipeSubRecipeResponse(RecipeSubRecipeBase):
    id: int
    parent_recipe_id: int
    created_at: datetime
    updated_at: datetime

    # Include sub-recipe details
    sub_recipe: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class RecipeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    status: RecipeStatus = RecipeStatus.DRAFT

    # Recipe details
    yield_quantity: float = Field(1.0, gt=0)
    yield_unit: Optional[str] = None
    portion_size: Optional[float] = Field(None, gt=0)
    portion_unit: Optional[str] = None

    # Preparation details
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    cook_time_minutes: Optional[int] = Field(None, ge=0)
    total_time_minutes: Optional[int] = Field(None, ge=0)
    complexity: RecipeComplexity = RecipeComplexity.SIMPLE

    # Instructions and notes
    instructions: Optional[List[str]] = None
    notes: Optional[str] = None
    allergen_notes: Optional[str] = None

    # Quality and consistency
    quality_standards: Optional[Dict[str, Any]] = None
    plating_instructions: Optional[str] = None
    image_urls: Optional[List[str]] = None


class RecipeCreate(RecipeBase):
    menu_item_id: int
    ingredients: List[RecipeIngredientCreate]
    sub_recipes: Optional[List[RecipeSubRecipeCreate]] = []


class RecipeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[RecipeStatus] = None

    # Recipe details
    yield_quantity: Optional[float] = Field(None, gt=0)
    yield_unit: Optional[str] = None
    portion_size: Optional[float] = Field(None, gt=0)
    portion_unit: Optional[str] = None

    # Preparation details
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    cook_time_minutes: Optional[int] = Field(None, ge=0)
    total_time_minutes: Optional[int] = Field(None, ge=0)
    complexity: Optional[RecipeComplexity] = None

    # Instructions and notes
    instructions: Optional[List[str]] = None
    notes: Optional[str] = None
    allergen_notes: Optional[str] = None

    # Quality and consistency
    quality_standards: Optional[Dict[str, Any]] = None
    plating_instructions: Optional[str] = None
    image_urls: Optional[List[str]] = None


class RecipeResponse(RecipeBase):
    id: int
    menu_item_id: int
    version: int

    # Cost calculations
    total_cost: Optional[float] = None
    food_cost_percentage: Optional[float] = None
    last_cost_update: Optional[datetime] = None

    # Metadata
    created_by: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Relationships
    ingredients: List[RecipeIngredientResponse] = []
    sub_recipes: List[RecipeSubRecipeResponse] = []

    # Include menu item details
    menu_item: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class RecipeCostAnalysis(BaseModel):
    """Detailed cost breakdown for a recipe"""

    recipe_id: int
    recipe_name: str
    menu_item_id: int
    menu_item_name: str
    menu_item_price: float

    # Cost details
    total_ingredient_cost: float
    total_sub_recipe_cost: float
    total_cost: float

    # Analysis
    food_cost_percentage: float
    profit_margin: float
    profit_amount: float

    # Breakdown
    ingredient_costs: List[Dict[str, Any]]
    sub_recipe_costs: List[Dict[str, Any]]

    # Recommendations
    cost_optimization_suggestions: Optional[List[str]] = None

    class Config:
        from_attributes = True


class RecipeValidation(BaseModel):
    """Recipe validation results"""

    recipe_id: int
    is_valid: bool
    validation_errors: List[str] = []
    warnings: List[str] = []

    # Specific checks
    has_ingredients: bool
    all_ingredients_available: bool
    cost_calculated: bool
    within_target_cost: bool
    instructions_complete: bool

    class Config:
        from_attributes = True


class BulkRecipeUpdate(BaseModel):
    """Bulk update recipes"""

    recipe_ids: List[int]
    updates: RecipeUpdate


class RecipeSearchParams(BaseModel):
    """Search parameters for recipes"""

    query: Optional[str] = None
    menu_item_id: Optional[int] = None
    status: Optional[RecipeStatus] = None
    complexity: Optional[RecipeComplexity] = None
    min_cost: Optional[float] = None
    max_cost: Optional[float] = None
    has_allergens: Optional[bool] = None
    ingredient_id: Optional[int] = None  # Find recipes using specific ingredient
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    sort_by: str = "name"
    sort_order: str = "asc"


class RecipeCloneRequest(BaseModel):
    """Request to clone a recipe"""

    source_recipe_id: int
    target_menu_item_id: int
    name: Optional[str] = None  # Override name
    adjust_portions: Optional[float] = None  # Scale recipe by factor


class RecipeHistoryResponse(BaseModel):
    """Recipe version history"""

    id: int
    recipe_id: int
    version: int
    change_type: str
    change_summary: str
    total_cost: Optional[float] = None
    food_cost_percentage: Optional[float] = None
    changed_by: int
    change_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecipeNutritionBase(BaseModel):
    """Nutritional information for recipes"""

    # Basic nutrition per serving
    calories: Optional[float] = None
    total_fat: Optional[float] = None
    saturated_fat: Optional[float] = None
    trans_fat: Optional[float] = None
    cholesterol: Optional[float] = None
    sodium: Optional[float] = None
    total_carbohydrates: Optional[float] = None
    dietary_fiber: Optional[float] = None
    sugars: Optional[float] = None
    protein: Optional[float] = None

    # Vitamins and minerals (as % of daily value)
    vitamin_a: Optional[float] = None
    vitamin_c: Optional[float] = None
    calcium: Optional[float] = None
    iron: Optional[float] = None

    # Additional nutrition facts
    additional_nutrients: Optional[Dict[str, float]] = None


class RecipeNutritionCreate(RecipeNutritionBase):
    recipe_id: int
    calculation_method: Optional[str] = "manual"


class RecipeNutritionUpdate(RecipeNutritionBase):
    pass


class RecipeNutritionResponse(RecipeNutritionBase):
    id: int
    recipe_id: int
    calculation_method: Optional[str] = None
    last_calculated: Optional[datetime] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MenuItemRecipeStatus(BaseModel):
    """Status of recipe configuration for menu items"""

    menu_item_id: int
    menu_item_name: str
    has_recipe: bool
    recipe_id: Optional[int] = None
    recipe_status: Optional[RecipeStatus] = None
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class RecipeComplianceReport(BaseModel):
    """Report on menu items without recipes"""

    total_menu_items: int
    items_with_recipes: int
    items_without_recipes: int
    compliance_percentage: float

    # Details
    missing_recipes: List[MenuItemRecipeStatus]
    draft_recipes: List[MenuItemRecipeStatus]
    inactive_recipes: List[MenuItemRecipeStatus]

    # By category
    compliance_by_category: Dict[str, Dict[str, Any]]

    # Performance info
    cached: Optional[bool] = False
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
