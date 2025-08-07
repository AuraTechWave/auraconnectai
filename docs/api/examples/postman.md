# Postman Collection

This page provides information about using the AuraConnect API with Postman.

## Download Collection

Download the official AuraConnect Postman collection:

[📥 Download AuraConnect API Collection](https://api.auraconnect.ai/postman/auraconnect-api.postman_collection.json)

## Import Collection

1. Open Postman
2. Click **Import** in the top left
3. Choose the downloaded collection file
4. The collection will appear in your Collections sidebar

## Environment Setup

### Create Environment

1. Click the **Environments** tab in Postman
2. Click **Create Environment**
3. Name it "AuraConnect Production" (or "AuraConnect Development")
4. Add the following variables:

| Variable | Type | Initial Value | Current Value |
|----------|------|---------------|---------------|
| `base_url` | default | `https://api.auraconnect.ai` | `https://api.auraconnect.ai` |
| `api_version` | default | `v1` | `v1` |
| `access_token` | secret | | |
| `refresh_token` | secret | | |
| `user_id` | default | | |
| `restaurant_id` | default | | |

### Environment Variables for Different Stages

#### Production Environment
```json
{
  "base_url": "https://api.auraconnect.ai",
  "api_version": "v1"
}
```

#### Staging Environment
```json
{
  "base_url": "https://api-staging.auraconnect.ai",
  "api_version": "v1"
}
```

#### Local Development
```json
{
  "base_url": "http://localhost:8000",
  "api_version": "v1"
}
```

## Collection Structure

The AuraConnect Postman collection is organized into folders:

```
📁 AuraConnect API
├── 📁 Authentication
│   ├── Login
│   ├── Logout
│   ├── Refresh Token
│   └── Get Current User
├── 📁 Orders
│   ├── Create Order
│   ├── List Orders
│   ├── Get Order
│   ├── Update Order
│   ├── Cancel Order
│   └── Complete Order
├── 📁 Menu
│   ├── List Menu Items
│   ├── Create Menu Item
│   ├── Update Menu Item
│   └── Delete Menu Item
├── 📁 Staff
│   ├── List Staff
│   ├── Create Staff Member
│   ├── Clock In/Out
│   └── Schedules
├── 📁 Inventory
│   ├── List Inventory
│   ├── Adjust Stock
│   └── Low Stock Report
├── 📁 Analytics
│   ├── Sales Report
│   ├── Revenue Analytics
│   └── Popular Items
└── 📁 Payments
    ├── Process Payment
    ├── Refund
    └── Payment History
```

## Authentication Flow

### 1. Login
Run the **Login** request in the Authentication folder:

```json
{
  "email": "admin@auraconnect.ai",
  "password": "your-password"
}
```

### 2. Automatic Token Storage
The collection includes a test script that automatically saves tokens:

```javascript
// This runs after login request
if (pm.response.code === 200) {
    const response = pm.response.json();
    pm.environment.set("access_token", response.access_token);
    pm.environment.set("refresh_token", response.refresh_token);
    pm.environment.set("user_id", response.user.id);
    pm.environment.set("restaurant_id", response.user.restaurant_id);
}
```

### 3. Token Usage
All authenticated requests automatically use the stored token:

```
Authorization: Bearer {{access_token}}
```

## Pre-request Scripts

### Automatic Token Refresh
The collection includes a pre-request script that checks token expiration:

```javascript
// Pre-request script for authenticated endpoints
const tokenExpiry = pm.environment.get("token_expiry");
const now = Date.now();

if (tokenExpiry && now > tokenExpiry) {
    // Token expired, refresh it
    pm.sendRequest({
        url: pm.environment.get("base_url") + "/api/v1/auth/refresh",
        method: 'POST',
        header: {
            'Content-Type': 'application/json'
        },
        body: {
            mode: 'raw',
            raw: JSON.stringify({
                refresh_token: pm.environment.get("refresh_token")
            })
        }
    }, function (err, response) {
        if (!err && response.code === 200) {
            const data = response.json();
            pm.environment.set("access_token", data.access_token);
            pm.environment.set("token_expiry", Date.now() + (data.expires_in * 1000));
        }
    });
}
```

## Common Requests

### Create Order Example
```json
{
  "order_type": "dine_in",
  "table_number": "{{table_number}}",
  "customer_id": {{customer_id}},
  "items": [
    {
      "menu_item_id": {{menu_item_id}},
      "quantity": 2,
      "modifiers": [
        {
          "modifier_id": 5,
          "quantity": 1
        }
      ],
      "special_instructions": "No onions please"
    }
  ],
  "notes": "Birthday celebration"
}
```

### Dynamic Variables
The collection uses dynamic variables for testing:

- `{{$randomInt}}` - Random integer
- `{{$randomEmail}}` - Random email
- `{{$randomFirstName}}` - Random first name
- `{{$timestamp}}` - Current timestamp

Example:
```json
{
  "first_name": "{{$randomFirstName}}",
  "email": "test-{{$timestamp}}@example.com",
  "phone": "+1-555-{{$randomInt}}"
}
```

## Testing

### Collection Tests
Each request includes tests to validate responses:

```javascript
// Example test for Create Order
pm.test("Status code is 201", function () {
    pm.response.to.have.status(201);
});

pm.test("Order has required fields", function () {
    const response = pm.response.json();
    pm.expect(response).to.have.property('id');
    pm.expect(response).to.have.property('order_number');
    pm.expect(response).to.have.property('status');
    pm.expect(response).to.have.property('total_amount');
});

// Save order ID for subsequent requests
if (pm.response.code === 201) {
    const response = pm.response.json();
    pm.collectionVariables.set("last_order_id", response.id);
}
```

### Running Tests
1. Click **Runner** in Postman
2. Select the AuraConnect collection
3. Choose environment
4. Configure iterations and delay
5. Click **Run AuraConnect API**

## Collection Variables

Common variables used across requests:

| Variable | Description | Example |
|----------|-------------|---------|
| `order_id` | Last created order ID | `1001` |
| `menu_item_id` | Test menu item | `10` |
| `customer_id` | Test customer | `123` |
| `employee_id` | Test employee | `1` |
| `table_number` | Test table | `12` |

## Workflows

### Complete Order Flow
1. **Login** → Get access token
2. **Create Customer** → Get customer ID
3. **List Menu Items** → Choose items
4. **Create Order** → Get order ID
5. **Process Payment** → Complete transaction
6. **Get Receipt** → Verify order

### Staff Shift Flow
1. **Login** (as staff)
2. **Clock In**
3. **Get Assigned Orders**
4. **Update Order Status**
5. **Clock Out**

## Tips and Tricks

### 1. Use Folders
Organize custom requests in folders:
```
📁 My Tests
├── 📁 Load Testing
├── 📁 Integration Tests
└── 📁 Bug Reproductions
```

### 2. Environment Switching
Quickly switch between environments using the environment dropdown.

### 3. Request History
Use the History tab to find and rerun previous requests.

### 4. Generate Code
Click **Code** to generate code snippets in various languages:
- cURL
- Python
- JavaScript
- PHP
- Ruby
- And more...

### 5. Monitor API
Set up monitors to run collections on a schedule:
1. Click **Monitors** tab
2. Create monitor from collection
3. Set schedule (hourly, daily, etc.)
4. Get alerts on failures

## Troubleshooting

### Authentication Issues
- Verify environment variables are set
- Check token expiration
- Ensure correct environment is selected

### Request Failures
- Check request URL includes `{{base_url}}`
- Verify required headers are included
- Check request body format (JSON)

### Variable Issues
- Use console to debug: `console.log(pm.environment.get("variable_name"))`
- Check variable scope (collection vs environment)
- Ensure variables are being set in tests

## Export/Import

### Export Collection
1. Right-click collection
2. Select **Export**
3. Choose Collection v2.1 format
4. Save file

### Share Collection
1. Click **Share** on collection
2. Choose sharing method:
   - Get public link
   - Invite team members
   - Export to file

## Additional Resources

- [Postman Learning Center](https://learning.postman.com/)
- [AuraConnect API Documentation](/api/)
- [API Status Page](https://status.auraconnect.ai/)
- [Developer Support](mailto:api-support@auraconnect.ai)