# Recipe (Bill of Materials) Management

## Overview

The Recipe Management system provides comprehensive Bill of Materials (BOM) functionality for menu items, enabling precise ingredient tracking, cost calculation, and recipe standardization across the restaurant.

## Features

### Core Functionality
- **Recipe Creation**: Link menu items to multiple ingredients with specific quantities
- **Cost Calculation**: Automatic calculation of food costs and profit margins
- **Version Control**: Track recipe changes with full history
- **Sub-Recipes**: Support for component recipes (e.g., sauces, bases)
- **Nutritional Tracking**: Optional nutritional information management
- **Compliance Reporting**: Ensure all active menu items have configured recipes

### Advanced Features
- **Recipe Cloning**: Duplicate recipes with portion adjustments
- **Bulk Operations**: Update multiple recipes simultaneously
- **Cost Analysis**: Detailed breakdown with optimization suggestions
- **Validation**: Comprehensive recipe validation for completeness
- **Search & Filter**: Find recipes by ingredients, cost, complexity

## Database Schema

### Main Tables
- `recipes` - Core recipe information
- `recipe_ingredients` - Ingredients with quantities
- `recipe_sub_recipes` - Component recipe relationships
- `recipe_history` - Version control and audit trail
- `recipe_nutrition` - Nutritional information

## API Endpoints

### Recipe Management
```
POST   /api/v1/menu/recipes                    # Create recipe
GET    /api/v1/menu/recipes/{id}               # Get recipe by ID
GET    /api/v1/menu/recipes/menu-item/{id}     # Get recipe by menu item
PUT    /api/v1/menu/recipes/{id}               # Update recipe
DELETE /api/v1/menu/recipes/{id}               # Delete recipe

GET    /api/v1/menu/recipes                    # Search recipes
PUT    /api/v1/menu/recipes/{id}/ingredients   # Update ingredients
GET    /api/v1/menu/recipes/{id}/cost-analysis # Get cost analysis
GET    /api/v1/menu/recipes/{id}/validate      # Validate recipe
```

### Compliance & Reporting
```
GET    /api/v1/menu/recipes/compliance/report  # Compliance report
GET    /api/v1/menu/recipes/compliance/missing # Items without recipes
POST   /api/v1/menu/recipes/recalculate-costs  # Recalculate all costs
```

### Advanced Operations
```
POST   /api/v1/menu/recipes/clone              # Clone recipe
GET    /api/v1/menu/recipes/{id}/history       # Version history
PUT    /api/v1/menu/recipes/bulk/update        # Bulk update
PUT    /api/v1/menu/recipes/bulk/activate      # Bulk activate/deactivate
```

## Usage Examples

### 1. Creating a Recipe
```python
POST /api/v1/menu/recipes
{
    "menu_item_id": 123,
    "name": "Classic Burger Recipe",
    "yield_quantity": 1,
    "yield_unit": "portion",
    "prep_time_minutes": 10,
    "cook_time_minutes": 8,
    "complexity": "simple",
    "instructions": [
        "Form patty from ground beef",
        "Season with salt and pepper",
        "Grill for 4 minutes per side",
        "Assemble with toppings"
    ],
    "ingredients": [
        {
            "inventory_id": 45,  // Ground beef
            "quantity": 0.25,
            "unit": "kg",
            "preparation": "formed into patty"
        },
        {
            "inventory_id": 89,  // Burger bun
            "quantity": 1,
            "unit": "piece",
            "preparation": "toasted"
        },
        {
            "inventory_id": 12,  // Lettuce
            "quantity": 0.02,
            "unit": "kg",
            "preparation": "shredded"
        }
    ]
}
```

### 2. Getting Cost Analysis
```python
GET /api/v1/menu/recipes/456/cost-analysis

Response:
{
    "recipe_id": 456,
    "recipe_name": "Classic Burger Recipe",
    "menu_item_price": 12.99,
    "total_ingredient_cost": 4.25,
    "total_cost": 4.25,
    "food_cost_percentage": 32.72,
    "profit_margin": 67.28,
    "profit_amount": 8.74,
    "ingredient_costs": [
        {
            "name": "Ground Beef",
            "quantity": 0.25,
            "unit": "kg",
            "unit_cost": 12.00,
            "total_cost": 3.00
        },
        ...
    ],
    "cost_optimization_suggestions": [
        "Consider negotiating better prices for Ground Beef"
    ]
}
```

### 3. Cloning a Recipe
```python
POST /api/v1/menu/recipes/clone
{
    "source_recipe_id": 456,
    "target_menu_item_id": 789,
    "name": "Double Burger Recipe",
    "adjust_portions": 2.0  // Double all quantities
}
```

### 4. Compliance Report
```python
GET /api/v1/menu/recipes/compliance/report

Response:
{
    "total_menu_items": 125,
    "items_with_recipes": 98,
    "items_without_recipes": 27,
    "compliance_percentage": 78.4,
    "missing_recipes": [
        {
            "menu_item_id": 101,
            "menu_item_name": "Caesar Salad",
            "has_recipe": false
        },
        ...
    ],
    "compliance_by_category": {
        "Appetizers": {
            "total": 25,
            "with_recipes": 20,
            "compliance_percentage": 80.0
        },
        ...
    }
}
```

## Recipe Status Workflow

1. **Draft**: Initial recipe creation
2. **Active**: Approved and in use
3. **Inactive**: Temporarily disabled
4. **Archived**: Historical reference only

## Best Practices

### Recipe Creation
- Always include all ingredients, even small amounts
- Use consistent units across similar ingredients
- Add preparation notes for clarity
- Include step-by-step instructions

### Cost Management
- Regularly update inventory costs
- Use the recalculate endpoint after price changes
- Monitor food cost percentages
- Set up alerts for high-cost recipes

### Compliance
- Ensure all active menu items have recipes
- Regularly review the compliance report
- Validate recipes before activating
- Keep recipes updated with menu changes

## Integration Points

### Inventory Management
- Recipes automatically link to inventory items
- Inventory costs flow through to recipe costs
- Stock levels can be checked against recipe requirements

### Order Processing
- Recipe quantities used to deduct inventory
- Accurate cost tracking per order
- Ingredient availability verification

### Analytics
- Food cost analysis by item/category
- Ingredient usage patterns
- Profitability reports

## Performance Considerations

### Optimization
- Recipe searches use database indexes
- Cost calculations are cached
- Bulk operations minimize database calls
- Eager loading prevents N+1 queries

### Scaling
- Recipes support up to 50 ingredients
- History maintains last 100 versions
- Bulk operations handle 100 items

## Migration Guide

### Running Migration
```bash
cd backend
alembic upgrade add_recipe_management
```

### Verification
```sql
-- Check tables created
SELECT table_name FROM information_schema.tables 
WHERE table_name LIKE 'recipe%';

-- Verify enum types
SELECT typname FROM pg_type 
WHERE typname IN ('recipestatus', 'recipecomplexity', 'unittype');
```

## Troubleshooting

### Common Issues

1. **Recipe Already Exists**
   - Each menu item can have only one active recipe
   - Archive or delete existing recipe first

2. **Invalid Ingredients**
   - Verify all inventory IDs exist
   - Check inventory items are active

3. **Cost Calculation Errors**
   - Ensure inventory items have cost_per_unit set
   - Run recalculate-costs endpoint

4. **Permission Errors**
   - Recipe creation requires menu:create permission
   - Bulk operations may require admin access

## Future Enhancements

- [ ] Allergen tracking and warnings
- [ ] Yield scaling for different portion sizes
- [ ] Recipe import/export functionality
- [ ] Photo management for plating reference
- [ ] Integration with kitchen display systems
- [ ] Automated nutritional calculations
- [ ] Supplier-specific ingredient variants
- [ ] Recipe scheduling and seasonal management