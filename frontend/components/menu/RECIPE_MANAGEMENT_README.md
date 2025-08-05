# Recipe Management UI Documentation

## Overview

The Recipe Management UI provides a comprehensive interface for managing restaurant recipes, including ingredient configurations, cost tracking, version history, and compliance monitoring.

## Features

### 1. Recipe Configuration
- **Create/Edit Recipes**: Configure recipes with ingredients, quantities, and preparation instructions
- **Ingredient Management**: Add, remove, and reorder ingredients with precise measurements
- **Cost Tracking**: Real-time cost calculation based on inventory prices
- **Complexity Levels**: Categorize recipes by difficulty (Simple, Moderate, Complex, Expert)
- **Time Tracking**: Record prep time, cook time, and total time

### 2. Recipe Review & Accuracy
- **Compliance Dashboard**: Monitor which menu items are missing recipes
- **Validation System**: Automated checks for recipe completeness and accuracy
- **Cost Analysis**: View detailed cost breakdowns and food cost percentages
- **Approval Workflow**: Manager/admin approval process for recipe changes

### 3. Version History
- **Change Tracking**: Complete audit trail of all recipe modifications
- **Version Comparison**: Compare different versions of recipes
- **User Attribution**: Track who made changes and when
- **Rollback Capability**: Revert to previous versions if needed

### 4. Bulk Operations
- **Mass Updates**: Update multiple recipes simultaneously
- **Bulk Activation**: Activate/deactivate recipes in batches
- **Cost Recalculation**: Recalculate all recipe costs with updated ingredient prices

## Components

### RecipeManagement.tsx
Main container component that manages the overall recipe interface.

**Key Props**: None (uses internal state and API hooks)

**Features**:
- Tab navigation between different views
- Permission-based access control
- Toast notifications for user feedback
- Compliance alerts

### RecipeList.tsx
Displays recipes in a sortable, filterable table format.

**Key Props**:
- `recipes`: Array of recipe objects
- `menuItems`: Array of menu item objects
- `onEdit`, `onDelete`, `onReview`, `onViewHistory`, `onApprove`: Callback functions
- Permission flags: `canEdit`, `canDelete`, `canApprove`

**Features**:
- Search and filter by status/complexity
- Sort by name, cost, or update date
- Bulk selection for mass operations
- Visual indicators for approval status and high food costs

### RecipeForm.tsx
Comprehensive form for creating and editing recipes.

**Key Props**:
- `recipe`: Recipe object (null for new recipes)
- `menuItems`: Available menu items
- `onSave`: Save callback
- `onCancel`: Cancel callback

**Features**:
- Dynamic ingredient management
- Real-time cost calculation
- Drag-and-drop ingredient reordering
- Custom unit support
- Validation with error messages

### RecipeReview.tsx
Review interface for recipe accuracy and compliance.

**Key Props**:
- `recipes`: All recipes
- `menuItems`: All menu items
- `complianceReport`: Compliance data
- `onEdit`, `onApprove`: Callback functions
- Permission flags

**Features**:
- Missing recipe identification
- Recipe validation results
- Cost analysis display
- Approval workflow interface

### RecipeHistory.tsx
Version history viewer with comparison capabilities.

**Key Props**:
- `recipeId`: ID of the recipe
- `recipeName`: Name for display
- `onClose`: Close callback

**Features**:
- Timeline view of changes
- Expandable change details
- Version selection for comparison
- Change type categorization

## API Integration

### Endpoints Used
- `GET /api/v1/menu/recipes` - List recipes with filters
- `POST /api/v1/menu/recipes` - Create new recipe
- `PUT /api/v1/menu/recipes/{id}` - Update recipe
- `DELETE /api/v1/menu/recipes/{id}` - Delete recipe
- `GET /api/v1/menu/recipes/{id}/validate` - Validate recipe
- `GET /api/v1/menu/recipes/{id}/cost-analysis` - Get cost analysis
- `GET /api/v1/menu/recipes/{id}/history` - Get version history
- `POST /api/v1/menu/recipes/{id}/approve` - Approve recipe
- `GET /api/v1/menu/recipes/compliance/report` - Get compliance report
- `POST /api/v1/menu/recipes/recalculate-costs` - Recalculate all costs

## Permissions

The UI respects the following permissions:
- `menu:read` - View recipes and reports
- `menu:create` - Create new recipes
- `menu:update` - Edit existing recipes
- `menu:delete` - Delete recipes
- `manager:recipes` - Approve recipes and perform bulk operations
- `admin:recipes` - Full access including cost recalculation

## Usage Example

```tsx
import RecipeManagement from './components/menu/RecipeManagement';

function MenuPage() {
  return (
    <div>
      <RecipeManagement />
    </div>
  );
}
```

## Styling

All components use CSS modules with responsive design:
- Mobile-first approach
- Tablet and desktop breakpoints
- Accessible color contrasts
- Loading states with skeleton loaders

## Testing

Comprehensive test coverage includes:
- Component rendering tests
- User interaction tests
- API integration tests
- Permission-based access tests
- Error handling tests

Run tests with:
```bash
npm test RecipeManagement.test.tsx
```

## Future Enhancements

Potential improvements for future releases:
1. Recipe templates for common dishes
2. Nutritional information tracking
3. Photo upload for plating instructions
4. Recipe sharing between locations
5. Integration with inventory forecasting
6. Mobile app support for kitchen staff