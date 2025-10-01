# Codex Agent Instructions – AuraConnect

## 🏗 Project Context
- Project: **AuraConnect** – AI-driven restaurant management platform.
- Monorepo layout with multiple apps and shared packages.
- Primary dev path: `/Volumes/CodeMatrix/Projects/clones/auraconnectai`.

## 📂 Repository Structure
- `backend/` – FastAPI services, Alembic migrations under `backend/alembic/`
- `frontend/` – React (web)
- `mobile/` – React Native
- `design-system/` – shared UI primitives/tokens
- `customer-web/` – customer-facing web
- `docs/`, `scripts/`, `Makefile` – shared docs & tooling
- Tests:
  - `backend/tests/`
  - `frontend/src/__tests__/`
  - `mobile/__tests__/`
  - Cross-cutting E2E under `tests/e2e/`

## ⚙️ Build & Run
- Install toolchains:
  - `make install` (all)
  - `make install-backend`, `make install-frontend`, `make install-mobile`
- Run apps:
  - `make backend-run`
  - `make frontend-run`
  - `npm run ios` / `npm run android` (from `mobile/`)
- Infra:
  - `docker-compose up -d` or `make docker-up` (Postgres/Redis/etc.)
  - `make docker-down`

## 🧭 Tech & Patterns
- **Frontend:** React + TypeScript + Tailwind + Zustand
- **API data:** React Query
- **Backend:** FastAPI + Pydantic + SQLAlchemy + Alembic
- **Design System:** tokens + Tailwind; **no MUI** (don’t add Material UI)
- **Node/JS Runtime:** Volta-pinned **Node v22** (assume via global config)

## 🎨 Design Sources
- Follow **`UI_ARCHITECTURE_PLAN.md`** and **`UI_COMPONENT_SPECIFICATIONS.md`**
- Color, type, spacing tokens are source of truth in the design system
- Keep **light & dark** modes consistent

## 🧪 Testing
- Backend: **Pytest**; keep coverage stable or increasing (`--cov`)
- Frontend/Mobile: **Jest** colocated tests (`__tests__/` or `*.test.tsx`)
- E2E: **Playwright** under `tests/e2e/` (ensure Docker services up)
- With every feature/fix: **add or update tests**

## 🧹 Code Quality
- Python: PEP8; format with `black` + `isort` + `ruff`; types via `mypy`
- TS/JS: ESLint + Prettier; strongly typed props; avoid `any`
- Shell: POSIX-compatible; mark executable

## 🔐 API & Security
- Keep **OpenAPI** (`openapi.json`) in sync with endpoints
- Enforce **RBAC** in sensitive routes; add tests for permissions
- Avoid leaking secrets; respect `.gitignore`

## 🧾 Git & PR (project specifics)
- (Global rule already set: new GitHub issue → create & switch to a new branch:
  `feature/<ISSUE-ID>-<kebab-desc>`.)
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, etc.)
- Rebase on `main` before PR
- PR must include:
  - Linked **GitHub issue**
  - Summary of changes
  - Checklist of verifications
  - Tests evidence (logs/screenshots)
  - Any migration or breaking-change notes

## 🧠 Session Routine
- **On start:**  
  - Check `/status`  
  - Confirm current branch matches active GitHub issue  
  - Read relevant parts of `UI_ARCHITECTURE_PLAN.md` / `UI_COMPONENT_SPECIFICATIONS.md`
- **While working:**  
  - Keep diffs scoped (< ~150 lines) and focused  
  - Update or add tests alongside changes
- **Before end:**  
  - Run tests (`make test` or targeted)  
  - Summarize completed work + next steps  
  - If partial, leave `// TODO: continue here` markers

## 🔎 When in Doubt
- Prefer **small, iterative** changes with clear tests
- Ask for minimal stubs if required data/functions are missing—don’t refactor unrelated areas
- Treat “**git issue**” as **GitHub issue** (also set in global config)

---

## ✅ PR Checklist (paste into PR description)
- [ ] Linked GitHub issue: `<#>`  
- [ ] Scoped commits & conventional titles  
- [ ] Tests added/updated (unit/integration/E2E as applicable)  
- [ ] `make test` (or targeted tests) pass locally  
- [ ] OpenAPI updated (if API changed)  
- [ ] Screenshots/logs for UI changes  
- [ ] No stray console logs/secrets; follows Tailwind-only rule# Codex Agent Instructions – AuraConnect

## 🏗 Project Context
- Project: **AuraConnect** – AI-driven restaurant management platform.
- Monorepo layout with multiple apps and shared packages.
- Primary dev path: `/Volumes/CodeMatrix/Projects/clones/auraconnectai`.

## 📂 Repository Structure
- `backend/` – FastAPI services, Alembic migrations under `backend/alembic/`
- `frontend/` – React (web)
- `mobile/` – React Native
- `design-system/` – shared UI primitives/tokens
- `customer-web/` – customer-facing web
- `docs/`, `scripts/`, `Makefile` – shared docs & tooling
- Tests:
  - `backend/tests/`
  - `frontend/src/__tests__/`
  - `mobile/__tests__/`
  - Cross-cutting E2E under `tests/e2e/`

## ⚙️ Build & Run
- Install toolchains:
  - `make install` (all)
  - `make install-backend`, `make install-frontend`, `make install-mobile`
- Run apps:
  - `make backend-run`
  - `make frontend-run`
  - `npm run ios` / `npm run android` (from `mobile/`)
- Infra:
  - `docker-compose up -d` or `make docker-up` (Postgres/Redis/etc.)
  - `make docker-down`

## 🧭 Tech & Patterns
- **Frontend:** React + TypeScript + Tailwind + Zustand
- **API data:** React Query
- **Backend:** FastAPI + Pydantic + SQLAlchemy + Alembic
- **Design System:** tokens + Tailwind; **no MUI** (don’t add Material UI)
- **Node/JS Runtime:** Volta-pinned **Node v22** (assume via global config)

## 🎨 Design Sources
- Follow **`UI_ARCHITECTURE_PLAN.md`** and **`UI_COMPONENT_SPECIFICATIONS.md`**
- Color, type, spacing tokens are source of truth in the design system
- Keep **light & dark** modes consistent

## 🧪 Testing
- Backend: **Pytest**; keep coverage stable or increasing (`--cov`)
- Frontend/Mobile: **Jest** colocated tests (`__tests__/` or `*.test.tsx`)
- E2E: **Playwright** under `tests/e2e/` (ensure Docker services up)
- With every feature/fix: **add or update tests**

## 🧹 Code Quality
- Python: PEP8; format with `black` + `isort` + `ruff`; types via `mypy`
- TS/JS: ESLint + Prettier; strongly typed props; avoid `any`
- Shell: POSIX-compatible; mark executable

## 🔐 API & Security
- Keep **OpenAPI** (`openapi.json`) in sync with endpoints
- Enforce **RBAC** in sensitive routes; add tests for permissions
- Avoid leaking secrets; respect `.gitignore`

## 🧾 Git & PR (project specifics)
- (Global rule already set: new GitHub issue → create & switch to a new branch:
  `feature/<ISSUE-ID>-<kebab-desc>`.)
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, etc.)
- Rebase on `main` before PR
- PR must include:
  - Linked **GitHub issue**
  - Summary of changes
  - Checklist of verifications
  - Tests evidence (logs/screenshots)
  - Any migration or breaking-change notes

## 🧠 Session Routine
- **On start:**  
  - Check `/status`  
  - Confirm current branch matches active GitHub issue  
  - Read relevant parts of `UI_ARCHITECTURE_PLAN.md` / `UI_COMPONENT_SPECIFICATIONS.md`
- **While working:**  
  - Keep diffs scoped (< ~150 lines) and focused  
  - Update or add tests alongside changes
- **Before end:**  
  - Run tests (`make test` or targeted)  
  - Summarize completed work + next steps  
  - If partial, leave `// TODO: continue here` markers

## 🔎 When in Doubt
- Prefer **small, iterative** changes with clear tests
- Ask for minimal stubs if required data/functions are missing—don’t refactor unrelated areas
- Treat “**git issue**” as **GitHub issue** (also set in global config)

---

## ✅ PR Checklist (paste into PR description)
- [ ] Linked GitHub issue: `<#>`  
- [ ] Scoped commits & conventional titles  
- [ ] Tests added/updated (unit/integration/E2E as applicable)  
- [ ] `make test` (or targeted tests) pass locally  
- [ ] OpenAPI updated (if API changed)  
- [ ] Screenshots/logs for UI changes  
- [ ] No stray console logs/secrets; follows Tailwind-only rule