# AuraConnect – Order Management (FOH + BOH)

## 1. 🧾 Overview & Goals

This module facilitates seamless order flow from Front of House (FOH) to Back of House (BOH). It ensures real-time updates, status tracking, and task routing between customers, servers, kitchen staff, and delivery.

**Goals:**

- Enable order capture across dine-in, takeout, delivery
- Sync FOH terminals with kitchen displays
- Track order lifecycle: pending → in kitchen → ready → served
- Route tasks based on roles and stations (e.g. grill, fry, bar)

---

## 2. 📋 Features

- Multi-source order intake (POS, kiosk, QR, mobile)
- Status pipeline with timestamps
- Item routing to respective kitchen stations
- Real-time updates for FOH staff
- Delayed prep alerts and reminders

---

## 3. 🧱 Architecture Overview

**Core Services:**

- `OrderService` – Captures and tracks orders
- `RoutingEngine` – Distributes order items to stations
- `KitchenDisplayService` – Push updates to BOH UI
- `NotificationService` – Delays, readiness pings
- `AuditLogger` – For compliance & replay

```
[Customer UI / POS] ──▶ [OrderService] ──▶ [OrderDB]
                                │
                                ▼
                      [RoutingEngine] ──▶ [KitchenDisplayService]
                                │                 ▲
                                ▼                 │
                     [NotificationService]  [BOH Staff Interface]
```

---

## 4. 🔄 Workflow Flowcharts

### Order Lifecycle:

1. Order received (QR/app/POS)
2. Items parsed and assigned to stations
3. BOH sees item queue on their KDS (Kitchen Display System)
4. Staff marks item as “In Progress” → “Ready”
5. FOH notified → Delivered → Marked complete

---

## 5. 📡 API Endpoints (REST)

### Order APIs

- `POST /orders` – create order
- `GET /orders` – list all
- `GET /orders/:id` – fetch order
- `PUT /orders/:id/status` – update status

### Routing & Status

- `POST /route` – reroute item to station
- `GET /stations/:id/queue` – current kitchen queue

---

## 6. 🗃️ Database Schema (PostgreSQL)

### Table: `orders`

\| id | table\_no | customer\_id | status | created\_at |

### Table: `order_items`

\| id | order\_id | item\_name | station | status | started\_at | completed\_at |

### Table: `stations`

\| id | name | staff\_id |

---

## 7. 🛠️ Code Stub

```ts
// order.service.ts
app.post("/orders", authenticate, async (req, res) => {
  const order = await db.insert("orders", req.body);
  routeItemsToStations(order);
  res.status(201).json(order);
});
```

---

## 8. 📘 Developer Notes

- WebSockets recommended for real-time updates to BOH and FOH
- RoutingEngine logic must support custom rules (e.g. vegetarian-only stations)
- Audit logs help with tracing issues and delays
- Design for performance under kitchen load (use Redis queues or batching)

---

## ✅ Summary

This module connects the guest-facing experience with BOH execution. A high-performing order management system is critical to fast service, reduced errors, and streamlined kitchen operations.

➡️ Next up: **Customer & Loyalty Module**

