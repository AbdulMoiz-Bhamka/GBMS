# GBMS — Complete Code Understanding Guide

> **What this is:** A verified walkthrough of the *actual* GBMS (Garment Business Management System) codebase from `GBMS.zip`: architecture, files, modules, flows, database, security, debugging, API reference and a teaching plan.
>
> **Rules followed:** No code was modified. Nothing here describes a feature that does not exist in your files. Where something could not be confirmed, it is labelled.

**Labels used throughout**

| Label | Meaning |
|---|---|
| **[V]** | Verified directly in your source files |
| **[I]** | Reasonable inference (logic follows from the code, but it was not run or observed) |
| **[R]** | Recommendation / improvement idea (not an existing feature) |

## Table of contents

1. [Scope and limitations](#1-scope-and-limitations)
2. [Architecture overview](#2-architecture-overview)
3. [Folder structure and file responsibilities](#3-folder-structure-and-file-responsibilities)
4. [Module dependency maps](#4-module-dependency-maps)
5. [Setup / run order](#5-setup--run-order)
6. [Module-by-module explanation](#6-module-by-module-explanation)
7. [End-to-end user journeys](#7-end-to-end-user-journeys)
8. [How data is shared between modules](#8-how-data-is-shared-between-modules)
9. [Database and SQL](#9-database-and-sql)
10. [Authentication, authorization and company isolation](#10-authentication-authorization-and-company-isolation)
11. [Security observations](#11-security-observations)
12. [Debugging guide](#12-debugging-guide)
13. [API endpoint reference](#13-api-endpoint-reference)
14. [Known incomplete features, duplicates and risks](#14-known-incomplete-features-duplicates-and-risks)
15. [Teaching plan and Lesson 1](#15-teaching-plan-and-lesson-1)

---

## 1. Scope and limitations

**Files read [V]:** all backend `.py` files, both `.sql` scripts, all frontend `src/` source files, `package.json`, `vite.config.js`, `index.html`, `requirements.txt`, `.env.example`, `.gitignore` files, the test file outline, and the `.env` / `.env.local` **key names** (values were intentionally not read or printed).

**Could not fully inspect:**

- `React (FrontEnd)/GBMS/GBMSunderstanding.md` — only the first lines were read; this guide does **not** rely on it.
- Binary/generated files: `.vs/.ssms_suo`, `.pnpm-store/v11/index.db`, `dist/` bundles, images, `package-lock.json`.
- `App.css` / `index.css` — styling only, not relevant to logic.
- Tests were read by outline only and **were not run**.
- The live SQL Server database was **not** reachable; table structure comes from the `.sql` scripts. The real database could differ if it was changed manually.

**Security note:** the zip includes `FastAPI (BackEnd)/.env` and `React (FrontEnd)/GBMS/.env.local`. If the zip is shared anywhere, rotate the JWT secret and database password first.

---

## 2. Architecture overview

### 2.1 What GBMS does today [V]

GBMS is a **multi-company (multi-tenant) platform**:

- A platform-level **SUPER_ADMIN** logs in, creates **companies**, and creates **login accounts** for each company.
- Company staff (**COMPANY_ADMIN**, **SUB_ADMIN**, **INVENTORY_USER**) log in and manage that company's **product catalogue** (categories, products, units of measure, reorder levels).
- Everything else on the sidebar (Production, Purchasing, Sales, Employees, Finance, Assets, Reports, Settings) is a **"Coming soon" placeholder** with no backend or page behind it.

### 2.2 Technology stack (verified)

| Layer | Technology [V] |
|---|---|
| Frontend | React 19, Vite, React Router v7, Tailwind CSS v4 + DaisyUI, lucide-react icons, React Compiler (Babel preset) |
| Backend | Python, FastAPI, Uvicorn, Pydantic (comes with FastAPI) |
| Database | Microsoft SQL Server via `pyodbc` — **raw SQL, no ORM** |
| Auth | JWT via PyJWT (HS256 by default), password hashing via `argon2-cffi` (`PasswordHasher`) |
| API style | REST/JSON under `/api/v1` |

### 2.3 Responsibilities of each layer

| Layer | Responsible for | NOT responsible for |
|---|---|---|
| **React (browser)** | Screens, forms, holding the session in memory, hiding menu items, calling the API | Security. Anything hidden in the UI can still be called directly with a tool like curl. |
| **FastAPI (server)** | Validating input, verifying the JWT, loading the user's role/company from the DB on every request, permission checks, running SQL, shaping JSON | Rendering UI |
| **SQL Server** | Storing data; enforcing uniqueness, foreign keys, check constraints, and a trigger on role/company rules | Knowing who is logged in |

### 2.4 How the layers communicate

```
Browser (React, :5173)
   │  fetch('/api/v1/...') + header  Authorization: Bearer <JWT>
   ▼
Vite dev server (:5173)  ── proxy /api and /health ──►  FastAPI (Uvicorn, 127.0.0.1:8000)
                                                            │
                                                            │  pyodbc connection (per request)
                                                            ▼
                                                       SQL Server (database GBMS)
```

In dev the browser only ever talks to port 5173; Vite forwards `/api` and `/health` to port 8000 (`vite.config.js`, `server.proxy`). [V]

### 2.5 Real request flow

```
User action
 → React page component (e.g. InventoryPage)
 → service file (inventoryService.js)
 → apiRequest() in authService.js  (adds Bearer token, calls fetch)
 → FastAPI router function
 → Pydantic schema validates the body
 → Depends(require_company_user)
      → Depends(get_current_user)
           → decode JWT  → user_id
           → DB lookup of user + role + company status
      → role check
 → service.py  (business rules, transactions, error mapping)
 → repository.py (parameterised SQL)
 → SQL Server
 → rows → dict (serialize_*) → JSON response
 → apiRequest() returns parsed JSON (or throws Error with server message)
 → page calls setState → React re-renders
```

**Difference from the generic example:** there is no separate frontend "API service" class and no global Axios-style interceptor — a single function `apiRequest()` is the shared HTTP client, and it lives inside `authService.js`. [V]

### 2.6 Company data isolation [V]

Isolation is implemented in the **backend**, not the frontend:

1. The JWT contains only the **user ID** (`sub`), never a company ID.
2. On each request the backend reloads the user from SQL Server, including `CompanyID` and company status.
3. Inventory routes pass `user["company_id"]` (from the DB lookup) to services — the client **cannot** send a company ID. Request schemas use `extra="forbid"`, so an extra `company_id` field in a body is rejected.
4. Every inventory SQL query contains `WHERE CompanyID = ?` (or joins on `CompanyID`).
5. The database adds a second line of defence: a composite foreign key `(CompanyID, CategoryID)` makes it impossible for a product to reference another company's category.

---

## 3. Folder structure and file responsibilities

### 3.1 Actual structure [V]

```
GBMS/
├── .gitignore
├── FastAPI (BackEnd)/
│   ├── main.py                         compatibility shim → re-exports app.main:app
│   ├── seed_admin.py                   CLI: create first SUPER_ADMIN
│   ├── requirements.txt
│   ├── .env / .env.example / .gitignore
│   ├── tests/
│   │   └── test_company_inventory.py   unittest with fake DB cursors
│   └── app/
│       ├── main.py                     REAL entry point (app, CORS, routers)
│       ├── core/
│       │   ├── config.py               .env loading, settings, regex patterns
│       │   ├── security.py             JWT + Argon2 helpers
│       │   └── validation.py           shared input normalisers
│       ├── db/
│       │   └── connection.py           connection + cursor context managers
│       ├── dependencies/
│       │   ├── auth.py                 get_current_user
│       │   └── permissions.py          require_super_admin / require_company_user
│       └── modules/
│           ├── auth/        router.py · schemas.py · service.py
│           ├── users/       router.py · schemas.py · service.py · repository.py
│           ├── companies/   router.py · schemas.py · service.py · repository.py
│           ├── inventory/   router.py · schemas.py · service.py · repository.py
│           └── roles/       service.py · repository.py        (no router)
│
├── React (FrontEnd)/GBMS/
│   ├── index.html · vite.config.js · package.json · eslint.config.js
│   ├── .env.local                      VITE_API_BASE_URL
│   ├── GBMSunderstanding.md            (pre-existing doc; not relied on)
│   ├── dist/                           build output (generated)
│   └── src/
│       ├── main.jsx                    browser entry point
│       ├── App.jsx                     landing page + LoginPopover + all <Routes>
│       ├── auth/
│       │   ├── AuthContext.jsx         AuthProvider (state + login/logout)
│       │   ├── authContext.js          createContext(null)
│       │   ├── useAuth.js              custom hook
│       │   ├── ProtectedRoute.jsx      "must be logged in"
│       │   └── RoleRoute.jsx           "must have one of these roles"
│       ├── services/
│       │   ├── authService.js          apiRequest() + login/me/dashboard
│       │   ├── companyService.js       company + company-user API calls
│       │   └── inventoryService.js     category/unit/product API calls
│       ├── Components/Layout/          AdminLayout · Sidebar · Topbar
│       └── pages/
│           ├── Dashboard/Dashboard.jsx
│           ├── Companies/CompaniesPage.jsx
│           └── Inventory/InventoryPage.jsx
│
└── SQL Server Query/
    ├── Auth Query.sql                          DB + Roles + Users + SUPER_ADMIN role
    ├── Multi Company Inventory Migration.sql   Companies, trigger, Units, Categories, Products
    └── Solution1.ssmssln, .vs/                 SSMS solution files
```

### 3.2 Backend core files

| Path | Responsibility | Called by | Depends on | If removed/changed |
|---|---|---|---|---|
| `app/main.py` | Creates `FastAPI` app, adds CORS, defines `/health`, registers 4 routers under `/api/v1` | Uvicorn (`app.main:app`), root `main.py`, tests | `core/config`, 4 routers | No API at all. Essential. |
| `main.py` (root) | One-line shim so `uvicorn main:app` also works | Optional | `app.main` | Nothing breaks if you always use `app.main:app`. |
| `app/core/config.py` | Loads `.env` (path relative to the file), exposes `JWT_SECRET`, `TOKEN_MINUTES`, DB settings, `ALLOWED_ORIGINS`, regex patterns. **Raises `RuntimeError` at import if the JWT secret is missing/placeholder.** | Nearly everything | `python-dotenv` | Server fails to start. Essential. |
| `app/core/security.py` | `make_token(user)`, `user_id_from_token(token)`, `password_hasher` | `auth/service`, `users/service`, `dependencies/auth`, `seed_admin` | `config`, `jwt`, `argon2` | No login/verification. Essential. |
| `app/core/validation.py` | `normalize_email`, `normalize_required_text` | Schemas in companies/users/inventory | `config.EMAIL_PATTERN` | Schemas would fail to import. Reusable. |
| `app/db/connection.py` | `get_connection()` (builds ODBC string; 503 on failure), `database_connection()` (rollback on exception, always close), `database_cursor()` | Every `service.py`, `seed_admin.py` | `pyodbc`, `config` | No DB access. Essential. |
| `app/dependencies/auth.py` | `get_current_user`: Bearer token → user dict | `permissions.py`, `auth/router` | `core/security`, `users/service` | All protected routes lose authentication. Essential. |
| `app/dependencies/permissions.py` | `require_super_admin`, `require_company_user` | companies/users/inventory routers | `dependencies/auth` | Role enforcement disappears. Essential. |
| `seed_admin.py` | Prompts for username/name/email/password, hashes, inserts `SUPER_ADMIN` | Run manually once | `security`, `db/connection` | You could no longer bootstrap the first admin from the CLI. |
| `tests/test_company_inventory.py` | Unit tests with fake cursors (no real DB) | Run manually | Most backend modules | No effect on runtime. |

### 3.3 Feature modules (pattern: router → service → repository)

| Module | Files | Notes |
|---|---|---|
| `auth` | `router.py`, `schemas.py`, `service.py` | No repository — it reuses `users/repository`. |
| `users` | `router.py`, `schemas.py`, `service.py`, `repository.py` | Also holds `get_authenticated_user`, used by the auth dependency. |
| `companies` | all four | Super Admin only. |
| `inventory` | all four | Company users only. |
| `roles` | `service.py`, `repository.py` | `get_role_id` lookup only. `service.get_role_id` is a pure pass-through wrapper of the repository function. [V] |

### 3.4 Frontend files

| Path | Responsibility | Used by | Notes |
|---|---|---|---|
| `index.html` | Static page with `<div id="root">`, loads `/src/main.jsx` | Browser | Essential |
| `src/main.jsx` | Mounts React; wraps in `StrictMode` → `BrowserRouter` → `AuthProvider` → `App` | `index.html` | Essential |
| `src/App.jsx` | Landing page components, `LoginPopover` (login form), and the whole `<Routes>` tree | `main.jsx` | Contains both marketing UI and routing |
| `src/auth/AuthContext.jsx` | `AuthProvider`: holds `token`, `user`, `isLoading`; `login()`, `logout()`; restores session | `main.jsx` | Essential |
| `src/auth/authContext.js` | Only `createContext(null)` | `AuthContext.jsx`, `useAuth.js` | Separate file (lint/Fast-Refresh convention [I]). Name differs from `AuthContext.jsx` only by capitalisation and extension, which is easy to confuse. |
| `src/auth/useAuth.js` | `useContext(AuthContext)` + error if used outside provider | Pages, layout, routes | Essential |
| `src/auth/ProtectedRoute.jsx` | Shows loading, else `<Outlet/>` if `user`, else redirect `/` | `App.jsx` | UI-level guard only |
| `src/auth/RoleRoute.jsx` | Same idea, plus `allowedRoles.includes(user.role_name)` else redirect `/dashboard` | `App.jsx` | UI-level guard only |
| `src/services/authService.js` | `request()` (low-level fetch), exported `apiRequest()` (adds token from `sessionStorage`), `authService.{login,me,dashboard}` | `AuthContext`, `Dashboard`, other services | Acts as the shared HTTP client |
| `src/services/companyService.js` | `list/get/create/update/setStatus/users/createUser` | `CompaniesPage` | Calls `apiRequest` |
| `src/services/inventoryService.js` | `categories/createCategory/units/products/getProduct/createProduct/updateProduct/setProductStatus` | `InventoryPage` | Calls `apiRequest` |
| `Components/Layout/AdminLayout.jsx` | Sidebar + Topbar + `<Outlet/>`; owns `sidebarOpen` state | `App.jsx` | Layout route |
| `Components/Layout/Sidebar.jsx` | Builds nav by role (`isSuperAdmin`, `isCompanyUser`) | `AdminLayout` | Menu visibility is cosmetic |
| `Components/Layout/Topbar.jsx` | Profile menu, **logout**, search box (no function), bell (no function) | `AdminLayout` | |
| `pages/Dashboard/Dashboard.jsx` | Calls `/dashboard`, shows welcome + role | route `/dashboard` | |
| `pages/Companies/CompaniesPage.jsx` | Company table, create/edit form, activate/deactivate, company accounts panel | route `/companies` | |
| `pages/Inventory/InventoryPage.jsx` | Product table, search/filter/paging, product form, inline category creation | route `/inventory` | |

---

## 4. Module dependency maps

### 4.1 Backend

```
app/main.py
 ├─► core/config.py ──► .env
 └─► modules/{auth,companies,users,inventory}/router.py
        │
        ├─► schemas.py                          Pydantic request validation
        ├─► dependencies/permissions.py         require_super_admin / require_company_user
        │        └─► dependencies/auth.py       get_current_user
        │                 ├─► core/security.py          decode JWT → user_id
        │                 └─► users/service.py          get_authenticated_user(user_id)
        │                          └─► users/repository.py ──► SQL Server
        └─► service.py
               ├─► db/connection.py             open connection + cursor, rollback/close
               └─► repository.py                SQL ──► SQL Server

auth/service.py   ─► users/repository.py, users/service.py (public_user, validate_role_company), core/security.py
users/service.py  ─► roles/service.py ─► roles/repository.py
```

### 4.2 Frontend

```
index.html ─► main.jsx ─► BrowserRouter ─► AuthProvider ─► App.jsx
                                │
                                ├─ LandingPage ─► LoginPopover ─► useAuth().login ─► authService.login
                                │
                                └─ ProtectedRoute ─► AdminLayout (Sidebar, Topbar)
                                        ├─ /dashboard  ─► DashboardPage ─► authService.dashboard
                                        ├─ RoleRoute[SUPER_ADMIN] ─► /companies ─► CompaniesPage ─► companyService
                                        └─ RoleRoute[company roles] ─► /inventory ─► InventoryPage ─► inventoryService
                                                                                     │
                            companyService / inventoryService ─► apiRequest (authService.js) ─► fetch
```

---

## 5. Setup / run order

Derived from the files [V unless marked]:

1. **Database:** run `Auth Query.sql` (creates DB `GBMS`, `Roles`, `Users`, unique indexes, `SUPER_ADMIN` role), then `Multi Company Inventory Migration.sql` (companies, trigger, units, categories, products, extra roles). The migration is written to be repeatable.
2. **Backend env:** copy `.env.example` → `.env`; set a real `JWT_SECRET_KEY` and DB settings. Blank `DB_USER`/`DB_PASSWORD` means Windows authentication (`Trusted_Connection=yes`).
3. **Seed the first admin:** from the backend folder run `python seed_admin.py`. Note its error message mentions `auth_schema.sql`, but your file is actually named `Auth Query.sql`.
4. **Start the backend:** from `FastAPI (BackEnd)`: `uvicorn app.main:app --reload` (stated in the docstring of root `main.py`).
5. **Start the frontend:** from `React (FrontEnd)/GBMS`: `npm run dev` (script in `package.json`).

---

## 6. Module-by-module explanation

Each module follows: **A** overview · **B** files · **C** execution flow · **D** functions · **E** data flow · **F** dependencies · **G** example · **H** teaching check.

### 6.1 Core & configuration (`app/core/*`)

**A. Overview.** Central settings, JWT/Argon2 helpers and shared validators. Everything else imports from here.

**B. Files.** `config.py`, `security.py`, `validation.py`.

**C. Execution flow.** The first time any module imports `app.core.config`, `load_dotenv()` reads `.env`, settings are read with `os.getenv`, and the JWT secret is checked. If it is missing or still `replace-with-a-long-random-secret`, a `RuntimeError` stops the server *before* it serves any request (fail-fast).

**D. Functions.**

| Function | Input | Does | Returns / raises |
|---|---|---|---|
| `make_token(user)` (`security.py`) | user dict with `user_id` | Encodes claims `sub` (user id as string), `iat`, `exp` (now + `TOKEN_MINUTES`), `type: "access"` with `JWT_SECRET` | JWT string |
| `user_id_from_token(token)` | JWT string | Decodes with `algorithms=[JWT_ALGORITHM]`, requires claims `sub, iat, exp, type`; PyJWT automatically rejects expired tokens; checks `type == "access"` | `int` user id; raises `jwt.PyJWTError` subclasses |
| `password_hasher` | — | `argon2.PasswordHasher()` with library defaults | Used for `.hash()` and `.verify()` |
| `normalize_email(value)` | str or None | Trim; blank → `None`; length ≤ 254 and regex check | cleaned email, `None`, or `ValueError` |
| `normalize_required_text(value, label)` | str, label | Trim; blank → `ValueError("<label> cannot be blank.")` | cleaned str |

**E. Data flow.** Plain values in, plain values out; no I/O except `.env` read at import.

**F. Dependencies.** `python-dotenv`, `PyJWT`, `argon2-cffi`. Used by every backend module.

**G. Example.** Login success → `make_token({"user_id": 7, ...})` → `{"sub":"7","iat":…,"exp":…,"type":"access"}` signed → string returned to the browser.

**H. Teaching check.**
1. Why does the token store only `sub` and not the role?
2. What happens, and when, if `.env` has no `JWT_SECRET_KEY`?

---

### 6.2 Database access (`app/db/connection.py`)

**A. Overview.** Opens SQL Server connections and cursors safely.

**C. Execution flow.** A service function does `with database_connection() as connection, database_cursor(connection) as cursor:` → work → on exit the cursor closes and the connection closes. If an exception escapes, `connection.rollback()` runs first.

**D. Functions.**

| Function | What it does |
|---|---|
| `get_connection()` | Builds `DRIVER={…};SERVER=…;DATABASE=…;` + either `UID/PWD` (if both set) or `Trusted_Connection=yes`, + `TrustServerCertificate=yes`. `pyodbc.connect(..., timeout=5)`. On `pyodbc.Error` raises **HTTP 503** "Database is unavailable…". |
| `database_connection()` | `@contextmanager`: yields the connection; on any exception → rollback and re-raise; `finally` → close. |
| `database_cursor(connection)` | `@contextmanager`: yields `connection.cursor()`; `finally` → close cursor. |

**E. Data flow.** Settings in → live connection out.

**F. Dependencies.** Imported by every `service.py` and `seed_admin.py`. [V] A **new connection is opened for each service call** (no pool in your code; ODBC may pool at driver level [I]).

**G. Example.** SQL Server is stopped → `get_connection()` raises 503 → React shows "Database is unavailable. Check the GBMS database connection settings."

**H. Teaching check.**
1. Why is `commit()` called explicitly in services instead of inside this file?
2. What does the rollback in `database_connection()` protect against?

---

### 6.3 Dependencies: authentication and permissions (`app/dependencies/*`)

**A. Overview.** FastAPI "dependencies" run *before* the route body. They turn a raw `Authorization` header into a trusted user dict and decide whether the role is allowed.

**D. Functions.**

| Function | Input | Internal logic | Output / errors |
|---|---|---|---|
| `get_current_user` (`auth.py`) | `HTTPAuthorizationCredentials` from `HTTPBearer(auto_error=False)` | No credentials or scheme ≠ bearer → 401. `user_id_from_token` inside try; `jwt.PyJWTError`, `ValueError`, `TypeError` → 401 "Your session is invalid or has expired." Then `get_authenticated_user(user_id)` | user dict (`user_id, username, full_name, email, role_name, company_id, company_status`) |
| `require_super_admin` (`permissions.py`) | `Depends(get_current_user)` | `role_name != "SUPER_ADMIN"` → 403 | user dict |
| `require_company_user` | `Depends(get_current_user)` | role not in `{COMPANY_ADMIN, SUB_ADMIN, INVENTORY_USER}` **or** `company_id is None` → 403 | user dict |

**Why `auto_error=False`?** So *your* code produces the 401 message and `WWW-Authenticate` header instead of FastAPI's default. [I]

**F. Dependencies.** `get_current_user` → `core.security` + `users.service.get_authenticated_user`. Permission functions → `get_current_user`. Chaining means `Depends(require_super_admin)` automatically runs authentication first.

**G. Example.** `GET /api/v1/companies` with an Inventory User token → token valid → user loaded → role `INVENTORY_USER` → `require_super_admin` raises 403 "Platform Super Admin access is required." The router function body never runs.

**H. Teaching check.**
1. Where in the code is the user's role actually *read* — the token or the DB?
2. What is the difference between 401 and 403 in these files?

---

### 6.4 Auth module (`app/modules/auth/*`)

**A. Overview.** Login, "who am I", and the authenticated landing endpoint.

**B. Files.** `router.py` (3 routes), `schemas.py` (`LoginPayload`), `service.py` (`login`).

**C. Execution flow (login).** Router receives JSON → Pydantic builds `LoginPayload` → `service.login(payload)` → DB lookup → Argon2 verify → status/company checks → token → response.

**D. Functions.**

| Item | Details |
|---|---|
| `login` route `POST /auth/login` | Input `LoginPayload{username: 1–80 chars, password: 1–1024 chars}`; returns `service.login(payload)` |
| `me` route `GET /auth/me` | `Depends(get_current_user)`; returns the user dict |
| `dashboard` route `GET /dashboard` | Any authenticated user; returns `{"message": "You have authenticated access to the GBMS workspace.", "user": user}` |
| `service.login(payload)` | 1) `repository.get_login_user_by_username(cursor, payload.username.strip())`. 2) no row → 401 "Invalid username or password." 3) `password_hasher.verify(row[6], payload.password)`; `VerifyMismatchError/VerificationError/ValueError` → same 401. 4) `row[5] != "ACTIVE"` → 403. 5) `validate_role_company(role, company_id, company_status)`. 6) `public_user(...)`. 7) returns `{access_token, token_type:"bearer", expires_in: TOKEN_MINUTES*60, user}` |

**Row indices used in login** (`get_login_user_by_username` SELECT order): `0 UserID, 1 Username, 2 FullName, 3 Email, 4 RoleName, 5 AccountStatus, 6 PasswordHash, 7 CompanyID, 8 CompanyStatus`.

**E. Data flow.** `{username,password}` → SQL row (tuple) → verified → dict `user` → JSON with token. The password hash never leaves the service (`public_user` omits it).

**F. Dependencies.** `users.repository`, `users.service`, `core.security`, `db.connection`.

**G. Example.** `admin` / correct password → 200 with a token and `role_name: "SUPER_ADMIN"`, `company_id: null`.

**H. Teaching check.**
1. Why does a missing user and a wrong password return the *same* message?
2. Which index of the SQL row is the password hash and why is it not sent to the browser?

---

### 6.5 Users module (`app/modules/users/*`)

**A. Overview.** Loads accounts for authentication and lets a Super Admin create/list a company's login accounts.

**D. Functions.**

| Function | File | Purpose |
|---|---|---|
| `get_auth_user_by_id`, `get_login_user_by_username` | `repository.py` | `Users JOIN Roles LEFT JOIN Companies`, `WHERE UserID = ?` / `Username = ?`, `.fetchone()` |
| `list_company_users` | `repository.py` | `WHERE u.CompanyID = ?` ordered by `FullName, UserID` |
| `insert_company_user` | `repository.py` | `SET NOCOUNT ON; INSERT … ; SELECT CONVERT(INT, SCOPE_IDENTITY())` then re-SELECT the row; raises `RuntimeError` if the ID/row isn't returned |
| `public_user(...)` | `service.py` | Builds the safe user dict (no hash) |
| `validate_role_company(role, company_id, company_status)` | `service.py` | SUPER_ADMIN must have **no** company; others must have a company and it must be `ACTIVE` (else 403) |
| `get_authenticated_user(user_id)` | `service.py` | DB lookup; missing → 401; status ≠ ACTIVE → 403; `validate_role_company`; returns `public_user` |
| `list_company_users(company_id)` | `service.py` | 404 if company missing; returns `{"items": [...]}` |
| `create_company_user(company_id, payload)` | `service.py` | Checks company exists (404) and is ACTIVE (409); resolves role ID via `roles.service.get_role_id` (500 + log if role missing); **hashes the password with Argon2**; inserts; `commit()`. Maps `pyodbc.IntegrityError` (codes 2601/2627, names `UQ_Users_Username` / `UQ_Users_Email`) to 409 with friendly text; other DB/unexpected errors are logged via `logging.getLogger("gbms")` and returned as 500 |
| `CompanyUserCreate` | `schemas.py` | `username` 3–80 `[A-Za-z0-9_.-]`, `full_name`, `email` (validated), `password` **12–128**, `role_name` ∈ {COMPANY_ADMIN, SUB_ADMIN, INVENTORY_USER} (default COMPANY_ADMIN); `extra="forbid"` |

**Routes** (`router.py`, both `require_super_admin`): `GET /companies/{company_id}/users`, `POST /companies/{company_id}/users` (201). `company_id` is validated `Path(gt=0)`.

**Not present [V]:** editing a user, deactivating a user, resetting/changing passwords, deleting users.

**G. Example.** Super Admin creates `ali.inv` with role `INVENTORY_USER` for company 3 → row inserted with `CompanyID = 3` (taken from the URL, which only a Super Admin can call) → trigger accepts it (non-super role has a company).

**H. Teaching check.**
1. Where does the new user's `CompanyID` come from?
2. What two layers (one in Python, one in SQL) both enforce "SUPER_ADMIN has no company"?

---

### 6.6 Roles module (`app/modules/roles/*`)

**A.** One lookup: `SELECT RoleID FROM dbo.Roles WHERE RoleName = ?`. `roles/service.get_role_id` simply calls the repository function.
**Notes [V]:** no router/schema. Roles are rows in `dbo.Roles`, but **permissions are not stored in the database** — they are hard-coded role-name checks in `permissions.py` and the frontend.

---

### 6.7 Companies module (`app/modules/companies/*`)

**A. Overview.** Super Admin manages tenant companies.

**D. Functions.**

| Function | Notes |
|---|---|
| `list_companies(cursor, search, limit, offset)` (repo) | Optional `LIKE` over `CompanyName/CompanyCode/Email`; `COUNT(*)` then `ORDER BY CompanyName, CompanyID OFFSET ? ROWS FETCH NEXT ? ROWS ONLY`. The `WHERE` text is built in Python, but values are bound parameters. |
| `create_company` (repo) | `INSERT … OUTPUT INSERTED.<cols> VALUES (?,?,?,?,?)` → returns the new row in one statement |
| `update_company` (repo) | Builds `SET` list from a **whitelist dict** (`company_name → CompanyName`, …) + `UpdatedAt = SYSUTCDATETIME()`; `OUTPUT INSERTED…`; `WHERE CompanyID = ?` |
| `update_company_status` (repo) | Sets `CompanyStatus`, `UpdatedAt` |
| `serialize_company(row)` (repo) | tuple → dict with snake_case keys |
| `list_companies / create_company / get_company / update_company / set_company_status` (service) | Call repo, `commit()` on writes, map `IntegrityError` (2601/2627 → 409 "A company with that name or code already exists."), 404 when missing, 400 if update has no fields, 422 if name/code explicitly null |
| `CompanyCreate / CompanyUpdate / CompanyStatusUpdate` (schemas) | Code pattern `^[A-Za-z0-9][A-Za-z0-9_-]{1,29}$`, code upper-cased, name not blank, email normalised, phone/address trimmed (blank → `None`), status ∈ {ACTIVE, INACTIVE}; `extra="forbid"` |

**Partial update trick:** `payload.model_dump(exclude_unset=True)` returns only the fields the client actually sent, so `PUT` behaves like a partial update. [V]

**Routes** (all `require_super_admin`): `GET /companies`, `POST /companies` (201), `GET /companies/{id}`, `PUT /companies/{id}`, `PATCH /companies/{id}/status`.

**G. Example.** Create company "Northline Apparel", code `nla` → schema upper-cases to `NLA` → `INSERT` → 201 + JSON → page shows "Company created." and reloads page 1.

**H. Teaching check.**
1. Why is `exclude_unset=True` important for `PUT /companies/{id}`?
2. What happens if two companies share a code?

---

### 6.8 Inventory module (`app/modules/inventory/*`)

**A. Overview.** Company-scoped product catalogue.

**D. Functions.**

| Function | Notes |
|---|---|
| `PRODUCT_SELECT` (repo) | `Products p LEFT JOIN ProductCategories c ON c.CategoryID = p.CategoryID AND c.CompanyID = p.CompanyID JOIN UnitsOfMeasure u` — the category join is also company-scoped |
| `list_categories(cursor, company_id)` | `WHERE CompanyID = ?` |
| `create_category` | `INSERT … OUTPUT INSERTED…` with `company_id` from the token-derived user |
| `list_units` | Global reference data; `IsActive = 1` |
| `category_available(cursor, category_id, company_id)` | `WHERE CategoryID = ? AND CompanyID = ?` |
| `list_products(...)` | Always `p.CompanyID = ?`; optional SKU/name `LIKE`, optional `category_id`; paging |
| `get_company_product` | `WHERE p.CompanyID = ? AND p.ProductID = ?` — another company's product ID simply returns "not found" |
| `insert_product` | `OUTPUT INSERTED.ProductID` |
| `update_product` | Whitelisted columns; `WHERE CompanyID = ? AND ProductID = ?` |
| `update_product_status` | Sets `IsActive`; service checks `rowcount == 0` → 404 |
| Service helpers | `_ensure_category` (422 if the category isn't this company's), `_ensure_unit` (422 if not an active unit), `_get_company_product` (404), `_integrity_error` (409 duplicate SKU) |
| Schemas | `ProductCreate/Update`: SKU pattern `^[A-Za-z0-9][A-Za-z0-9._/-]{0,59}$` and upper-cased; `product_type` ∈ {RAW_MATERIAL, FINISHED_GOOD}; `reorder_level` Decimal ≥ 0 (18 digits, 3 decimals); `extra="forbid"` |

**Routes** (all `require_company_user`): categories (`GET`, `POST`), `GET /inventory/units`, products (`GET` list, `POST`, `GET /{id}`, `PUT /{id}`, `PATCH /{id}/status`).

**Not present [V]:** stock quantities, stock movements, warehouses, deletion.

**G. Example.** An Inventory User of company 3 requests product 99 that belongs to company 5 → query `WHERE CompanyID = 3 AND ProductID = 99` returns no row → 404 "Product not found." (the existence of the other company's product is not revealed).

**H. Teaching check.**
1. Which parameter guarantees a user only sees their company's products, and where does it come from?
2. Name two places that stop a product linking to another company's category.

---

### 6.9 Frontend — auth state (`src/auth/*`)

**A.** Keeps the logged-in session available to every component.

**D. Functions/components.**

| Item | Behaviour |
|---|---|
| `AuthProvider` (`AuthContext.jsx`) | State: `token` (initialised from `sessionStorage['gbms_access_token']`), `user` (null), `isLoading` (true if a token was found). `useEffect([token])`: if token → `authService.me(token)` → `setUser`; on failure removes the token and resets state; `active` flag prevents state updates after unmount/token change. Exposes `{token, user, isLoading, login, logout}` via `useMemo`. |
| `login(credentials)` | `authService.login` → store `access_token` in `sessionStorage` → `setToken` + `setUser(result.user)`. Errors propagate to the caller (LoginPopover). |
| `logout()` | Remove token from `sessionStorage`; `setToken(null)`; `setUser(null)`. **No backend call.** |
| `useAuth()` | `useContext(AuthContext)`; throws if outside provider |
| `ProtectedRoute` | loading → "Loading workspace…"; `user` → `<Outlet/>`; else `<Navigate to="/" replace/>` |
| `RoleRoute({allowedRoles})` | loading → message; no user → `/`; role allowed → `<Outlet/>`; else `<Navigate to="/dashboard"/>` |

**Note [V]:** after `login()` sets a new token, the `useEffect([token])` runs again and calls `/auth/me` a second time (harmless duplicate request). [I]

---

### 6.10 Frontend — layout and navigation (`Components/Layout/*`)

- `AdminLayout`: owns `sidebarOpen`; renders `Sidebar`, `Topbar`, and `<Outlet/>` inside `<main>`.
- `Sidebar`: from `useAuth().user.role_name` computes `isSuperAdmin` / `isCompanyUser`, builds groups: OVERVIEW (always), PLATFORM → Companies (super admin), BUSINESS → Inventory (company roles), COMING SOON (disabled placeholders). Uses `NavLink` for active styling.
- `Topbar`: initials/name from `user`; profile dropdown (closes on outside click/Escape); `handleLogout` → `logout()` then `navigate('/', {replace:true})`. Search box and bell are **decorative** (no behaviour).

### 6.11 Frontend — services (`src/services/*`)

- `request(path, {token, ...options})` — private. Builds `fetch(`${API_BASE}${path}`)`; sets `Content-Type: application/json` when there is a body and `Authorization: Bearer <token>` when a token exists; a `TypeError` (network failure) becomes the readable error "Cannot reach FastAPI at http://127.0.0.1:8000…"; parses JSON (empty object if parsing fails); for `!response.ok` builds a message from `body.detail` (string, or array of Pydantic errors → joined `msg`s) and throws `Error` with `.status`.
- `apiRequest(path, options)` — exported; takes `options.token` or falls back to `sessionStorage`.
- `authService.login / me / dashboard`; `companyService.*`; `inventoryService.*` — thin wrappers that map a JS function to one HTTP route.

### 6.12 Frontend — pages

| Page | State & behaviour [V] |
|---|---|
| `DashboardPage` | On mount (and when `token` changes) calls `authService.dashboard(token)`; shows `dashboard.message`, `user.username`, `user.role_name`. No business data. |
| `CompaniesPage` | Table with search (`searchInput` → `search` on submit), paging (`limit = 20`, `offset`), create/edit form (`editingId`), activate/deactivate with `window.confirm`, and an "Accounts" panel (`userCompany`, `companyUsers`, `userForm`) that lists/creates users via `companyService.users/createUser`. |
| `InventoryPage` | Loads products, categories and units; search + category filter + paging; create/edit product form; activate/deactivate; inline "Create a category" form that, on success, inserts the new category into local state and preselects it in the product form. |
| `App.jsx` landing page | Marketing UI with **hard-coded illustrative data** (`DashboardPreview`, capability cards). `LoginPopover` is the real login form. |

**Frontend validation [V]:** HTML attributes only (`required`, `maxLength`, `pattern`, `type="email"`, `min`). The real validation is the backend's Pydantic schemas.

---

## 7. End-to-end user journeys

### Flow 1 — Application startup

**Frontend**
1. Browser loads `index.html` → `<script type="module" src="/src/main.jsx">`.
2. `main.jsx` calls `createRoot(document.getElementById('root')).render(...)` with the tree `StrictMode → BrowserRouter → AuthProvider → App`.
3. `AuthProvider` reads `sessionStorage` for a saved token (see Flow 5).
4. `App` renders `<Routes>` (in `App.jsx`):

```
/               → LandingPage (public)
ProtectedRoute  → AdminLayout
   /dashboard   → DashboardPage
   RoleRoute[SUPER_ADMIN]                                  → /companies
   RoleRoute[COMPANY_ADMIN, SUB_ADMIN, INVENTORY_USER]     → /inventory
*               → redirect to /
```

**Backend**
1. `uvicorn app.main:app --reload` imports `app/main.py`.
2. Importing `core/config.py` loads `.env` and **stops with `RuntimeError` if the JWT secret is missing**.
3. The four routers are imported (which imports services, repositories, `db/connection`, `core/security`).
4. `FastAPI(title="GBMS API", version="1.1.0")` is created; `CORSMiddleware` allows only `ALLOWED_ORIGINS`, methods `GET, POST, PUT, PATCH`, headers `Authorization, Content-Type`, with credentials allowed.
5. `/health` is defined; routers are registered with `prefix="/api/v1"` (inventory additionally has its own `/inventory` prefix).

**Connection in dev:** Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`.

---

### Flow 2 — Login

| Step | Where | What happens |
|---|---|---|
| 1 | `App.jsx` → `LoginPopover` | User types username/password; inputs have `required`, `maxLength` 80 / 1024 |
| 2 | `LoginPopover` `onSubmit` | `event.preventDefault()`, `setIsSubmitting(true)`, `new FormData(event.currentTarget)` → `login({username, password})` |
| 3 | `AuthContext.login` | Calls `authService.login(credentials)` |
| 4 | `authService.js` | `request('/api/v1/auth/login', {method:'POST', body: JSON.stringify(credentials)})` |
| 5 | `auth/router.py` | `login(payload: LoginPayload)` — Pydantic validates lengths (422 if invalid) |
| 6 | `auth/service.login` | Opens DB connection, runs `get_login_user_by_username` |
| 7 | SQL Server | `SELECT … FROM dbo.Users u JOIN dbo.Roles r … LEFT JOIN dbo.Companies c … WHERE u.Username = ?` |
| 8 | `auth/service.login` | `password_hasher.verify(row[6], password)`; checks `AccountStatus == 'ACTIVE'`; `validate_role_company` |
| 9 | `core/security.make_token` | Creates JWT (`sub`, `iat`, `exp`, `type`) |
| 10 | Response | `{access_token, token_type:"bearer", expires_in, user}` |
| 11 | `AuthContext.login` | `sessionStorage.setItem('gbms_access_token', …)`, `setToken`, `setUser` |
| 12 | `LoginPopover` | `onClose()` then `navigate('/dashboard')` |
| 13 | `ProtectedRoute` | `user` exists → `<Outlet/>` renders the dashboard |

**Errors**

| Situation | Backend result | What the user sees |
|---|---|---|
| Unknown username | 401 "Invalid username or password." | Message in the popover (`setMessage(error.message)`) |
| Wrong password | same 401 | same |
| Account not ACTIVE (after password OK) | 403 "This account is not active…" | message |
| Company inactive / no company / invalid super admin config | 403 from `validate_role_company` | message |
| DB down | 503 "Database is unavailable…" | message |
| Backend down | fetch `TypeError` | "Cannot reach FastAPI at http://127.0.0.1:8000…" |
| Empty fields | blocked by HTML `required`; 422 from backend if bypassed | message from joined `msg`s |

---

### Flow 3 — Authenticated requests

1. **Creation:** `make_token` at login (Flow 2).
2. **Storage:** `sessionStorage['gbms_access_token']` and React state `token`.
3. **Sending:** `apiRequest` reads the token (`options.token ?? sessionStorage.getItem(...)`) and sends `Authorization: Bearer <token>`.
4. **Extraction:** `HTTPBearer(auto_error=False)` in `dependencies/auth.py` parses the header.
5. **Validation:** `user_id_from_token` verifies the signature with `JWT_SECRET`, the algorithm list, required claims, expiry (`exp`), and `type == "access"`.
6. **Identification:** `get_authenticated_user(user_id)` queries the DB; the result carries the **current** role, company and status.
7. **Authorization:** `require_super_admin` or `require_company_user` compares the DB-loaded role.
8. **Expiry:** after `ACCESS_TOKEN_MINUTES` (default 30 in `config.py`) PyJWT rejects the token → 401. The frontend has **no global 401 handler**; the page that made the request just shows the error text. The session is only cleared if `/auth/me` fails (on load/token change). [V]

---

### Flow 4 — Dashboard

1. `/dashboard` is inside `ProtectedRoute → AdminLayout`.
2. `DashboardPage` takes `token` and `user` from `useAuth()`.
3. `useEffect` calls `authService.dashboard(token)` → `GET /api/v1/dashboard`.
4. Backend: `get_current_user` → returns `{message, user}`.
5. The page shows the welcome name (from context), `dashboard.message`, username and role.

**Reality check [V]:** the dashboard holds **no business metrics**. The charts/numbers on the landing page are static, hard-coded "illustrative data".

---

### Flow 5 — Logout and session persistence

**Logout:** `Topbar.handleLogout` → `logout()` (remove token, clear state) → `navigate('/', {replace:true})`. No request is sent to the backend, so the JWT stays technically valid until it expires (see §11).

**Refresh:** React state is lost, but `sessionStorage` survives a refresh in the same tab → `AuthProvider` starts with the saved token and `isLoading = true` → `/auth/me` restores `user` → `ProtectedRoute` shows "Loading workspace…" then the page. If `/auth/me` fails (expired, inactive, deleted), the token is removed and the user is sent to `/`.

**New tab / browser restart:** `sessionStorage` is per tab, so the user must log in again. [V code, standard browser behaviour]

---

### Flow 6 — Company management (Super Admin)

Example: **Create company**

1. `CompaniesPage` → "Create company" (`openCreate`) → form (`form` state).
2. Submit → `handleSubmit`: builds `payload` (blank optional fields → `null`) → `companyService.create(payload)`.
3. `apiRequest('/api/v1/companies', {method:'POST', body})` + Bearer token.
4. `companies/router.create_company(payload: CompanyCreate, _admin=Depends(require_super_admin))`.
5. Pydantic: name not blank, code regex + upper-case, email normalised.
6. `service.create_company` → `repository.create_company`:

```sql
INSERT INTO dbo.Companies (CompanyName, CompanyCode, Email, Phone, Address)
OUTPUT INSERTED.CompanyID, INSERTED.CompanyName, INSERTED.CompanyCode,
       INSERTED.Email, INSERTED.Phone, INSERTED.Address,
       INSERTED.CompanyStatus, INSERTED.CreatedAt, INSERTED.UpdatedAt
VALUES (?, ?, ?, ?, ?)
```
   - `OUTPUT INSERTED.*` returns the created row from the same statement (including DB defaults like `CompanyStatus='ACTIVE'`, `CreatedAt`).
   - `?` are bound parameters (no string concatenation of values).
7. `connection.commit()`; `serialize_company(row)` → dict → **201** JSON.
8. Frontend: `setSuccess('Company created.')`, `setOffset(0)`, `setFormOpen(false)`, `loadCompanies(0)` refreshes the table.
9. Duplicate name/code → unique index violation (2601/2627) → **409** "A company with that name or code already exists." → shown in the red alert.

Other actions: edit (`GET` then `PUT`), activate/deactivate (`PATCH …/status`, after `window.confirm`).

---

### Flow 7 — Company user creation and permissions

1. In the companies table, "Accounts" → `manageUsers(company)` loads `GET /companies/{id}/users`.
2. The form posts `{username, full_name, email, password, role_name}` to `POST /companies/{id}/users`.
3. Backend: `require_super_admin` → `CompanyUserCreate` (password ≥ 12 chars) → `create_company_user`:
   - company exists (404) and is `ACTIVE` (409 otherwise);
   - role name → `RoleID` (500 if missing);
   - `password_hasher.hash(password)` (Argon2);
   - `INSERT INTO dbo.Users (Username, FullName, Email, PasswordHash, RoleID, CompanyID) VALUES (?, …)` then `SCOPE_IDENTITY()`;
   - `commit()`;
   - the SQL **trigger** `TR_Users_CompanyRoleScope` re-checks the role/company rule.
4. The **company association** comes from the URL `company_id`, which only a Super Admin can call, never from the new user.
5. Duplicate username/email → 409 with a specific message.
6. After login, that user's permissions come from `role_name`: all three company roles currently have **identical access** (inventory only).

**Backend protection against unauthorised access:** `require_super_admin` on the route; the client cannot choose a role outside the `Literal[...]` list (so no `SUPER_ADMIN` creation via the API).

---

### Flow 8 — Inventory

Example: **Add a product**

1. `InventoryPage.saveProduct` builds `payload` (SKU/name trimmed, numbers converted, `category_id` → number or `null`, `reorder_level` as entered).
2. `inventoryService.createProduct` → `POST /api/v1/inventory/products` + Bearer token.
3. Router `create_product(payload: ProductCreate, user=Depends(require_company_user))` → `service.create_product(user["company_id"], payload)`.
4. Service: `_ensure_category(cursor, category_id, company_id)`, `_ensure_unit(cursor, unit_id)`.
5. `repository.insert_product`:

```sql
INSERT INTO dbo.Products
  (CompanyID, CategoryID, SKU, ProductName, ProductType, UnitID, Description, ReorderLevel)
OUTPUT INSERTED.ProductID
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```
6. `_get_company_product` reads it back via `PRODUCT_SELECT … WHERE p.CompanyID = ? AND p.ProductID = ?`; `commit()`; `serialize_product` → **201** JSON.
7. Frontend: `setSuccess('Product created.')`, close form, `setOffset(0)`, `loadProducts(0)`.
8. Duplicate SKU **within the same company** → unique index `UQ_Products_Company_SKU` → 409. (Different companies may reuse the same SKU.)

---

## 8. How data is shared between modules

### 8.1 Five mechanisms compared

| Mechanism | Used for | Example in GBMS | Scope |
|---|---|---|---|
| **Direct function call** | Moving data between backend layers | `router.create_product` → `service.create_product(user["company_id"], payload)` → `repository.insert_product(cursor, company_id, payload)` | Same process, same request |
| **React props** | Parent → child | `AdminLayout` passes `isOpen`/`onClose` to `Sidebar` and `onMenuClick` to `Topbar`; `LandingPage` passes `onLogin` to `Navbar`, `HeroSection`, `CTASection`, `Footer`; `LoginPopover` receives `open`/`onClose` | One component subtree, explicit |
| **React Context** | App-wide state without prop-drilling | `AuthContext` value `{token, user, isLoading, login, logout}`, read with `useAuth()` in routes, layout, pages | Everything below `AuthProvider` |
| **HTTP API** | Browser ↔ server | `inventoryService.products()` → `GET /api/v1/inventory/products` → JSON | Across processes; must be validated on arrival |
| **SQL Server** | Persistent shared data | `Products`, `Users`, … read/written via `cursor.execute(sql, params)` | Across requests and users |

### 8.2 Backend connections, with real code

- **Router → service:** `return service.list_products(user["company_id"], search, category_id, limit, offset)`.
- **Auth dependency → route:** `user=Depends(require_company_user)` — FastAPI runs the dependency chain and injects the returned dict as `user`.
- **Schema → service:** FastAPI parses JSON into `ProductCreate`; the service reads `payload.sku`, `payload.unit_id`, etc.
- **Service → repository:** passes the open `cursor` plus plain values.
- **Rows → JSON:** `cursor.execute(...).fetchone()` returns a tuple; `serialize_product(row)` maps `row[0]` → `"product_id"`, etc. FastAPI turns the dict into JSON.
- **Errors:** `HTTPException(status_code, detail)` raised in services/dependencies → FastAPI response `{"detail": "..."}`. Pydantic validation failures → 422 with `detail` as a list.

### 8.3 Frontend connections, with real code

- **Hook:** `const { token, user } = useAuth()` in `DashboardPage`.
- **Page → service:** `companyService.list({ search, limit, offset })` → `apiRequest('/api/v1/companies?search=…&limit=20&offset=0')` (query string via `URLSearchParams`, skipping empty values).
- **Response → UI:** `setCompanies(result.items); setTotal(result.total)` → re-render of the table.
- **Error → UI:** `apiRequest` throws `Error(detail)`; pages `catch (failure) { setError(failure.message) }` and render `<p role="alert">`.

### 8.4 How an error travels

```
SQL error / HTTPException in service or dependency
  → FastAPI JSON {"detail": "…"} with status code
  → apiRequest(): !response.ok → new Error(detail) (with .status)
  → page's catch → setError(message)
  → red alert <p role="alert"> in the UI
```

---

## 9. Database and SQL

### 9.1 Tables [V — from scripts]

| Table | Purpose | Key columns |
|---|---|---|
| `dbo.Roles` | Global role names | `RoleID` PK (identity), `RoleName` UNIQUE (`UQ_Roles_RoleName`), `Description`, `CreatedAt` |
| `dbo.Users` | Accounts | `UserID` PK, `Username`, `FullName`, `Email`, `PasswordHash` (NVARCHAR 255), `RoleID` FK→Roles, `CompanyID` FK→Companies (**nullable**, added by migration), `AccountStatus` default `ACTIVE`, `CreatedAt`, `UpdatedAt` |
| `dbo.Companies` | Tenants | `CompanyID` PK, `CompanyName`, `CompanyCode`, `Email`, `Phone`, `Address`, `CompanyStatus` default `ACTIVE`, `CreatedAt`, `UpdatedAt` |
| `dbo.UnitsOfMeasure` | Global units | `UnitID` PK, `UnitCode` UNIQUE, `UnitName`, `Symbol`, `IsActive`; seeded: PC, KG, M, YD, ROLL, BOX |
| `dbo.ProductCategories` | Per-company categories | `CategoryID` PK, `CompanyID` FK→Companies, `CategoryName`, `Description` |
| `dbo.Products` | Per-company products | `ProductID` PK, `CompanyID` FK, `CategoryID` (nullable), `SKU`, `ProductName`, `ProductType`, `UnitID` FK, `Description`, `ReorderLevel` DECIMAL(18,3), `IsActive` BIT, timestamps |

### 9.2 Relationships

```
Roles 1 ───< Users >─── 0..1 Companies
                          │ 1
                          ├───< ProductCategories
                          └───< Products >─── 1 UnitsOfMeasure
ProductCategories (CompanyID, CategoryID)  ◄── Products (CompanyID, CategoryID)   composite FK
```

### 9.3 Constraints and indexes

| Object | Rule |
|---|---|
| `CK_Users_AccountStatus` | `ACTIVE`, `INACTIVE`, `SUSPENDED` |
| `UQ_Users_Username`, `UQ_Users_Email` | unique indexes |
| `IX_Users_CompanyID` | lookup index |
| `CK_Companies_CompanyStatus` | `ACTIVE`, `INACTIVE` |
| `CK_Companies_*_NotBlank` | name/code non-blank |
| `UQ_Companies_CompanyCode`, `UQ_Companies_CompanyName` | unique indexes |
| `CK_Products_ProductType` | `RAW_MATERIAL`, `FINISHED_GOOD` |
| `CK_Products_ReorderLevel` | `>= 0` |
| `UQ_Products_Company_SKU` | unique **(CompanyID, SKU)** — SKUs unique per company |
| `UQ_ProductCategories_Company_CategoryName` | unique (CompanyID, CategoryName) |
| `UQ_ProductCategories_Company_CategoryID` | unique (CompanyID, CategoryID) — target of the composite FK |
| `FK_Products_CompanyCategory` | `(CompanyID, CategoryID)` → `ProductCategories(CompanyID, CategoryID)` — blocks cross-company category links (a `NULL` category is allowed) |
| `IX_Products_Company_Name`, `IX_Products_Company_Category` | lookup indexes |
| **Trigger** `TR_Users_CompanyRoleScope` (AFTER INSERT, UPDATE on Users) | `SUPER_ADMIN` with a company, or any other role without one → `THROW 51001` |

### 9.4 How queries run

- **Connection:** `pyodbc.connect(connection_string, timeout=5)` in `get_connection()`.
- **Parameters:** `cursor.execute("… WHERE u.Username = ?", username)` — `?` placeholders mean values are never glued into the SQL text (prevents SQL injection).
- **Fetching:** `.fetchone()` (one tuple or `None`), `.fetchall()` (list of tuples).
- **Transforming:** `serialize_*` / list comprehensions in services convert tuples to dicts.
- **Transactions:** pyodbc does not autocommit by default [I, standard pyodbc behaviour]; services call `connection.commit()` after writes; `database_connection()` rolls back on any exception.
- **Dynamic SQL:** `f"…{where}…"` and `UPDATE … SET {assignments}` are built only from **hard-coded fragments and whitelisted column names**; user values always travel as parameters. [V]

### 9.5 The important queries, line by line

**Login query** (`users/repository.get_login_user_by_username`)

```sql
SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
       u.AccountStatus, u.PasswordHash, u.CompanyID, c.CompanyStatus
FROM dbo.Users AS u                                  -- start from the account
JOIN dbo.Roles AS r ON r.RoleID = u.RoleID           -- INNER JOIN: every user has a role
LEFT JOIN dbo.Companies AS c ON c.CompanyID = u.CompanyID
                                                     -- LEFT JOIN: Super Admin has no company, row must still return
WHERE u.Username = ?                                 -- bound parameter
```

**Company-scoped product list** (`inventory/repository.list_products`)

```sql
SELECT COUNT(*) FROM dbo.Products AS p
WHERE p.CompanyID = ? [AND (p.SKU LIKE ? OR p.ProductName LIKE ?)] [AND p.CategoryID = ?]

<PRODUCT_SELECT> WHERE <same conditions>
ORDER BY p.ProductName, p.ProductID
OFFSET ? ROWS FETCH NEXT ? ROWS ONLY                 -- pagination (needs ORDER BY)
```

**Safe-ID insert** (`users/repository.insert_company_user`): `SET NOCOUNT ON; INSERT …; SELECT CONVERT(INT, SCOPE_IDENTITY());` — `SCOPE_IDENTITY()` returns the identity created *in this scope* (safer than `@@IDENTITY` when triggers exist, which is relevant because `Users` has a trigger).

### 9.6 Caveats about the scripts

- `Auth Query.sql` ends with `Select * from Users;` and the migration ends with `Select * From Companies;`. These are harmless reads but would display password hashes if you run the first one.
- Table definitions are inferred from scripts; confirm against your live DB if you ever edited it manually.

---

## 10. Authentication, authorization and company data isolation

| Concept | Question | Answer in your code |
|---|---|---|
| **Authentication** | Who is this? | `get_current_user`: Bearer JWT → `user_id` → DB row |
| **Authorization** | What may they do? | `require_super_admin` / `require_company_user` check `role_name` (and `company_id`) of the DB-loaded user |
| **Roles** | How are rights decided? | Role *names* in `dbo.Roles`; meaning is hard-coded in `permissions.py` and in frontend arrays. No permission tables. |
| **JWT** | What is inside? | `sub` (user id string), `iat`, `exp`, `type="access"`. **No role, no company.** Signed with HS256 using `JWT_SECRET`. Validation requires all four claims, checks signature, expiry and `type`. |
| **Argon2** | How is the password checked? | At user creation `password_hasher.hash(password)` produces a salted hash string stored in `PasswordHash`. At login `password_hasher.verify(stored_hash, typed_password)` re-computes and compares; mismatch raises `VerifyMismatchError`. The password itself is never stored. |
| **Frontend route protection** | Who can open a page? | `ProtectedRoute` (logged in?) and `RoleRoute` (role allowed?) — **user-experience only** |
| **Backend protection** | Who can call an API? | Dependencies on every route except `/auth/login` and `/health` |
| **Company isolation** | Can company A see company B? | No — see below |

### Which protections are real?

| Protection | Backend (real) | Frontend only (cosmetic) |
|---|---|---|
| Must be logged in to call APIs | ✅ `get_current_user` | |
| Companies/users APIs only for Super Admin | ✅ `require_super_admin` | Sidebar hides link; `RoleRoute` |
| Inventory APIs only for company roles | ✅ `require_company_user` | Sidebar hides link; `RoleRoute` |
| Tenant scoping of data | ✅ `user["company_id"]` + `WHERE CompanyID = ?` + DB constraints | |
| Deactivated company blocks its users immediately | ✅ `validate_role_company` runs on **every** request | |
| Button hiding / redirects | | ✅ cosmetic |

**Company isolation in detail [V]:**
1. Tenant identity is read from the DB, never from the request.
2. Request schemas forbid extra fields (the tests include "client tenant" rejection).
3. All product/category queries filter on `CompanyID`.
4. Fetching another company's product by ID yields 404.
5. Database composite FK prevents cross-company category references.
6. **Gap to understand:** categories are protected by the composite FK; `Products.UnitID` is global by design (units are shared reference data).

---

## 11. Security observations

*(Observations only — nothing has been changed.)*

| # | Finding | Location | Type |
|---|---|---|---|
| 1 | `.env` and `.env.local` are inside the zip; the backend `.gitignore` ignores `.env`, but the zip bypasses git | project zip | [V] Rotate secrets if shared |
| 2 | **No server-side logout / token revocation.** After "Sign out" the JWT stays valid until `exp`. | `AuthContext.logout`, no backend route | [V] Risk window = token lifetime (default 30 min) |
| 3 | Token stored in `sessionStorage` (readable by any injected script). | `AuthContext.jsx`, `authService.js` | [V] Common trade-off; [R] consider httpOnly cookies later |
| 4 | **No login rate-limiting or lockout.** | `auth/router.py`, `auth/service.py` | [V] absent |
| 5 | Unknown username returns before Argon2 runs, so response time may differ from a wrong password (username enumeration by timing). | `auth/service.login` | [I] |
| 6 | No frontend handling of 401 mid-session; expired token yields per-page errors instead of a clean sign-out. | `authService.request` | [V] UX/security hygiene |
| 7 | No endpoints to change/reset passwords or deactivate individual users. Temporary passwords set by the Super Admin cannot be changed by the user. | users module | [V] absent |
| 8 | `TrustServerCertificate=yes` disables SQL Server certificate validation. | `db/connection.py` | [V] Acceptable locally; review for production |
| 9 | `ALLOWED_ORIGINS` always includes localhost origins even if `CORS_ORIGINS` is configured otherwise. | `core/config.py` | [V] |
| 10 | `VITE_API_BASE_URL` is set to `http://localhost:5173` (the Vite server, with a leading space in the file). It works in dev through the proxy, but a production build would bake in that value. | `.env.local`, `authService.js` line 2 | [V] value; [I] effect |
| 11 | JWT default algorithm HS256 with one shared secret; strength depends entirely on `JWT_SECRET_KEY`. | `config.py` | [V] |
| 12 | Only `create_company_user` logs errors; other services don't log DB failures. | `users/service.py` only | [V] |
| 13 | SQL injection risk is low: values are bound parameters and dynamic column names come from whitelists. | repositories | [V] positive |
| 14 | Password policy: 12–128 chars on creation; no complexity/breach check. | `users/schemas.py` | [V] |

---

## 12. Debugging guide

*(Items marked **[general]** are general advice, not features of your project.)*

### 12.1 React rendering error
1. Browser DevTools → **Console** for the red error and component stack.
2. A blank page after a change often means an exception thrown during render.
3. `useAuth must be used inside AuthProvider` (from `useAuth.js`) → the component is outside the provider (check `main.jsx`).
4. React DevTools **[general]** to inspect state (`token`, `user`, `isLoading`).

### 12.2 Failed API request
1. DevTools → **Network** tab → click the request → check URL, status, request headers (is `Authorization: Bearer …` present?), payload, response body.
2. URL should start with `/api/v1/...`; remember inventory routes have the extra `/inventory`.
3. "Cannot reach FastAPI at http://127.0.0.1:8000…" (from `authService.request`) → backend not running or proxy misconfigured (`vite.config.js`).
4. Read the backend terminal (Uvicorn prints each request and status).

### 12.3 FastAPI validation error (422)
1. Response body `detail` is a list of `{loc, msg, type}`. `apiRequest` joins `msg`s for display.
2. Compare the JSON you send with the schema in `modules/<x>/schemas.py` (lengths, patterns, `extra="forbid"` → "extra fields not permitted").
3. FastAPI's auto docs at `/docs` **[general; enabled by default unless disabled — not disabled in `app/main.py`]** let you test routes manually.

### 12.4 Authentication / authorization failure
| Status + message | Where it comes from | Likely cause |
|---|---|---|
| 401 "Your session is invalid or has expired." | `dependencies/auth.py` / `get_authenticated_user` | Missing/invalid/expired token, or user ID no longer exists |
| 401 "Invalid username or password." | `auth/service.login` | Bad credentials |
| 403 "This account is not active…" | `auth/service`, `users/service` | `AccountStatus` ≠ `ACTIVE` |
| 403 "This company is inactive." / "…not assigned to a company." | `validate_role_company` | Company status or missing `CompanyID` |
| 403 "Platform Super Admin access is required." | `require_super_admin` | Wrong role for companies/users APIs |
| 403 "An authorized company inventory role is required." | `require_company_user` | Super Admin or role not in allowed set calling inventory |

Steps: check the token exists in DevTools → Application → Session Storage (`gbms_access_token`); decode it **[general: jwt.io style tools — never paste real production tokens into third-party sites]**; query the user's row (`Users` join `Roles`, `Companies`) to confirm role/company/status.

### 12.5 SQL Server connection error
- Message: **503 "Database is unavailable. Check the GBMS database connection settings."** (from `get_connection`).
- Check `.env`: `DB_SERVER`, `DB_NAME`, `DB_DRIVER` (must match an installed ODBC driver), `DB_USER/DB_PASSWORD` or Windows auth; confirm SQL Server service is running and reachable. The underlying `pyodbc.Error` is chained (`from exc`) so it appears in the Uvicorn traceback/log.

### 12.6 Failed database query
- 409 messages come from unique-index violations (2601/2627) mapped in `_integrity_error`.
- 500 "Could not save…" means an unexpected integrity/DB error. For users, `logger.exception(...)` writes the traceback to the server log ("Check the server log"). For companies/inventory there is no logging; the Uvicorn console traceback is your clue.
- Reproduce in SSMS by running the same SELECT with real values **[general]**.

### 12.7 Company-data isolation problem
1. Confirm the logged-in user's `company_id` via `GET /api/v1/auth/me`.
2. Check every query you add includes `WHERE CompanyID = ?` and receives `user["company_id"]`.
3. Look at `Users.CompanyID`, `Products.CompanyID`, `ProductCategories.CompanyID` rows directly in SQL.
4. Run the existing tests: `tests/test_company_inventory.py` covers category scoping and client-tenant rejection **[V that tests exist; running them is general advice: from the backend folder, `python -m unittest`]**.

---

## 13. API endpoint reference

All paths are prefixed with `/api/v1` unless noted. "DB" = the main database operation. Status = success code.

| # | Method | Path | Purpose | Request | Response | Auth | Authorization | DB operation |
|---|---|---|---|---|---|---|---|---|
| 0 | GET | `/health` (no prefix) | Liveness | — | `{"status":"ok"}` | none | none | none |
| 1 | POST | `/auth/login` | Log in | `LoginPayload{username, password}` | `{access_token, token_type, expires_in, user}` | none | none | SELECT Users+Roles+Companies |
| 2 | GET | `/auth/me` | Current user | — | user dict | Bearer | any active user | SELECT by UserID |
| 3 | GET | `/dashboard` | Authenticated welcome | — | `{message, user}` | Bearer | any active user | SELECT by UserID |
| 4 | GET | `/companies` | List companies | query: `search`(≤120), `limit`(1–100, def 25), `offset`(≥0) | `{items,total,limit,offset}` | Bearer | SUPER_ADMIN | COUNT + SELECT paged |
| 5 | POST | `/companies` | Create company | `CompanyCreate` | company dict (201) | Bearer | SUPER_ADMIN | INSERT…OUTPUT |
| 6 | GET | `/companies/{company_id}` | Get company | path `>0` | company dict | Bearer | SUPER_ADMIN | SELECT |
| 7 | PUT | `/companies/{company_id}` | Update (partial) | `CompanyUpdate` | company dict | Bearer | SUPER_ADMIN | UPDATE…OUTPUT |
| 8 | PATCH | `/companies/{company_id}/status` | Activate/deactivate | `{company_status}` | company dict | Bearer | SUPER_ADMIN | UPDATE…OUTPUT |
| 9 | GET | `/companies/{company_id}/users` | List accounts | — | `{items:[user…]}` | Bearer | SUPER_ADMIN | SELECT Companies, SELECT Users+Roles |
| 10 | POST | `/companies/{company_id}/users` | Create account | `CompanyUserCreate` | user dict (201) | Bearer | SUPER_ADMIN | SELECT company, role; INSERT Users |
| 11 | GET | `/inventory/categories` | List own categories | — | `[{category_id, category_name, description}]` | Bearer | company roles | SELECT … WHERE CompanyID |
| 12 | POST | `/inventory/categories` | Create category | `CompanyCategoryCreate` | category dict (201) | Bearer | company roles | INSERT…OUTPUT |
| 13 | GET | `/inventory/units` | List active units | — | `[{unit_id, unit_code, unit_name, symbol}]` | Bearer | company roles | SELECT UnitsOfMeasure |
| 14 | GET | `/inventory/products` | List products | `search`, `category_id`, `limit`, `offset` | `{items,total,limit,offset}` | Bearer | company roles | COUNT + SELECT (CompanyID-scoped) |
| 15 | POST | `/inventory/products` | Create product | `ProductCreate` | product dict (201) | Bearer | company roles | INSERT…OUTPUT, SELECT |
| 16 | GET | `/inventory/products/{product_id}` | Get product | — | product dict | Bearer | company roles | SELECT (CompanyID-scoped) |
| 17 | PUT | `/inventory/products/{product_id}` | Update (partial) | `ProductUpdate` | product dict | Bearer | company roles | UPDATE, SELECT |
| 18 | PATCH | `/inventory/products/{product_id}/status` | Activate/deactivate | `{is_active}` | product dict | Bearer | company roles | UPDATE, SELECT |

**Company roles** = `COMPANY_ADMIN`, `SUB_ADMIN`, `INVENTORY_USER` (and the user must have a `company_id`).

**Request schemas summary**

- `LoginPayload`: `username` 1–80, `password` 1–1024.
- `CompanyCreate`: `company_name` ≤160, `company_code` 2–30 (pattern), optional `email`, `phone` ≤40, `address` ≤400.
- `CompanyUpdate`: same fields, all optional.
- `CompanyUserCreate`: `username`, `full_name`, `email`, `password` (12–128), `role_name`.
- `CompanyCategoryCreate`: `category_name` ≤100, optional `description` ≤300.
- `ProductCreate`: `sku`, `product_name`, `product_type`, `unit_id`, optional `category_id`, `description` ≤1000, `reorder_level`.

---

## 14. Known incomplete features, duplicates and risks

**Incomplete / not implemented [V]**
- Modules marked "Coming soon": Production, Purchasing, Sales, Employees, Finance, Assets, Reports, Settings.
- Inventory has **no stock levels, movements, warehouses, or delete**.
- Dashboard has no data; landing page numbers are static samples.
- Topbar search and notifications bell do nothing.
- No user edit/deactivate, password change/reset, or logout endpoint.
- No per-user permission model beyond three role names.

**Duplicated or confusing code [V]**
- `queryString()` is copy-pasted in `companyService.js` and `inventoryService.js`.
- `TOKEN_KEY` is defined in both `AuthContext.jsx` and `authService.js`.
- `CompaniesPage` and `InventoryPage` each contain a `loadX` callback **and** a nearly identical fetch inside `useEffect`.
- `authService.js` is both the auth API and the shared HTTP client.
- `authContext.js` vs `AuthContext.jsx` differ only by case/extension.
- `roles/service.get_role_id` merely wraps the repository function.
- Frontend regex/patterns duplicate backend patterns (company code, SKU).
- `seed_admin.py` message mentions `auth_schema.sql`, which does not exist in the project (the file is `Auth Query.sql`).

**Risks:** see §11 (security) and the `.env.local` base-URL note.

---

## 15. Teaching plan and Lesson 1

### 15.1 Lesson plan (adjusted to your code)

| # | Lesson | Status |
|---|---|---|
| 1 | Architecture, folders, **startup and how components connect** | ✅ below |
| 2 | Frontend startup and routing in depth | next |
| 3 | Backend startup and API registration | |
| 4 | SQL Server connection and database structure | |
| 5 | Login flow end-to-end | |
| 6 | JWT validation and protected routes | |
| 7 | Dashboard and authenticated requests | |
| 8 | Logout and session persistence | |
| 9 | Company management | |
| 10 | Company users, roles, permissions | |
| 11 | Inventory | |
| 12 | Cross-module dependencies, errors, debugging | |
| 13 | Security review and architecture improvements | |

### 15.2 Lesson 1 — How the app starts and connects

**Frontend startup (`src/main.jsx`)**

```jsx
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
```

- `createRoot(...)` — React takes control of `<div id="root">`.
- `StrictMode` — dev-only checks (runs effects twice to expose bugs).
- `BrowserRouter` — makes `Routes`, `Navigate`, `useNavigate` work.
- `AuthProvider` — supplies login state to everything inside it. Remove it and the first `useAuth()` call throws (`useAuth.js`).
- Analogy: the nesting is like building layers of a power supply — `App` can only use "electricity" (router, auth) that the outer layers provide.

**Backend startup (`app/main.py`)** — see Flow 1.

**The connection:** every `fetch('/api/v1/...')` goes to the Vite dev server, which proxies to FastAPI on port 8000. FastAPI sees the same request as if it came directly. Because the browser considers it same-origin, CORS is not exercised in this dev setup. [I]

### 15.3 Lesson 1 questions

1. In `main.jsx`, `AuthProvider` wraps `<App />`. What happens to `ProtectedRoute` if `AuthProvider` is removed, and which file/line produces the error?
2. A product list request starts in `InventoryPage`. Write the **full URL path** it calls, and name the two backend places where `/api/v1` and `/inventory` come from.
3. If `JWT_SECRET_KEY` is missing from `.env`, **when** does the failure happen (startup or first login), and why is that a good design?

### 15.4 Answer key (check after you try)

1. `ProtectedRoute` calls `useAuth()`, which runs `useContext(AuthContext)`; with no provider it returns `null`, so `useAuth.js` throws `"useAuth must be used inside AuthProvider"` (line 7) and the app crashes on render.
2. `/api/v1/inventory/products`. `/api/v1` comes from `app.include_router(inventory_router, prefix="/api/v1")` in `app/main.py`; `/inventory` comes from `APIRouter(prefix="/inventory", ...)` in `inventory/router.py`; `/products` from `@router.get("/products")`. The frontend string is in `inventoryService.js`.
3. At **server startup**, when `app.core.config` is first imported (it raises `RuntimeError`). Failing early prevents running with an insecure/placeholder signing secret.

---

*End of guide. Continue with Lesson 2 whenever you're ready.*
