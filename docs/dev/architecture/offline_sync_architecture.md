# AuraConnect – Offline Sync for Mobile

## 1. 🌐 Overview & Goals

This module ensures AuraConnect mobile clients (React Native) can operate without internet connectivity and sync automatically once back online. It enables order taking, staff access, and limited reporting even when offline.

**Goals:**

- Cache essential data locally
- Enable offline-first order creation and shift tracking
- Sync queued changes on reconnection
- Handle conflicts, retries, and partial sync gracefully

---

## 2. 🔋 Offline Features Supported

- Order creation and updates (queue-based)
- Local staff login (with limited access tokens)
- Local shift logs and clock-ins
- Menu and price caching
- Partial reporting (based on local store)

---

## 3. 🧱 Architecture Overview

**Mobile Components:**

- `SyncManager` – Queues offline mutations
- `LocalDB` – Secure on-device SQLite/AsyncStorage store
- `ConnectionMonitor` – Detects connectivity
- `ConflictResolver` – Handles dual-source data issues

**Backend Components:**

- `SyncAPI` – Accepts batched or delayed updates
- `DeltaTracker` – Version control for records

```
[Mobile App] ─▶ [SyncManager] ─▶ [LocalDB] ←→ [UI]
                        │
                        ▼
             [ConnectionMonitor] → [SyncAPI] (when online)
                                      ▼
                             [DeltaTracker + DB]
```

---

## 4. 🔄 Sync Lifecycle

### Offline Order Flow:

1. User creates an order
2. SyncManager saves to LocalDB & queue
3. UI updates optimistically
4. When online, queued orders sent to SyncAPI
5. Server applies and returns confirmation or conflict

### Shift Log Flow:

1. Staff checks in (offline)
2. Entry stored locally
3. On reconnection, batched updates pushed

---

## 5. 📡 API Endpoints

### Sync

- `POST /sync/orders` – batch order sync
- `POST /sync/shifts` – batch shift updates
- `POST /sync/menu` – push cached delta (admin only)

### Conflict Resolution

- `POST /sync/conflict/resolve` – manual or rule-based resolution

---

## 6. 🗃️ Local & Server Schema

### Local Store (Mobile)

- `orders_offline`
- `staff_logs_offline`
- `menu_cache`

### Server Tables (same as main modules)

- Accept offline deltas with `source: mobile_offline`

---

## 7. 🛠️ Mobile Code Stub

```ts
// syncManager.ts (React Native)
const queue = [];
function saveOffline(order) {
  queue.push(order);
  AsyncStorage.setItem("offlineQueue", JSON.stringify(queue));
}

function trySync() {
  if (isOnline()) {
    const queued = JSON.parse(AsyncStorage.getItem("offlineQueue"));
    sendToSyncAPI(queued);
  }
}
```

---

## 8. 📘 Developer Notes

- Use React Native libraries like `NetInfo`, `AsyncStorage`, `SQLite`
- Conflict resolution rules must be clear (e.g., last-write-wins vs manual merge)
- Ensure secure storage of sensitive data (e.g., tokens, order info)
- Retry mechanism with exponential backoff recommended

---

## ✅ Summary

Offline Sync enables AuraConnect to function in unreliable network environments — critical for field operations, delivery zones, and rural venues. A robust sync system ensures a resilient user experience.

➡️ Final optional module coming up: **AI Customization Suite**

