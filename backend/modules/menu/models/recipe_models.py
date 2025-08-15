# backend/modules/menu/models/recipe_models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Float,
    Text,
    Boolean,
    JSON,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from enum import Enum


class RecipeStatus(str, Enum):
    """Recipe status enumeration"""

    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class RecipeComplexity(str, Enum):
    """Recipe complexity levels"""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


class UnitType(str, Enum):
    """Common unit types for ingredients"""

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


class Recipe(Base, TimestampMixin):
    """Recipe (Bill of Materials) for menu items"""

    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    menu_item_id = Column(
        Integer, ForeignKey("menu_items.id"), nullable=False, unique=True
    )
    name = Column(String(200), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(SQLEnum(RecipeStatus), nullable=False, default=RecipeStatus.DRAFT)

    # Recipe details
    yield_quantity = Column(Float, nullable=False, default=1.0)
    yield_unit = Column(String(50), nullable=True)
    portion_size = Column(Float, nullable=True)
    portion_unit = Column(String(50), nullable=True)

    # Preparation details
    prep_time_minutes = Column(Integer, nullable=True)
    cook_time_minutes = Column(Integer, nullable=True)
    total_time_minutes = Column(Integer, nullable=True)
    complexity = Column(
        SQLEnum(RecipeComplexity), nullable=False, default=RecipeComplexity.SIMPLE
    )

    # Instructions and notes
    instructions = Column(JSON, nullable=True)  # List of step-by-step instructions
    notes = Column(Text, nullable=True)
    allergen_notes = Column(Text, nullable=True)

    # Cost calculations
    total_cost = Column(Float, nullable=True)  # Calculated from ingredients
    food_cost_percentage = Column(Float, nullable=True)  # Cost as % of menu price
    last_cost_update = Column(DateTime, nullable=True)

    # Quality and consistency
    quality_standards = Column(
        JSON, nullable=True
    )  # Temperature, texture, presentation standards
    plating_instructions = Column(Text, nullable=True)
    image_urls = Column(JSON, nullable=True)  # Reference images

    # Metadata
    created_by = Column(Integer, nullable=False)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    menu_item = relationship("MenuItem", backref="recipe", uselist=False)
    ingredients = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan"
    )
    sub_recipes = relationship(
        "RecipeSubRecipe",
        foreign_keys="RecipeSubRecipe.parent_recipe_id",
        back_populates="parent_recipe",
    )
    parent_recipes = relationship(
        "RecipeSubRecipe",
        foreign_keys="RecipeSubRecipe.sub_recipe_id",
        back_populates="sub_recipe",
    )
    history = relationship(
        "RecipeHistory",
        back_populates="recipe",
        order_by="RecipeHistory.created_at.desc()",
    )

    def __repr__(self):
        return f"<Recipe(id={self.id}, name='{self.name}', menu_item_id={self.menu_item_id})>"


class RecipeIngredient(Base, TimestampMixin):
    """Ingredients in a recipe with quantities"""

    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "inventory_id", name="_recipe_inventory_uc"),
    )

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)

    # Quantity and unit
    quantity = Column(Float, nullable=False)
    unit = Column(SQLEnum(UnitType), nullable=False)
    custom_unit = Column(String(50), nullable=True)  # For when unit is CUSTOM

    # Preparation notes
    preparation = Column(String(200), nullable=True)  # "diced", "julienned", etc.
    is_optional = Column(Boolean, nullable=False, default=False)

    # Cost tracking
    unit_cost = Column(Float, nullable=True)  # Cost per unit at time of recipe creation
    total_cost = Column(Float, nullable=True)  # quantity * unit_cost

    # Display order
    display_order = Column(Integer, nullable=False, default=0)

    # Notes
    notes = Column(Text, nullable=True)

    # Metadata
    created_by = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    recipe = relationship("Recipe", back_populates="ingredients")
    inventory_item = relationship("Inventory", backref="recipe_ingredients")

    def __repr__(self):
        return f"<RecipeIngredient(recipe_id={self.recipe_id}, inventory_id={self.inventory_id}, quantity={self.quantity})>"


class RecipeSubRecipe(Base, TimestampMixin):
    """Sub-recipes within recipes (e.g., sauce recipe within a dish recipe)"""

    __tablename__ = "recipe_sub_recipes"
    __table_args__ = (
        UniqueConstraint(
            "parent_recipe_id", "sub_recipe_id", name="_parent_sub_recipe_uc"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    parent_recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)
    sub_recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)

    # Quantity of sub-recipe needed
    quantity = Column(Float, nullable=False, default=1.0)
    unit = Column(String(50), nullable=True)  # portions, batches, etc.

    # Display order
    display_order = Column(Integer, nullable=False, default=0)

    # Notes
    notes = Column(Text, nullable=True)

    # Metadata
    created_by = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    parent_recipe = relationship(
        "Recipe", foreign_keys=[parent_recipe_id], back_populates="sub_recipes"
    )
    sub_recipe = relationship(
        "Recipe", foreign_keys=[sub_recipe_id], back_populates="parent_recipes"
    )

    def __repr__(self):
        return f"<RecipeSubRecipe(parent_id={self.parent_recipe_id}, sub_id={self.sub_recipe_id})>"


class RecipeHistory(Base, TimestampMixin):
    """Track changes to recipes for audit and rollback"""

    __tablename__ = "recipe_history"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)
    version = Column(Integer, nullable=False)

    # What changed
    change_type = Column(
        String(50), nullable=False
    )  # created, updated, ingredients_changed, etc.
    change_summary = Column(Text, nullable=False)

    # Snapshot of recipe data
    recipe_snapshot = Column(
        JSON, nullable=False
    )  # Complete recipe data at this version
    ingredients_snapshot = Column(JSON, nullable=False)  # Complete ingredients list

    # Cost at time of change
    total_cost = Column(Float, nullable=True)
    food_cost_percentage = Column(Float, nullable=True)

    # Who made the change
    changed_by = Column(Integer, nullable=False)
    change_reason = Column(Text, nullable=True)

    # Approval if required
    requires_approval = Column(Boolean, nullable=False, default=False)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Metadata
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    recipe = relationship("Recipe", back_populates="history")

    def __repr__(self):
        return f"<RecipeHistory(recipe_id={self.recipe_id}, version={self.version}, change_type='{self.change_type}')>"


class RecipeNutrition(Base, TimestampMixin):
    """Nutritional information for recipes"""

    __tablename__ = "recipe_nutrition"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False, unique=True)

    # Basic nutrition per serving
    calories = Column(Float, nullable=True)
    total_fat = Column(Float, nullable=True)  # grams
    saturated_fat = Column(Float, nullable=True)  # grams
    trans_fat = Column(Float, nullable=True)  # grams
    cholesterol = Column(Float, nullable=True)  # milligrams
    sodium = Column(Float, nullable=True)  # milligrams
    total_carbohydrates = Column(Float, nullable=True)  # grams
    dietary_fiber = Column(Float, nullable=True)  # grams
    sugars = Column(Float, nullable=True)  # grams
    protein = Column(Float, nullable=True)  # grams

    # Vitamins and minerals (as % of daily value)
    vitamin_a = Column(Float, nullable=True)
    vitamin_c = Column(Float, nullable=True)
    calcium = Column(Float, nullable=True)
    iron = Column(Float, nullable=True)

    # Additional nutrition facts
    additional_nutrients = Column(JSON, nullable=True)

    # Calculation method
    calculation_method = Column(
        String(50), nullable=True
    )  # manual, calculated, estimated
    last_calculated = Column(DateTime, nullable=True)

    # Metadata
    created_by = Column(Integer, nullable=True)
    verified_by = Column(Integer, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    recipe = relationship("Recipe", backref="nutrition", uselist=False)

    def __repr__(self):
        return (
            f"<RecipeNutrition(recipe_id={self.recipe_id}, calories={self.calories})>"
        )
