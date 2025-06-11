# AuraConnect – Menu & Inventory System

## 1. 🍽️ Overview & Goals

This module manages the restaurant’s menu offerings and kitchen inventory. It allows for real-time menu updates, stock-level tracking, ingredient-level costing, and inventory alerting.

**Goals:**

- Centralized menu and modifier management
- Sync menu with POS and ordering platforms
- Real-time inventory tracking with usage logs
- Auto restock suggestions and vendor integration

---

## 2. 📋 Features

- CRUD for menus, categories, and items
- Menu modifiers (e.g., spice level, add-ons)
- Ingredient-based recipe linkage
- Inventory depletion per sale
- Restock alerts and reorder logs

---

## 3. 🧱 Architecture Overview

**Core Services:**

- `MenuService` – Menu & modifier APIs
- `InventoryService` – Stock, vendors, tracking
- `SyncService` – POS/ordering platform sync
- `NotificationService` – Restock alerts
- `DB` – PostgreSQL or Supabase

```
[Frontend] ──▶ [MenuService] ──▶ [MenuDB]
                     │
                     ▼
              [InventoryService] ──▶ [InventoryDB]
                     │                    │
                     ▼                    ▼
              [NotificationService]  [SyncService]
```

---

## 4. 🔁 Workflow Flowcharts

### Inventory Usage Flow:

1. Customer places an order
2. System maps order to ingredients
3. InventoryService deducts quantities
4. If below threshold → Notification triggers

### Menu Update Flow:

1. Admin updates item or pricing
2. Change stored in MenuDB
3. SyncService pushes to connected platforms

---

## 5. 📡 API Endpoints (REST)

### Menu Management

- `GET /menu` – all items
- `POST /menu` – create item
- `PUT /menu/:id` – update item
- `DELETE /menu/:id`

### Modifiers

- `GET /modifiers`
- `POST /modifiers`

### Inventory

- `GET /stock`
- `POST /stock`
- `PUT /stock/:id`
- `GET /vendors`
- `POST /vendors`

---

## 6. 🗃️ Database Schema (PostgreSQL)

### Table: `menu_items`

\| id | name | price | category | ingredients (jsonb) |

### Table: `inventory`

\| id | item\_name | quantity | unit | threshold |

### Table: `modifiers`

\| id | name | type | values (jsonb) |

### Table: `vendors`

\| id | name | contact | items\_supplied (jsonb) |

---

## 7. 🛠️ Initial Code Stub

```ts
// inventory.service.ts
app.post("/stock", authenticate, authorize("manager"), async (req, res) => {
  const item = await db.insert("inventory", req.body);
  res.status(201).json(item);
});
```

---

## 8. 📘 Developer Notes

- Modifiers should be stored in a normalized form for flexible combinations
- Use `jsonb` for dynamic ingredient lists
- `SyncService` may use webhooks or polling depending on 3rd-party integrations
- Alerts can integrate with email, SMS, or Slack

---

## ✅ Summary

This module is the backbone for both operations and experience — linking customer-facing menus with kitchen and vendor logistics. It’s key to enabling real-time POS sync, accurate costing, and automated supply management.

➡️ Next up: **Order Management (FOH + BOH)**

