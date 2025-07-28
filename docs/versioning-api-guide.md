# Menu Versioning API Guide

## Overview

The Menu Versioning API provides comprehensive version control and audit trail capabilities for restaurant menu management. This guide covers all available endpoints, request/response formats, and usage examples.

## Base URL

```
https://your-domain.com/api/menu/versions
```

## Authentication

All endpoints require JWT authentication with appropriate RBAC permissions:

```http
Authorization: Bearer <your-jwt-token>
```

### Required Permissions

- `menu:read` - View versions and audit logs
- `menu:create` - Create new versions
- `menu:update` - Publish and rollback versions
- `menu:delete` - Delete draft versions
- `menu:manage_versions` - Advanced version management

## Endpoints

### 1. Version Management

#### Create Version

Creates a new menu version from the current active menu state.

```http
POST /menu/versions
```

**Request Body:**

```json
{
  "version_name": "Summer Menu 2025",
  "description": "Updated menu with seasonal items",
  "version_type": "manual",
  "include_inactive": false,
  "scheduled_publish_at": "2025-06-01T12:00:00Z"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version_name` | string | No | Human-readable name for the version |
| `description` | string | No | Detailed description of changes |
| `version_type` | enum | No | Type: `manual`, `scheduled`, `auto_save` (default: `manual`) |
| `include_inactive` | boolean | No | Include inactive items in snapshot (default: `false`) |
| `scheduled_publish_at` | datetime | No | Schedule automatic publishing |

**Response:**

```json
{
  "id": 123,
  "version_number": "v20250728-001",
  "version_name": "Summer Menu 2025",
  "description": "Updated menu with seasonal items",
  "version_type": "manual",
  "is_active": false,
  "is_published": false,
  "published_at": null,
  "scheduled_publish_at": "2025-06-01T12:00:00Z",
  "created_by": 1,
  "total_items": 45,
  "total_categories": 8,
  "total_modifiers": 23,
  "changes_summary": null,
  "parent_version_id": null,
  "created_at": "2025-01-28T10:30:00Z",
  "updated_at": "2025-01-28T10:30:00Z"
}
```

**Example:**

```bash
curl -X POST https://api.example.com/menu/versions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "version_name": "Weekend Special Menu",
    "description": "Added weekend brunch items",
    "version_type": "manual"
  }'
```

#### List Versions

Retrieves a paginated list of menu versions.

```http
GET /menu/versions
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `size` | integer | 20 | Items per page (max 100) |
| `version_type` | enum | all | Filter by version type |

**Response:**

```json
{
  "items": [
    {
      "id": 123,
      "version_number": "v20250728-001",
      "version_name": "Summer Menu 2025",
      "is_active": true,
      "is_published": true,
      "total_items": 45,
      "created_at": "2025-01-28T10:30:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "size": 20,
  "pages": 2
}
```

#### Get Version Details

Retrieves detailed information about a specific version including all related data.

```http
GET /menu/versions/{version_id}
```

**Response:**

```json
{
  "id": 123,
  "version_number": "v20250728-001",
  "version_name": "Summer Menu 2025",
  "description": "Updated menu with seasonal items",
  "version_type": "manual",
  "is_active": true,
  "is_published": true,
  "published_at": "2025-01-28T12:00:00Z",
  "created_by": 1,
  "total_items": 45,
  "total_categories": 8,
  "total_modifiers": 23,
  "categories": [
    {
      "id": 1,
      "original_category_id": 10,
      "name": "Appetizers",
      "description": "Small plates and starters",
      "display_order": 1,
      "is_active": true,
      "change_type": "create",
      "change_summary": "Added new appetizer category"
    }
  ],
  "items": [
    {
      "id": 1,
      "original_item_id": 25,
      "name": "Caesar Salad",
      "description": "Fresh romaine with caesar dressing",
      "price": 12.99,
      "category_id": 10,
      "is_active": true,
      "is_available": true,
      "change_type": "update",
      "change_summary": "Updated price from $11.99 to $12.99",
      "price_history": [
        {
          "price": 11.99,
          "date": "2025-01-20T00:00:00Z"
        },
        {
          "price": 12.99,
          "date": "2025-01-28T00:00:00Z"
        }
      ]
    }
  ],
  "modifiers": [],
  "audit_entries": [
    {
      "id": 1,
      "action": "create_version",
      "entity_type": "menu_version",
      "change_type": "create",
      "change_summary": "Created new version v20250728-001",
      "user_id": 1,
      "created_at": "2025-01-28T10:30:00Z"
    }
  ],
  "parent_version": null
}
```

#### Publish Version

Publishes a version, making it the active menu.

```http
POST /menu/versions/{version_id}/publish
```

**Request Body:**

```json
{
  "scheduled_at": "2025-06-01T12:00:00Z",
  "force": false
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scheduled_at` | datetime | No | Schedule publishing for future time |
| `force` | boolean | No | Force publish even if already published |

**Response:**

```json
{
  "id": 123,
  "version_number": "v20250728-001",
  "is_active": true,
  "is_published": true,
  "published_at": "2025-01-28T12:00:00Z"
}
```

#### Rollback Version

Rolls back to a previous version, creating a new version based on the target.

```http
POST /menu/versions/rollback
```

**Request Body:**

```json
{
  "target_version_id": 120,
  "create_backup": true,
  "rollback_reason": "Critical bug in current version"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target_version_id` | integer | Yes | ID of version to rollback to |
| `create_backup` | boolean | No | Create backup of current state (default: `true`) |
| `rollback_reason` | string | Yes | Reason for rollback (required for audit) |

**Response:**

```json
{
  "id": 124,
  "version_number": "r20250728-001",
  "version_name": "Rollback to v20250726-003",
  "description": "Rollback to version v20250726-003. Reason: Critical bug in current version",
  "version_type": "rollback",
  "is_active": true,
  "is_published": true,
  "parent_version_id": 120,
  "created_at": "2025-01-28T14:00:00Z"
}
```

#### Delete Version

Soft deletes a draft version (cannot delete published or active versions).

```http
DELETE /menu/versions/{version_id}
```

**Response:**

```json
{
  "message": "Version deleted successfully"
}
```

### 2. Version Comparison

#### Compare Versions

Compares two versions and returns detailed differences.

```http
POST /menu/versions/compare
```

**Request Body:**

```json
{
  "from_version_id": 120,
  "to_version_id": 123,
  "include_details": true,
  "entity_types": ["items", "categories"]
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from_version_id` | integer | Yes | Source version for comparison |
| `to_version_id` | integer | Yes | Target version for comparison |
| `include_details` | boolean | No | Include detailed field changes (default: `true`) |
| `entity_types` | array | No | Limit comparison to specific entity types |

**Response:**

```json
{
  "from_version_id": 120,
  "to_version_id": 123,
  "from_version_number": "v20250726-003",
  "to_version_number": "v20250728-001",
  "summary": {
    "created": 5,
    "updated": 12,
    "deleted": 2,
    "price_changed": 8
  },
  "categories": [
    {
      "entity_type": "category",
      "entity_id": 10,
      "entity_name": "Appetizers",
      "change_type": "update",
      "field_changes": [
        {
          "field_name": "description",
          "old_value": "Small plates",
          "new_value": "Small plates and starters",
          "change_type": "modified"
        }
      ]
    }
  ],
  "items": [
    {
      "entity_type": "item",
      "entity_id": 25,
      "entity_name": "Caesar Salad",
      "change_type": "update",
      "field_changes": [
        {
          "field_name": "price",
          "old_value": 11.99,
          "new_value": 12.99,
          "change_type": "modified"
        }
      ]
    }
  ],
  "modifiers": [],
  "generated_at": "2025-01-28T15:00:00Z"
}
```

### 3. Audit Trail

#### Get Audit Logs

Retrieves paginated audit logs for menu changes.

```http
GET /menu/versions/audit/logs
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `version_id` | integer | null | Filter by specific version |
| `page` | integer | 1 | Page number |
| `size` | integer | 50 | Items per page (max 200) |
| `entity_type` | string | null | Filter by entity type |
| `change_type` | string | null | Filter by change type |
| `user_id` | integer | null | Filter by user |
| `start_date` | datetime | null | Filter from date |
| `end_date` | datetime | null | Filter to date |

**Response:**

```json
{
  "items": [
    {
      "id": 456,
      "menu_version_id": 123,
      "action": "update_item_price",
      "entity_type": "menu_item",
      "entity_id": 25,
      "entity_name": "Caesar Salad",
      "change_type": "price_change",
      "old_values": {
        "price": 11.99
      },
      "new_values": {
        "price": 12.99
      },
      "changed_fields": ["price"],
      "change_summary": "Price updated from $11.99 to $12.99",
      "user_id": 1,
      "user_role": "manager",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "session_id": "sess_123abc",
      "batch_id": "batch_789xyz",
      "tags": ["price_increase", "weekend_menu"],
      "created_at": "2025-01-28T11:15:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "size": 50,
  "pages": 3
}
```

### 4. Statistics and Analytics

#### Get Version Statistics

Retrieves comprehensive statistics about versions and changes.

```http
GET /menu/versions/stats
```

**Response:**

```json
{
  "total_versions": 25,
  "active_version": {
    "id": 123,
    "version_number": "v20250728-001",
    "version_name": "Summer Menu 2025",
    "published_at": "2025-01-28T12:00:00Z"
  },
  "published_versions": 18,
  "draft_versions": 7,
  "scheduled_versions": 2,
  "latest_change": "2025-01-28T11:15:00Z",
  "total_changes_today": 15,
  "most_changed_items": [
    {
      "name": "Caesar Salad",
      "changes": 8,
      "last_changed": "2025-01-28T11:15:00Z"
    },
    {
      "name": "Margherita Pizza",
      "changes": 6,
      "last_changed": "2025-01-28T10:30:00Z"
    }
  ]
}
```

### 5. Bulk Operations

#### Bulk Change

Applies bulk changes to menu entities and creates version if significant.

```http
POST /menu/versions/bulk-change
```

**Request Body:**

```json
{
  "entity_type": "item",
  "entity_ids": [25, 26, 27, 28],
  "changes": {
    "is_available": false
  },
  "change_reason": "Temporarily unavailable due to supply shortage"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_type` | enum | Yes | Type: `item`, `category`, `modifier` |
| `entity_ids` | array | Yes | List of entity IDs to update |
| `changes` | object | Yes | Changes to apply |
| `change_reason` | string | Yes | Reason for bulk change |

**Response:**

```json
{
  "updated": 4,
  "errors": [],
  "version_created": true,
  "version_id": 124,
  "change_summary": "Bulk updated 4 items: set availability to false"
}
```

### 6. Export and Import

#### Export Version

Exports version data in various formats.

```http
POST /menu/versions/{version_id}/export
```

**Request Body:**

```json
{
  "format": "json",
  "include_audit_trail": true,
  "include_inactive": false
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format` | enum | No | Format: `json`, `csv`, `excel` (default: `json`) |
| `include_audit_trail` | boolean | No | Include audit trail data |
| `include_inactive` | boolean | No | Include inactive entities |

**Response:**

```json
{
  "version": {
    "id": 123,
    "version_number": "v20250728-001",
    "categories": [...],
    "items": [...],
    "modifiers": [...]
  },
  "exported_at": "2025-01-28T16:00:00Z",
  "exported_by": "user@example.com",
  "format": "json"
}
```

#### Import Version

Imports menu data and optionally creates a new version.

```http
POST /menu/versions/import
```

**Request Body:**

```json
{
  "import_data": {
    "categories": [...],
    "items": [...],
    "modifiers": [...]
  },
  "import_mode": "merge",
  "create_version": true,
  "version_name": "Imported Menu Data"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `import_data` | object | Yes | Menu data to import |
| `import_mode` | enum | No | Mode: `merge`, `replace`, `append` (default: `merge`) |
| `create_version` | boolean | No | Create version after import (default: `true`) |
| `version_name` | string | No | Name for created version |

### 7. Advanced Operations

#### Preview Version

Previews what the menu would look like with a specific version active.

```http
GET /menu/versions/{version_id}/preview
```

**Response:**

```json
{
  "version_info": {
    "id": 123,
    "version_number": "v20250728-001",
    "version_name": "Summer Menu 2025"
  },
  "categories": 8,
  "items": 45,
  "modifiers": 23,
  "preview_generated_at": "2025-01-28T16:30:00Z",
  "differences_from_current": {
    "new_items": 5,
    "updated_items": 12,
    "removed_items": 2
  }
}
```

#### Get Change Buffer Status

Gets the current status of the auto-versioning change buffer.

```http
GET /menu/versions/buffer-status
```

**Response:**

```json
{
  "buffer_size": 7,
  "threshold": 10,
  "enabled": true,
  "recent_changes": [
    {
      "entity_type": "menu_item",
      "change_type": "update",
      "entity_id": 25,
      "timestamp": "2025-01-28T16:25:00Z"
    }
  ]
}
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "VERSION_NOT_FOUND",
  "timestamp": "2025-01-28T16:00:00Z",
  "path": "/menu/versions/999"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `VERSION_NOT_FOUND` | 404 | Version does not exist |
| `INSUFFICIENT_PERMISSIONS` | 403 | User lacks required permissions |
| `VERSION_ALREADY_PUBLISHED` | 400 | Attempting to modify published version |
| `INVALID_VERSION_STATE` | 400 | Version in invalid state for operation |
| `COMPARISON_FAILED` | 500 | Version comparison could not be generated |
| `ROLLBACK_FORBIDDEN` | 400 | Cannot rollback to specified version |

## Rate Limiting

API endpoints are rate-limited to prevent abuse:

- **Version Creation**: 10 requests per minute per user
- **Bulk Operations**: 5 requests per minute per user
- **General Queries**: 100 requests per minute per user

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1643723400
```

## Webhooks

Configure webhooks to receive notifications about version events:

### Webhook Events

- `version.created` - New version created
- `version.published` - Version published
- `version.rollback` - Version rollback performed
- `audit.critical_change` - Critical change detected

### Webhook Payload

```json
{
  "event": "version.published",
  "timestamp": "2025-01-28T12:00:00Z",
  "data": {
    "version_id": 123,
    "version_number": "v20250728-001",
    "user_id": 1,
    "changes_summary": {
      "total_changes": 15,
      "critical_changes": 3
    }
  }
}
```

## SDK Examples

### JavaScript/TypeScript

```typescript
import { MenuVersioningAPI } from '@auraconnect/menu-versioning';

const api = new MenuVersioningAPI({
  baseURL: 'https://api.example.com',
  apiKey: 'your-api-key'
});

// Create a new version
const version = await api.createVersion({
  version_name: 'Summer Menu 2025',
  description: 'Updated seasonal menu',
  version_type: 'manual'
});

// Compare versions
const comparison = await api.compareVersions({
  from_version_id: 120,
  to_version_id: 123,
  include_details: true
});

// Get audit logs
const auditLogs = await api.getAuditLogs({
  page: 1,
  size: 50,
  entity_type: 'menu_item'
});
```

### Python

```python
from auraconnect.menu_versioning import MenuVersioningClient

client = MenuVersioningClient(
    base_url='https://api.example.com',
    api_key='your-api-key'
)

# Create version
version = client.create_version(
    version_name='Summer Menu 2025',
    description='Updated seasonal menu',
    version_type='manual'
)

# Publish version
client.publish_version(version.id, force=False)

# Get version details
details = client.get_version_details(version.id)
```

This API guide provides comprehensive documentation for integrating with the Menu Versioning system. For additional support or advanced use cases, please refer to the architecture documentation or contact the development team.