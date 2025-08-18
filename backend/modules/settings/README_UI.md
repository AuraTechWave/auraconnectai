# Settings Configuration Interface

This module provides a comprehensive settings management UI with validation, bulk operations, and preset configurations.

## Features

### 1. Settings Dashboard
- Organized by categories and sections
- Real-time validation
- Unsaved changes tracking
- Restart requirements notification
- Advanced settings toggle

### 2. Validation System
- Type validation
- Custom validation rules
- Dependency checking
- Conflict detection
- Real-time feedback

### 3. Bulk Operations
- Update multiple settings atomically
- Validate before saving
- Rollback on failure
- Batch reset to defaults
- Import/export configurations

### 4. Preset Configurations
- Quick Service
- Fine Dining
- Casual Dining
- Takeout & Delivery
- Bar & Lounge

### 5. Feature Flags
- Enable/disable features
- Rollout percentages
- User/restaurant targeting
- Time-based activation

## API Endpoints

### Dashboard & Sections

#### `GET /api/v1/settings-ui/dashboard`
Get complete settings dashboard with UI metadata.

**Query Parameters:**
- `scope`: Setting scope (system, restaurant, location, user)
- `restaurant_id`: Restaurant ID (optional)
- `include_definitions`: Include setting definitions (default: true)
- `include_history`: Include change history (default: false)

**Response:**
```json
{
  "categories": [
    {
      "key": "general",
      "label": "General",
      "icon": "settings",
      "sections": [...],
      "total_settings": 15,
      "modified_count": 3
    }
  ],
  "sections": [
    {
      "id": "restaurant_info",
      "name": "Restaurant Information",
      "settings": [
        {
          "key": "restaurant_name",
          "label": "Restaurant Name",
          "value": "My Restaurant",
          "field_type": "text",
          "is_required": true,
          "validation_rules": {"maxLength": 100}
        }
      ]
    }
  ],
  "has_unsaved_changes": false,
  "requires_restart": [],
  "can_edit": true
}
```

#### `GET /api/v1/settings-ui/sections`
Get settings organized by sections/groups.

### Validation

#### `POST /api/v1/settings-ui/validate`
Validate settings before saving.

**Request Body:**
```json
{
  "tax_rate": 8.5,
  "order_timeout_minutes": 60
}
```

**Response:**
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": [],
  "dependencies_met": true,
  "conflicts_detected": []
}
```

### Bulk Operations

#### `POST /api/v1/settings-ui/bulk-update`
Update multiple settings in a single transaction.

**Request Body:**
```json
{
  "settings": [
    {
      "key": "tax_rate",
      "value": 9.0
    }
  ],
  "scope": "restaurant",
  "validate_only": false,
  "reason": "Tax rate increase"
}
```

#### `POST /api/v1/settings-ui/reset`
Reset settings to defaults.

**Request Body:**
```json
{
  "scope": "restaurant",
  "category": "general",
  "confirm": true
}
```

### Import/Export

#### `POST /api/v1/settings-ui/export`
Export settings to JSON.

**Request Body:**
```json
{
  "scope": "restaurant",
  "categories": ["general", "operations"],
  "include_sensitive": false,
  "format": "json"
}
```

#### `POST /api/v1/settings-ui/import`
Import settings from JSON.

**Request Body:**
```json
{
  "data": {...},
  "scope": "restaurant",
  "merge_strategy": "override",
  "validate_only": true
}
```

### Presets

#### `POST /api/v1/settings-ui/apply-preset/{preset_name}`
Apply a predefined configuration preset.

**Available Presets:**
- `quick_service`: Fast food/quick service optimization
- `fine_dining`: Upscale dining experience
- `casual_dining`: Balanced casual restaurant
- `takeout_focused`: Takeout/delivery optimization
- `bar_lounge`: Bar and lounge settings

### Search & Comparison

#### `POST /api/v1/settings-ui/search`
Search settings by key, label, or description.

#### `GET /api/v1/settings-ui/compare/{template_id}`
Compare current settings with a template.

### Metadata

#### `GET /api/v1/settings-ui/metadata`
Get UI metadata including categories, field types, and permissions.

## Setting Categories

### General
- Restaurant Information
- Business Hours
- Localization

### Operations
- Order Management
- Table Management
- Kitchen Operations

### Payment
- Payment Processing
- Tax Configuration
- Tip Management

### Notifications
- Customer Notifications
- Staff Notifications
- Alert Preferences

### Security
- Access Control
- Audit & Logging
- Compliance

### Features
- Feature Toggles
- Advanced Features
- Integrations

## Field Types

The UI supports various field types:
- `text`: Single-line text input
- `number`: Numeric input with validation
- `toggle`: Boolean on/off switch
- `select`: Dropdown selection
- `multiselect`: Multiple selection
- `textarea`: Multi-line text
- `json`: JSON editor
- `date`/`time`/`datetime`: Date/time pickers
- `currency`: Currency input
- `percentage`: Percentage input
- `password`: Secure password field

## Validation Rules

Settings support various validation rules:
```json
{
  "min": 0,
  "max": 100,
  "minLength": 3,
  "maxLength": 50,
  "pattern": "^[A-Z][0-9]+$",
  "required": true,
  "email": true,
  "url": true
}
```

## Security

- Role-based access control
- Audit logging for all changes
- Sensitive value encryption
- Permission checks per scope
- IP-based restrictions for API keys

## Best Practices

1. **Validation First**: Always validate before saving
2. **Bulk Updates**: Use bulk operations for multiple changes
3. **Audit Trail**: Include reasons for changes
4. **Restart Awareness**: Check for settings requiring restart
5. **Preset Usage**: Start with presets and customize

## Example Usage

### React Component Example
```jsx
const SettingsDashboard = () => {
  const [settings, setSettings] = useState({});
  const [errors, setErrors] = useState({});
  
  const validateSettings = async (changes) => {
    const response = await fetch('/api/v1/settings-ui/validate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(changes)
    });
    
    const result = await response.json();
    setErrors(result.errors);
    return result.is_valid;
  };
  
  const saveSettings = async () => {
    const response = await fetch('/api/v1/settings-ui/bulk-update', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        settings: Object.entries(settings).map(([key, value]) => ({
          key,
          value
        })),
        scope: 'restaurant',
        reason: 'Settings updated via UI'
      })
    });
    
    const result = await response.json();
    if (result.success) {
      toast.success('Settings saved successfully');
      if (result.requires_restart.length > 0) {
        toast.warning('Some settings require a restart to take effect');
      }
    }
  };
  
  return (
    <SettingsForm
      settings={settings}
      errors={errors}
      onChange={validateSettings}
      onSave={saveSettings}
    />
  );
};
```

## Migration Guide

If migrating from an older settings system:

1. Export existing settings
2. Map to new schema format
3. Validate using the validation endpoint
4. Import with merge strategy
5. Verify and test

## Performance Considerations

- Settings are cached after first load
- Bulk operations are transactional
- Validation is performed client-side first
- WebSocket updates for real-time sync
- Lazy loading for advanced settings