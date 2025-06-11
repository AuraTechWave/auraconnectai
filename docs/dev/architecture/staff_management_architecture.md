# AuraConnect – Staff Management Module

## 1. 🎯 Overview & Goals

The Staff Management Module allows restaurants to efficiently onboard, manage, and monitor employees such as managers, chefs, servers, and delivery staff. It handles roles, shifts, permissions, profiles, and access control.

**Goals:**

- Onboard staff with custom roles
- Role-based access to AuraConnect modules
- Manage shift schedules and leaves
- Track performance and attendance
- Ensure compliance and audit readiness

---

## 2. 👥 Staff Roles & Permissions

### Supported Roles (Configurable):

- **Admin** – Full access
- **Manager** – Ops & team supervision
- **Chef / Kitchen Staff** – Kitchen-only interface
- **Server / FOH Staff** – Orders, customer service
- **Delivery Staff** – Delivery schedule, order status

### Role-Based Access Control (RBAC):

- Defined in the DB and enforced in middleware
- Access tokens embed role-based scopes

---

## 3. 🧱 Architecture Diagram

**Core Components:**

- `StaffService` (REST API layer)
- `AuthService` (with token & permission engine)
- `UserDB` (PostgreSQL or Supabase)
- `Scheduler` (manages shift tables)
- `NotificationService` (reminders, alerts)

```
[Frontend] ──▶ [StaffService API] ──▶ [UserDB]
                     │                     │
                     ▼                     ▼
             [AuthService]          [Scheduler]
                     │
              [NotificationService]
```

---

## 4. 🔁 Workflow Flowcharts

### Onboarding Flow:

1. Admin creates staff profile
2. Assigns role + shift schedule
3. System sends welcome email + app link
4. Staff logs in and updates profile

### Shift Scheduling Flow:

1. Manager creates weekly shift plan
2. Scheduler validates overlaps
3. Staff confirms availability
4. Finalized schedule notifies staff

---

## 5. 📡 API Endpoints (REST)

### Authentication

- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/logout`

### Staff Management

- `GET /staff` – list all staff
- `GET /staff/:id` – view profile
- `POST /staff` – add staff
- `PUT /staff/:id` – update profile
- `DELETE /staff/:id` – remove staff

### Shift & Roles

- `GET /shifts` – view schedule
- `POST /shifts` – create shifts
- `POST /roles` – create custom roles
- `GET /roles` – list all roles

---

## 6. 🗃️ Database Schema (PostgreSQL)

### Table: `users`

| id | name | email | role | is\_active | created\_at |
| -- | ---- | ----- | ---- | ---------- | ----------- |

### Table: `roles`

\| id | name | permissions (jsonb) |

### Table: `shifts`

\| id | user\_id | start\_time | end\_time | status |

---

## 7. 🛠️ Initial Code Stub (Optional)

```ts
// staff.service.ts (Node + Express)
app.post("/staff", authenticate, authorize("admin"), async (req, res) => {
  const staff = await db.insert("users", req.body);
  sendWelcomeEmail(staff.email);
  res.status(201).json(staff);
});
```

---

## 8. 📘 Developer Notes

- Middleware should enforce role-based access control (RBAC)
- Use JWT for session tokens with embedded scopes
- Scheduler should auto-adjust for public holidays (extendable logic)
- Notifications can be handled via Firebase or a queue system

---

## ✅ Summary

This module empowers restaurant operators to scale and secure their workforce operations with RBAC, shift management, and reliable onboarding. It’s critical for supporting access control across all other modules.

➡️ Next up: **Menu & Inventory System** (will be structured in a new focused chat)

