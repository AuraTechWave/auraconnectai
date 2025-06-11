# ⚙️ Phase 3 – Core Backend Development

### 📅 Duration: 2–3 Weeks  
**Goal**: Build the complete backend foundation using FastAPI. Implement the database, APIs, and integrations.

---

## 🗓️ Sprint Plan

| Day(s) | Task | Deliverable |
|--------|------|-------------|
| Day 1–2 | Set up FastAPI project structure + Docker | Dev server ready |
| Day 3–4 | Define DB schema (Users, Tables, Menu, Orders) | SQLAlchemy models |
| Day 5–6 | Implement menu endpoints | `GET /menu`, `GET /menu/{id}` |
| Day 7–8 | Reservation API + conflict checking | `POST /reservations` |
| Day 9–10 | Orders CRUD endpoints | `POST /orders`, `GET /orders/{id}` |
| Day 11–12 | Staff roles + dashboard endpoints | `GET /staff/tasks`, `PUT /staff/assign` |
| Day 13–14 | AI Event API + WebSocket hook | `/events/agent`, `WS /agent-live` |
| Day 15–16 | Auth with JWT + onboarding | `POST /register`, `POST /login` |
| Day 17–18 | Middleware: Logging, CORS, rate-limiting | Middleware added |
| Day 19–21 | Testing + Swagger validation | Unit tests + `/docs` complete |

---

## 📦 Deliverables

- ✅ Dockerized FastAPI backend
- ✅ REST API: Menu, Reservations, Orders, Staff
- ✅ PostgreSQL schema + Alembic
- ✅ Auth system (JWT)
- ✅ WebSocket + AI Agent stub
- ✅ Unit tests + Swagger docs
- ✅ OpenAPI JSON file

---

## 📁 Suggested Project Layout

```
/backend
  ├── app/
  │   ├── main.py
  │   ├── api/
  │   │   ├── routes/
  │   │   └── deps.py
  │   ├── core/
  │   │   ├── config.py
  │   ├── db/
  │   │   ├── models.py
  │   │   └── base.py
  │   ├── schemas/
  │   ├── services/
  │   └── events/
  ├── tests/
  ├── alembic/
  └── Dockerfile
```

---

## 💡 Notes

- Use PostgreSQL (prod), SQLite (dev optional)
- Design for future event-based integrations
- Env support for Twilio, Firebase, Stripe
