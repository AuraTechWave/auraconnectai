# Core Models Implementation Summary

## Overview
Created the missing core models (Restaurant, Floor, Location) that are referenced throughout the codebase but were not implemented.

## Models Created

### 1. Restaurant Model
The root entity for multi-tenant data isolation.

**Key Features:**
- Basic information (name, legal name, brand name)
- Contact details (email, phone, website)
- Full address fields
- Business information (tax ID, license)
- Operational settings (timezone, currency, status)
- Operating hours (JSON format for flexibility)
- Subscription management
- Feature flags and settings

**Status Enum:**
- ACTIVE - Operational restaurant
- INACTIVE - Temporarily closed
- SUSPENDED - Account suspended
- PENDING - Awaiting approval
- CLOSED - Permanently closed

### 2. Location Model
Represents different physical locations for a restaurant (main dining, kitchen, warehouse, etc.)

**Key Features:**
- Links to parent restaurant
- Location type classification
- Separate address (can differ from restaurant)
- Contact information
- Capacity information
- Primary location designation
- Operating hours override capability

**Location Types:**
- RESTAURANT - Main dining location
- KITCHEN - Kitchen/prep area
- WAREHOUSE - Storage facility
- OFFICE - Administrative office
- OTHER - Other location types

### 3. Floor Model
Represents floors/sections within a restaurant for table management.

**Key Features:**
- Links to restaurant and optionally to specific location
- Layout configuration (dimensions, grid, background)
- Status management
- Capacity settings
- Reservation settings
- Service charge configuration
- Default floor designation

**Note:** The Floor model was moved from the tables module to core to avoid circular dependencies.

## Module Structure

```
modules/core/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── core_models.py
├── schemas/
│   ├── __init__.py
│   └── core_schemas.py
└── services/
    ├── __init__.py
    └── core_service.py
```

## Integration Changes

### Tables Module
- Updated to import Floor from core module instead of defining locally
- Removed duplicate FloorStatus enum
- Maintained existing Table model with foreign key to floors table

### Migration Strategy
- Created comprehensive migration file
- Handles case where floors table might already exist
- Inserts default demo restaurant, location, and floor for development
- Proper foreign key constraints and indexes

## Schemas

### Request/Response Schemas
Created comprehensive Pydantic schemas for all models:
- Base schemas with common fields
- Create schemas with required fields
- Update schemas with optional fields
- Response schemas with computed properties
- List response schemas with pagination

### Validation
- Email validation
- Phone number format validation
- URL validation for websites
- Time format validation for operating hours
- Country/currency ISO code validation
- Cross-field validation (e.g., warranty dates)

## Service Layer

Created CoreService with full CRUD operations:
- Restaurant management (with email uniqueness)
- Location management (with primary location handling)
- Floor management (with default floor handling)
- Proper error handling and status codes
- Cascading operations (create restaurant → create default location & floor)

## Database Considerations

### Foreign Key Relationships
- Restaurant → Locations (one-to-many)
- Restaurant → Floors (one-to-many)
- Location → Floors (one-to-many, optional)
- Floor → Tables (one-to-many, defined in tables module)

### Constraints
- Unique email for restaurants
- Unique floor name within restaurant
- Only one primary location per restaurant
- Only one default floor per restaurant

## Usage Examples

### Creating a Restaurant
```python
from modules.core.services import CoreService
from modules.core.schemas import RestaurantCreate

restaurant_data = RestaurantCreate(
    name="Bella Italia",
    email="info@bellaitalia.com",
    phone="+1234567890",
    address_line1="456 Oak Street",
    city="San Francisco",
    state="CA",
    postal_code="94102",
    country="US"
)

service = CoreService(db)
restaurant = service.create_restaurant(restaurant_data)
# Automatically creates default location and floor
```

### Adding a Location
```python
from modules.core.schemas import LocationCreate

location_data = LocationCreate(
    name="Downtown Kitchen",
    location_type="KITCHEN",
    address_line1="789 Pine Street",
    city="San Francisco",
    state="CA",
    postal_code="94103"
)

location = service.create_location(restaurant.id, location_data)
```

## Benefits

1. **Centralized Core Models**: All fundamental entities in one place
2. **Eliminates Circular Dependencies**: Floor moved from tables to core
3. **Multi-tenant Support**: Restaurant as root entity for data isolation
4. **Flexibility**: JSON fields for settings and features
5. **Extensibility**: Easy to add new fields without schema changes

## Next Steps

1. Update all modules to properly reference Restaurant model
2. Add restaurant_id to all tenant-specific models
3. Implement proper multi-tenant filtering in queries
4. Add restaurant context to authentication
5. Create admin APIs for restaurant management