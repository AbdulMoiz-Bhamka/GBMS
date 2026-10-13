<!-- GBMSunderstanding.md -->
# GBMS Authentication Flow --- Understanding Guide

> **Purpose:** This document explains the authentication system that
> currently exists in the uploaded GBMS project.
>
> **Important:** This guide is based on the actual files in the uploaded
> `GBMS.zip`. It explains what the code currently does; it does not
> silently replace it with a different architecture.

## 1. What is already built?

The current authentication flow is:

``` text
GBMS Landing Page
      |
      | Login form
      v
React LoginPopover
      |
      | authContext.login()
      v
AuthContext
      |
      | authService.login()
      v
POST /api/v1/auth/login
      |
      v
FastAPI
      |
      | SQL query by username
      v
SQL Server: Users + Roles
      |
      | PasswordHash
      v
Argon2 password verification
      |
      | success
      v
FastAPI creates JWT
      |
      v
React stores JWT in sessionStorage
      |
      v
React navigates to /dashboard
      |
      v
ProtectedRoute
      |
      | GET /api/v1/auth/me
      v
FastAPI verifies JWT
      |
      v
SQL Server verifies that the user still exists and is ACTIVE
      |
      v
Dashboard
      |
      | GET /api/v1/dashboard with Bearer JWT
      v
FastAPI verifies JWT again
      |
      v
Dashboard receives authenticated user
```

There are **three different ideas** working together:

1.  **Authentication** --- username/password proves who the user is.
2.  **JWT session** --- FastAPI gives React a signed access token after
    successful login.
3.  **Authorization/protection** --- protected endpoints require a valid
    JWT and an ACTIVE database account.

The database also contains the foundation for roles through `Roles` and
`Users.RoleID`.

------------------------------------------------------------------------

# 2. The project files involved in authentication

Only the authentication-related files are important for understanding
the current flow.

``` text
GBMS/
│
├── React (FrontEnd)/
│   └── GBMS/
│       └── src/
│           ├── App.jsx
│           ├── main.jsx
│           │
│           ├── auth/
│           │   ├── authContext.js
│           │   ├── AuthContext.jsx
│           │   ├── ProtectedRoute.jsx
│           │   └── useAuth.js
│           │
│           ├── services/
│           │   └── authService.js
│           │
│           └── pages/
│               └── Dashboard.jsx
│
├── FastAPI (BackEnd)/
│   ├── main.py
│   ├── seed_admin.py
│   ├── .env
│   ├── .env.example
│   └── requirements.txt
│
└── SQL Server Query/
    └── Auth Query.sql
```

A notable point about the current implementation is that `main.py`
contains the backend configuration, database connection, password
verification, JWT functions, dependencies, and routes all in one file.
That is acceptable for this current authentication milestone, but it is
something we can refactor into the planned layered architecture later.

------------------------------------------------------------------------

# 3. The most important mental model

## Company access and company administrators

Creating a company creates its workspace record; it does not automatically create a login. A platform `SUPER_ADMIN` opens **Company management → Accounts** for the company, then creates the first user with the `COMPANY_ADMIN` role. The admin username and password are the values entered in that form. The password is stored as an Argon2 hash and is never returned by the API.

The company administrator signs in on the regular GBMS login screen with that username and password. After login, the company user's account is linked to the company's database ID, and inventory requests are limited to that company. A company account cannot access platform company management. A Super Admin can use the same Accounts panel to create `SUB_ADMIN` or `INVENTORY_USER` accounts as needed.

New company users can only be created for an active company. Use a unique username/email and a password of at least 12 characters. Share the initial password with the user securely; password reset/change is not yet implemented.

### Calling protected APIs in FastAPI docs

The API expects a JWT in `Authorization: Bearer <token>` for protected routes. In `/docs`, first call `POST /api/v1/auth/login` with the JSON username/password and copy the `access_token` from the response. Select **Authorize**, paste the token value (without adding the word `Bearer`), and confirm. FastAPI adds the Bearer prefix to requests. Without this step, protected endpoints correctly return HTTP 401. The Swagger security scheme is HTTP Bearer because the login endpoint accepts JSON rather than OAuth2 form fields.

In local development, Vite proxies `/api` and `/health` requests to FastAPI at `http://127.0.0.1:8000`; this avoids browser CORS issues when the frontend is opened at either `http://localhost:5173` or `http://127.0.0.1:5173`. Start FastAPI on that address (`python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000`) and restart Vite after changing its config or `.env.local`. `/health` checks API availability without requiring a token.

Before reading individual lines, remember this:

### React does NOT authenticate the user.

React collects the username/password and sends them to FastAPI.

### FastAPI does NOT store the user's account.

SQL Server stores the account.

### SQL Server does NOT create the JWT.

FastAPI creates the JWT after SQL Server lookup + password verification
succeeds.

### The JWT does NOT contain the user's password.

It identifies the user and proves that FastAPI issued the token.

### The frontend does NOT decide whether a protected API is allowed.

FastAPI verifies the JWT and checks the database.

That gives us:

``` text
React
  = interface

FastAPI
  = authentication authority + API

SQL Server
  = application data / user records

JWT
  = signed proof of an authenticated session
```

------------------------------------------------------------------------

# 4. Database first: SQL Server

File:

``` text
GBMS/SQL Server Query/Auth Query.sql
```

## Line-by-line explanation

### Lines 1--4

``` sql
IF DB_ID(N'GBMS') IS NULL
    CREATE DATABASE [GBMS];
GO
```

**Line 1**

`DB_ID(N'GBMS')` asks SQL Server for the database ID of `GBMS`.

If the database does not exist, SQL Server returns `NULL`.

So this means:

> "Does the GBMS database already exist?"

**Line 2**

If it does not exist, create it.

**Line 4**

`GO` is a batch separator understood by SQL Server tooling. It tells the
SQL client to execute the previous batch.

------------------------------------------------------------------------

### Lines 6--7

``` sql
USE [GBMS];
GO
```

`USE [GBMS]` changes the active database.

Everything after this operates against the `GBMS` database unless
another database is selected.

------------------------------------------------------------------------

# 5. Roles table

### Lines 9--19

``` sql
IF OBJECT_ID(N'dbo.Roles', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Roles
    (
        RoleID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Roles PRIMARY KEY,
        RoleName NVARCHAR(50) NOT NULL CONSTRAINT UQ_Roles_RoleName UNIQUE,
        Description NVARCHAR(250) NULL,
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Roles_CreatedAt DEFAULT SYSUTCDATETIME()
    );
END;
GO
```

**Line 9**

Checks whether a user table named `dbo.Roles` exists.

`N'U'` means SQL Server user table.

**Line 10**

Starts the conditional block.

**Line 11**

Begins the table definition.

### `RoleID`

``` sql
RoleID INT IDENTITY(1,1) NOT NULL
```

-   `INT` = integer
-   `IDENTITY(1,1)` = SQL Server automatically generates IDs starting at
    1 and increments by 1.
-   `NOT NULL` = this field cannot be empty.

``` sql
CONSTRAINT PK_Roles PRIMARY KEY
```

Makes `RoleID` the primary key.

So:

``` text
SUPER_ADMIN → RoleID 1
```

could exist.

### `RoleName`

``` sql
RoleName NVARCHAR(50) NOT NULL
```

Stores names such as:

``` text
SUPER_ADMIN
SUB_ADMIN
ACCOUNTANT
EMPLOYEE
```

The UNIQUE constraint means two roles cannot have the same name.

### `Description`

Optional explanation of the role.

### `CreatedAt`

Stores when the role was created.

``` sql
DEFAULT SYSUTCDATETIME()
```

means SQL Server automatically supplies the UTC timestamp when no value
is provided.

------------------------------------------------------------------------

# 6. Users table

### Lines 21--42

The `Users` table is the actual authentication account table.

``` sql
CREATE TABLE dbo.Users
(
    UserID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Users PRIMARY KEY,
    Username NVARCHAR(80) NOT NULL,
    FullName NVARCHAR(160) NOT NULL,
    Email NVARCHAR(254) NOT NULL,
    PasswordHash NVARCHAR(255) NOT NULL,
    RoleID INT NOT NULL,
    AccountStatus NVARCHAR(20) NOT NULL
        CONSTRAINT DF_Users_AccountStatus DEFAULT N'ACTIVE',
    CreatedAt DATETIME2(0) NOT NULL
        CONSTRAINT DF_Users_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt DATETIME2(0) NOT NULL
        CONSTRAINT DF_Users_UpdatedAt DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_Users_Roles FOREIGN KEY (RoleID)
        REFERENCES dbo.Roles(RoleID),
    CONSTRAINT CK_Users_AccountStatus CHECK
        (AccountStatus IN (N'ACTIVE', N'INACTIVE', N'SUSPENDED'))
);
```

### `UserID`

Unique identifier for each user.

``` text
UserID
1
2
3
...
```

### `Username`

The username used during login.

### `FullName`

The name displayed in GBMS.

This is why the dashboard can say:

``` text
Welcome, Abdul Moiz
```

without putting the full name into the password/token system.

### `Email`

The account email.

### `PasswordHash`

This is one of the most important columns.

It does **not** contain:

``` text
mypassword123
```

It contains an Argon2 password hash.

Conceptually:

``` text
Password entered
      |
      v
Argon2
      |
      v
PasswordHash
```

### `RoleID`

This connects the user to the `Roles` table.

Relationship:

``` text
Users.RoleID
      |
      v
Roles.RoleID
```

For example:

``` text
User: Abdul
RoleID: 1
      |
      v
Roles
RoleID: 1
RoleName: SUPER_ADMIN
```

### `AccountStatus`

Controls whether the account can currently authenticate.

Allowed values:

``` text
ACTIVE
INACTIVE
SUSPENDED
```

This is important because a valid JWT should not automatically mean the
account remains authorized forever.

### `CreatedAt`

When the account was created.

### `UpdatedAt`

When the account was last updated.

### Foreign key

``` sql
CONSTRAINT FK_Users_Roles FOREIGN KEY (RoleID)
    REFERENCES dbo.Roles(RoleID)
```

This tells SQL Server:

> A user's `RoleID` must correspond to an actual role.

You cannot safely create a user pointing to role ID 999 if role 999 does
not exist.

### Account status CHECK

``` sql
CHECK (AccountStatus IN (...))
```

Prevents invalid status values.

For example:

``` text
ACTIVE       ✓
INACTIVE     ✓
SUSPENDED    ✓
WHATEVER     ✗
```

------------------------------------------------------------------------

# 7. Unique username and email

The script then creates unique indexes.

``` sql
CREATE UNIQUE INDEX UQ_Users_Username
ON dbo.Users(Username);
```

This means:

``` text
admin
```

cannot exist twice.

The email index does the same for email addresses.

------------------------------------------------------------------------

# 8. Creating the Super Admin role

``` sql
IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE RoleName = N'SUPER_ADMIN')
    INSERT INTO dbo.Roles (RoleName, Description)
    VALUES (N'SUPER_ADMIN', N'Full access to the GBMS workspace');
```

This asks:

> Does `SUPER_ADMIN` already exist?

If not, create it.

This is the first role in the current authentication foundation.

The complete RBAC permission system has not been built yet.

------------------------------------------------------------------------

# 9. Final SQL query

``` sql
Select * from Users;
```

This is simply a developer verification query.

It lets you open SQL Server and see the current users.

It is **not** called by React or FastAPI automatically.

------------------------------------------------------------------------

# 10. How the initial Admin is created

File:

``` text
FastAPI (BackEnd)/seed_admin.py
```

This is important because there is intentionally no public signup.

The initial administrator is created through this controlled seed
process.

## Line by line

``` python
from getpass import getpass
```

Allows password input without showing the password in the terminal.

``` python
import pyodbc
```

Allows the script to connect to SQL Server.

``` python
from argon2 import PasswordHasher
```

Uses the same secure hashing algorithm as the API.

``` python
from main import DB_NAME, DB_SERVER, DB_DRIVER, DB_USER, DB_PASSWORD
```

Reuses the backend's database configuration.

------------------------------------------------------------------------

### Input

``` python
username = input('Admin username: ').strip()
```

Gets the username.

`.strip()` removes accidental spaces around it.

``` python
full_name = input('Admin full name: ').strip()
```

Gets the display name.

``` python
email = input('Admin email: ').strip()
```

Gets email.

``` python
password = getpass('Admin password: ')
```

Gets the password without displaying it.

------------------------------------------------------------------------

### Validation

``` python
if not username or not full_name or not email or len(password) < 12:
```

Requires all fields and at least a 12-character password.

------------------------------------------------------------------------

### Connection

The script uses the same SQL Server configuration as the API.

------------------------------------------------------------------------

### Password hashing

``` python
hashed = PasswordHasher().hash(password)
```

This is critical.

If the administrator enters:

``` text
MyStrongPassword123
```

SQL Server receives something like an Argon2 hash, not the original
password.

------------------------------------------------------------------------

### Find Super Admin role

``` sql
SELECT RoleID
FROM dbo.Roles
WHERE RoleName='SUPER_ADMIN'
```

This gets the role's database ID.

------------------------------------------------------------------------

### Insert user

``` sql
IF NOT EXISTS (SELECT 1 FROM dbo.Users WHERE Username=?)
    INSERT dbo.Users
    (Username, FullName, Email, PasswordHash, RoleID, AccountStatus)
    VALUES (?, ?, ?, ?, ?, 'ACTIVE')
```

The `?` symbols are pyodbc parameter placeholders.

The Python values are passed separately.

This is important because parameterized SQL is much safer than
constructing SQL by concatenating user input.

------------------------------------------------------------------------

# 11. FastAPI configuration

File:

``` text
FastAPI (BackEnd)/main.py
```

Now we reach the heart of the authentication system.

## Imports

``` python
import os
```

Reads environment variables.

``` python
from datetime import datetime, timedelta, timezone
```

Used for JWT timestamps.

``` python
from pathlib import Path
```

Used to locate `.env`.

``` python
import jwt
```

PyJWT.

``` python
import pyodbc
```

SQL Server connection.

``` python
from argon2 import PasswordHasher
```

Password hashing/verification.

``` python
from dotenv import load_dotenv
```

Loads `.env`.

``` python
from fastapi import Depends, FastAPI, HTTPException, status
```

FastAPI framework and dependency/error tools.

``` python
from fastapi.middleware.cors import CORSMiddleware
```

Allows React to call FastAPI from another development origin.

``` python
from fastapi.security import OAuth2PasswordBearer
```

Extracts Bearer tokens from the Authorization header.

``` python
from pydantic import BaseModel, Field
```

Validates the login body.

------------------------------------------------------------------------

# 12. Environment configuration

``` python
load_dotenv(Path(__file__).with_name('.env'))
```

This loads:

``` text
FastAPI (BackEnd)/.env
```

into environment variables.

The application then reads:

``` python
JWT_SECRET = os.getenv('JWT_SECRET_KEY', '')
```

This is the secret used to sign JWTs.

``` python
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
```

Currently the configured algorithm is HS256.

``` python
TOKEN_MINUTES = int(os.getenv('ACCESS_TOKEN_MINUTES', '30'))
```

The token lifetime is 30 minutes by default.

Database variables:

``` python
DB_SERVER
DB_NAME
DB_DRIVER
DB_USER
DB_PASSWORD
```

tell FastAPI how to reach SQL Server.

------------------------------------------------------------------------

# 13. JWT secret safety check

``` python
if not JWT_SECRET or JWT_SECRET == 'replace-with-a-long-random-secret':
    raise RuntimeError(...)
```

This is a very good defensive check.

If you accidentally start the server without a real JWT secret, the
application refuses to start.

Why?

Because otherwise someone could guess the secret and forge GBMS tokens.

------------------------------------------------------------------------

# 14. Password hashing object

``` python
password_hasher = PasswordHasher()
```

This object performs:

``` text
hash(password)
verify(hash, password)
```

The actual hashing algorithm is Argon2.

------------------------------------------------------------------------

# 15. Bearer token extraction

``` python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')
```

This does not perform the login itself.

It tells FastAPI:

> When a protected endpoint needs a token, look for a Bearer token in
> the Authorization header.

Example:

``` http
Authorization: Bearer eyJhbGciOi...
```

------------------------------------------------------------------------

# 16. FastAPI application

``` python
app = FastAPI(title='GBMS API', version='1.0.0')
```

Creates the application.

------------------------------------------------------------------------

# 17. CORS

``` python
allowed_origins = [...]
```

Reads allowed frontend origins.

Then:

``` python
app.add_middleware(CORSMiddleware, ...)
```

allows the React application to communicate with FastAPI.

Without CORS configuration, the browser could block the request even
though FastAPI itself is working.

------------------------------------------------------------------------

# 18. SQL Server connection

``` python
def get_connection():
```

Creates one centralized function for opening SQL Server connections.

If SQL credentials exist:

``` python
UID=...
PWD=...
```

Otherwise:

``` text
Trusted_Connection=yes
```

is used.

Then:

``` python
pyodbc.connect(...)
```

actually opens the SQL Server connection.

------------------------------------------------------------------------

# 19. `public_user()`

``` python
def public_user(row):
    return {
        'user_id': row[0],
        'username': row[1],
        'full_name': row[2],
        'email': row[3],
        'role_name': row[4]
    }
```

This function is important for security.

The database row contains:

``` text
UserID
Username
FullName
Email
RoleName
AccountStatus
PasswordHash
```

But the frontend should never receive:

``` text
PasswordHash
```

So `public_user()` converts the DB result into the safe version.

------------------------------------------------------------------------

# 20. Login request validation

``` python
class LoginPayload(BaseModel):
```

Defines the expected login JSON.

``` python
username: str = Field(min_length=1, max_length=80)
```

Username must be a string and cannot be empty.

``` python
password: str = Field(min_length=1, max_length=1024)
```

Password must also be supplied.

So React sends:

``` json
{
  "username": "admin",
  "password": "..."
}
```

FastAPI converts it into a `LoginPayload`.

------------------------------------------------------------------------

# 21. JWT creation

``` python
def make_token(user):
```

This creates the access token.

``` python
now = datetime.now(timezone.utc)
```

Gets current UTC time.

Then:

``` python
jwt.encode({
    'sub': str(user['user_id']),
    'iat': now,
    'exp': now + timedelta(minutes=TOKEN_MINUTES),
    'type': 'access'
}, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

The JWT contains:

### `sub`

Subject.

In GBMS:

``` text
sub = UserID
```

Example:

``` text
sub = "1"
```

### `iat`

Issued At.

When was this JWT created?

### `exp`

Expiration.

When should this JWT stop working?

### `type`

Custom GBMS claim:

``` text
access
```

This helps distinguish the access token from other possible token types
later.

------------------------------------------------------------------------

# 22. The most important function: `get_current_user()`

``` python
def get_current_user(token: str = Depends(oauth2_scheme)):
```

This is the protection mechanism for the API.

FastAPI first gets the Bearer token.

Then:

``` python
jwt.decode(...)
```

verifies:

-   signature
-   algorithm
-   required claims
-   expiration

If anything is wrong:

``` text
401 Unauthorized
```

The code then reads:

``` python
user_id = int(claims['sub'])
```

So the JWT says:

``` text
sub = 1
```

and FastAPI interprets that as:

``` text
UserID = 1
```

------------------------------------------------------------------------

# 23. Why query SQL Server again?

This is extremely important.

After validating the JWT, the backend executes:

``` sql
SELECT
    u.UserID,
    u.Username,
    u.FullName,
    u.Email,
    r.RoleName,
    u.AccountStatus
FROM dbo.Users u
JOIN dbo.Roles r
    ON r.RoleID=u.RoleID
WHERE u.UserID=?
```

Why?

Because the JWT alone does not prove that the user account is still
active.

Imagine:

``` text
10:00
User logs in
JWT created
```

Then:

``` text
10:05
Admin suspends user
```

If FastAPI trusted only the JWT, the user could potentially continue
making requests until the token expires.

Instead:

``` text
JWT
 ↓
UserID
 ↓
SQL Server
 ↓
Current account status
```

So:

``` text
ACTIVE → allow
INACTIVE → deny
SUSPENDED → deny
```

That is a very important part of your current design.

------------------------------------------------------------------------

# 24. Login endpoint

``` python
@app.post('/api/v1/auth/login')
```

This creates:

``` text
POST /api/v1/auth/login
```

React calls this endpoint.

FastAPI receives:

``` json
{
  "username": "admin",
  "password": "..."
}
```

------------------------------------------------------------------------

## SQL login query

The query joins:

``` text
Users
   |
   | RoleID
   v
Roles
```

and retrieves:

``` text
UserID
Username
FullName
Email
RoleName
AccountStatus
PasswordHash
```

The username is passed as a parameter:

``` text
WHERE u.Username=?
```

This is parameterized SQL.

------------------------------------------------------------------------

# 25. Password verification

This line is the heart of password authentication:

``` python
password_hasher.verify(row[6], payload.password)
```

Remember:

``` text
row[6] = PasswordHash
payload.password = password typed by user
```

Argon2 checks whether they match.

If they don't:

``` text
401 Invalid username or password
```

The same message is returned when the username does not exist.

That avoids unnecessarily revealing whether a username exists.

------------------------------------------------------------------------

# 26. Account status check

After password verification:

``` python
if row[5] != 'ACTIVE':
```

If the account is:

``` text
INACTIVE
```

or:

``` text
SUSPENDED
```

authentication is rejected.

------------------------------------------------------------------------

# 27. Successful login

``` python
user = public_user(row)
```

Creates the safe user object.

Then:

``` python
return {
    'access_token': make_token(user),
    'token_type': 'bearer',
    'expires_in': TOKEN_MINUTES * 60,
    'user': user
}
```

FastAPI sends the JWT back to React.

Conceptually:

``` json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "user_id": 1,
    "username": "admin",
    "full_name": "Admin",
    "email": "...",
    "role_name": "SUPER_ADMIN"
  }
}
```

------------------------------------------------------------------------

# 28. `/auth/me`

``` python
@app.get('/api/v1/auth/me')
def me(user=Depends(get_current_user)):
    return user
```

The important part is:

``` python
Depends(get_current_user)
```

FastAPI executes:

``` text
get_current_user()
```

before `me()`.

So `/auth/me` cannot simply be called by an unauthenticated browser.

The dependency verifies the JWT first.

------------------------------------------------------------------------

# 29. Dashboard API

``` python
@app.get('/api/v1/dashboard')
def dashboard(user=Depends(get_current_user)):
```

Again:

``` text
JWT required
```

Then:

``` python
return {
    'message': 'You have authenticated access to the GBMS workspace.',
    'user': user
}
```

This is intentionally simple right now.

It exists to prove that:

``` text
React → JWT → FastAPI → protected endpoint
```

works.

------------------------------------------------------------------------

# 30. React application startup

File:

``` text
src/main.jsx
```

The important lines are:

``` jsx
<BrowserRouter>
    <AuthProvider>
        <App />
    </AuthProvider>
</BrowserRouter>
```

The hierarchy is:

``` text
BrowserRouter
   |
   └── AuthProvider
          |
          └── App
```

This matters because every component inside `AuthProvider` can use:

``` javascript
useAuth()
```

to access authentication state.

------------------------------------------------------------------------

# 31. `authContext.js`

``` javascript
import { createContext } from 'react'

export const AuthContext = createContext(null)
```

This creates the shared authentication container.

Think of Context as a central React state channel:

``` text
AuthProvider
     |
     +-- Landing/Login
     |
     +-- ProtectedRoute
     |
     +-- Dashboard
```

All of them can access the same authentication state.

------------------------------------------------------------------------

# 32. `AuthContext.jsx`

This is the frontend authentication manager.

The most important state is:

``` javascript
const [token, setToken] = useState(...)
```

and:

``` javascript
const [user, setUser] = useState(null)
```

So React knows:

``` text
token = JWT
user = authenticated user's information
```

------------------------------------------------------------------------

# 33. Why `sessionStorage`?

``` javascript
sessionStorage.getItem(TOKEN_KEY)
```

The current implementation stores the access token in browser session
storage.

`sessionStorage` survives page navigation and reloads within the current
tab/session, but is cleared when the tab/session ends.

The code uses:

``` text
gbms_access_token
```

as the key.

Important security note:

`sessionStorage` is accessible to JavaScript, so an XSS vulnerability
could expose the token. For a future production-grade deployment, we
should evaluate an HttpOnly secure-cookie session architecture. For the
current learning/development milestone, the important thing is that
token handling is centralized rather than scattered across components.

------------------------------------------------------------------------

# 34. Token re-validation on page refresh

This is one of the most useful parts of the current code.

Suppose you refresh:

``` text
/dashboard
```

React reads the JWT from `sessionStorage`.

But it does NOT immediately assume:

> "I am authenticated."

Instead:

``` javascript
authService.me(token)
```

calls:

``` text
GET /api/v1/auth/me
```

with:

``` http
Authorization: Bearer <JWT>
```

FastAPI verifies it.

If valid:

``` text
user returned
```

If invalid:

``` text
token removed
user cleared
```

This is why `isLoading` exists.

------------------------------------------------------------------------

# 35. Login function

Inside `AuthProvider`:

``` javascript
const login = useCallback(async (credentials) => {
    const result = await authService.login(credentials)
    sessionStorage.setItem(TOKEN_KEY, result.access_token)
    setToken(result.access_token)
    setUser(result.user)
}, [])
```

Flow:

``` text
Login form
   ↓
login(credentials)
   ↓
authService.login()
   ↓
FastAPI
   ↓
JWT
   ↓
result.access_token
   ↓
sessionStorage
   ↓
React token state
   ↓
React user state
```

------------------------------------------------------------------------

# 36. Logout

``` javascript
sessionStorage.removeItem(TOKEN_KEY)
```

Deletes the browser token.

Then:

``` javascript
setToken(null)
setUser(null)
```

clears React authentication state.

After that, the dashboard cannot pass the authentication guard.

------------------------------------------------------------------------

# 37. `useAuth.js`

``` javascript
export function useAuth() {
    const context = useContext(AuthContext)
```

This is a convenience hook.

Instead of doing:

``` javascript
useContext(AuthContext)
```

everywhere, components can simply do:

``` javascript
const { user, token, login, logout } = useAuth()
```

The safety check:

``` javascript
if (!context) throw new Error(...)
```

makes sure the hook is only used under `AuthProvider`.

------------------------------------------------------------------------

# 38. `authService.js`

This file is the bridge between React and FastAPI.

``` javascript
const API_BASE =
    (import.meta.env.VITE_API_BASE_URL ||
    'http://127.0.0.1:8000').replace(/\/$/, '')
```

It reads the FastAPI URL from Vite configuration.

If no environment variable exists, it uses:

``` text
http://127.0.0.1:8000
```

------------------------------------------------------------------------

## Generic request function

``` javascript
async function request(path, { token, ...options } = {})
```

This prevents you from repeating fetch configuration in every API
function.

For example:

``` javascript
authService.me(token)
```

ultimately becomes:

``` text
GET http://127.0.0.1:8000/api/v1/auth/me
Authorization: Bearer <token>
```

------------------------------------------------------------------------

# 39. Authorization header

The important code is:

``` javascript
...(token ? {
    Authorization: `Bearer ${token}`
} : {}),
```

If a token exists:

``` http
Authorization: Bearer eyJhbGci...
```

is sent.

FastAPI's:

``` python
OAuth2PasswordBearer
```

extracts that token.

So these two files are directly connected:

``` text
React authService.js
        |
        | Authorization: Bearer JWT
        v
FastAPI OAuth2PasswordBearer
```

------------------------------------------------------------------------

# 40. `authService` endpoints

``` javascript
login:
    POST /api/v1/auth/login
```

Authenticates.

``` javascript
me:
    GET /api/v1/auth/me
```

Verifies the current session and returns the user.

``` javascript
dashboard:
    GET /api/v1/dashboard
```

Calls the protected dashboard API.

So:

``` text
authService.js
      |
      +── /auth/login
      |
      +── /auth/me
      |
      └── /dashboard
```

matches the FastAPI routes in `main.py`.

------------------------------------------------------------------------

# 41. The Login UI in `App.jsx`

The authentication-relevant component is:

``` javascript
function LoginPopover({ open, onClose }) {
```

It controls the login form.

It gets the login function:

``` javascript
const { login } = useAuth()
```

and navigation:

``` javascript
const navigate = useNavigate()
```

------------------------------------------------------------------------

## Form submission

The important sequence is:

``` javascript
event.preventDefault()
```

Prevents the browser's normal form submission.

``` javascript
const formData = new FormData(event.currentTarget)
```

Reads the form fields.

Then:

``` javascript
await login({
    username: formData.get('username'),
    password: formData.get('password')
})
```

calls the authentication context.

This is the exact chain:

``` text
LoginPopover
     ↓
AuthContext.login()
     ↓
authService.login()
     ↓
fetch()
     ↓
POST /api/v1/auth/login
```

After successful login:

``` javascript
onClose()
navigate('/dashboard')
```

closes the login panel and changes the route.

If login fails:

``` javascript
setMessage(error.message)
```

displays the backend error.

------------------------------------------------------------------------

# 42. The protected route

In `App.jsx`:

``` jsx
<Route element={<ProtectedRoute />}>
    <Route path="/dashboard" element={<DashboardPage />} />
</Route>
```

This means:

``` text
/dashboard
     |
     v
ProtectedRoute
     |
     +-- authenticated → DashboardPage
     |
     └-- not authenticated → /
```

------------------------------------------------------------------------

# 43. `ProtectedRoute.jsx`

The code gets:

``` javascript
const { user, isLoading } = useAuth()
```

If authentication is still being checked:

``` text
Loading workspace…
```

If a verified user exists:

``` jsx
<Outlet />
```

renders the nested dashboard.

If not:

``` jsx
<Navigate to="/" replace />
```

sends the user back to the landing page.

This is frontend route protection.

But remember:

> This is NOT the actual security boundary.

The real security boundary is still FastAPI.

Someone could bypass React and call the API directly. That is why the
backend also verifies JWTs.

------------------------------------------------------------------------

# 44. Dashboard flow

`Dashboard.jsx` gets:

``` javascript
const { token, user, logout } = useAuth()
```

Then:

``` javascript
authService.dashboard(token)
```

calls:

``` text
GET /api/v1/dashboard
```

with the Bearer token.

FastAPI:

``` text
JWT
 ↓
decode
 ↓
verify signature
 ↓
check expiration
 ↓
get UserID
 ↓
SQL Server
 ↓
check user exists
 ↓
check ACTIVE
 ↓
return user
```

Then React displays:

``` jsx
Welcome, {user?.full_name || user?.username}
```

and:

``` jsx
Role: {user?.role_name}
```

------------------------------------------------------------------------

# 45. Complete authentication flow --- memorize this

This is the most important part of the whole document.

## A. Initial account creation

``` text
seed_admin.py
       |
       v
Ask for admin credentials
       |
       v
Argon2 hashes password
       |
       v
SQL Server
       |
       +── Roles
       |
       └── Users
```

There is no public signup.

------------------------------------------------------------------------

## B. Login

``` text
Landing Page
      |
      v
LoginPopover
      |
      v
useAuth().login()
      |
      v
AuthContext.login()
      |
      v
authService.login()
      |
      v
POST /api/v1/auth/login
      |
      v
FastAPI
      |
      v
SELECT Users + Roles
      |
      v
Argon2.verify()
      |
      v
Account ACTIVE?
      |
      v
Create JWT
      |
      v
React
```

------------------------------------------------------------------------

## C. JWT

The JWT contains:

``` text
sub
iat
exp
type
```

For example:

``` text
sub = "1"
iat = ...
exp = ...
type = "access"
```

The important part is:

``` text
sub = UserID
```

It tells the backend which GBMS user the token represents.

------------------------------------------------------------------------

## D. Protected dashboard

``` text
React
  |
  | Authorization: Bearer JWT
  v
FastAPI
  |
  v
get_current_user()
  |
  +── jwt.decode()
  |
  +── verify signature
  |
  +── verify expiration
  |
  +── extract UserID
  |
  v
SQL Server
  |
  +── user exists?
  |
  +── account ACTIVE?
  |
  v
Dashboard response
```

------------------------------------------------------------------------

# 46. Why both frontend and backend protection exist

You might wonder:

> If `ProtectedRoute` already protects `/dashboard`, why does FastAPI
> need JWT verification?

Because the browser is not trusted.

Someone could skip React entirely and send:

``` http
GET /api/v1/dashboard
```

from Postman.

Therefore:

``` text
Frontend protection
= user experience

Backend protection
= actual security
```

This distinction is extremely important for your future ERP.

------------------------------------------------------------------------

# 47. Authentication vs authorization in your current code

Your current system has **authentication** and the beginning of
**authorization**, but not full RBAC yet.

### Authentication currently implemented

``` text
Username
Password
Password hash
JWT
JWT verification
Account status
Protected routes
```

### Role foundation exists

``` text
Roles
Users.RoleID
RoleName
```

### Full authorization is NOT implemented yet

We do not yet have:

``` text
Permissions
RolePermissions
permission checks
Admin user creation
Sub-admin permissions
module-level access
```

That should be the next security layer after you fully understand this
code.

------------------------------------------------------------------------

# 48. Important current limitations to understand

These are observations about the uploaded code, not changes we are
making right now.

### 1. `main.py` is doing many jobs

Currently it contains:

``` text
configuration
DB connection
security
JWT
authentication
dependencies
routes
```

For learning this is easier to see in one place.

Later we can separate it into:

``` text
core/
db/
models/
schemas/
services/
api/
dependencies/
```

as the GBMS architecture grows.

### 2. `sessionStorage` is the current token storage

This is convenient for the current development milestone, but it is
accessible to JavaScript. We should revisit production session
storage/security later.

### 3. Full RBAC does not exist yet

`SUPER_ADMIN` exists as a role, but the actual permission system is
still to be built.

### 4. User creation dashboard does not exist yet

The current `seed_admin.py` is the controlled way to create the first
admin.

The next feature will eventually allow the Super Admin to create users
through GBMS itself.

------------------------------------------------------------------------

# 49. Packages used by authentication

## Backend

From `requirements.txt`:

``` text
fastapi
```

Web API framework.

``` text
uvicorn
```

Runs the FastAPI application.

``` text
pyodbc
```

Connects Python to SQL Server.

``` text
python-dotenv
```

Loads `.env`.

``` text
PyJWT
```

Creates and verifies JWTs.

``` text
argon2-cffi
```

Provides Argon2 password hashing.

## Frontend

Relevant dependencies include:

``` text
react
react-dom
react-router-dom
```

React UI + routing.

And:

``` text
lucide-react
```

for interface icons.

------------------------------------------------------------------------

# 50. One simple analogy

Think of GBMS like your university LMS.

### SQL Server

is the university's student/account database.

### Username/password

are your LMS credentials.

### FastAPI

is the security desk checking those credentials.

### JWT

is the temporary access badge issued after successful login.

### React dashboard

is the university portal you can enter after getting the badge.

### Protected API

is the security guard checking the badge every time you request
something restricted.

### Role

is your position/access category.

Later:

``` text
Student
Teacher
Admin
Registrar
```

will become analogous to:

``` text
Employee
Manager
Sub Admin
Super Admin
```

And permissions determine what each role can actually do.

------------------------------------------------------------------------

# 51. The single most important chain to memorize

If you understand this, you understand the current authentication
architecture:

``` text
                         SQL SERVER
                       ┌─────────────┐
                       │   Users     │
                       │   Roles     │
                       │ PasswordHash│
                       └──────┬──────┘
                              │
                              │
Landing Page                  │
     │                        │
     ▼                        │
Login Form                    │
     │                        │
     ▼                        │
authContext.login()           │
     │                        │
     ▼                        │
authService.login()           │
     │                        │
     ▼                        │
POST /auth/login ─────────────┘
     │
     ▼
FastAPI
     │
     ├── Find user
     ├── Verify Argon2 password
     ├── Check ACTIVE
     │
     ▼
Create JWT
     │
     ▼
React sessionStorage
     │
     ▼
/dashboard
     │
     ▼
ProtectedRoute
     │
     ▼
GET /auth/me
     │
     ▼
FastAPI JWT verification
     │
     ▼
SQL Server user/status verification
     │
     ▼
Authenticated User
     │
     ▼
Dashboard
```

**If you can draw this flow yourself on paper and explain every arrow,
you have understood the authentication foundation of GBMS.**

------------------------------------------------------------------------

# 52. Recommended learning order before we build anything else

Do NOT jump into the next GBMS module yet.

Learn this in this order:

1.  **SQL Server**
    -   `Roles`
    -   `Users`
    -   primary key
    -   foreign key
    -   unique index
    -   CHECK constraint
2.  **Password hashing**
    -   plaintext vs hash
    -   Argon2
    -   hash vs verify
3.  **FastAPI**
    -   request body
    -   endpoint
    -   dependency
    -   HTTP status codes
4.  **JWT**
    -   header
    -   payload
    -   signature
    -   `sub`
    -   `iat`
    -   `exp`
    -   signing vs verification
5.  **React Context**
    -   Provider
    -   Context
    -   custom hook
    -   state
6.  **Protected routes**
    -   React route protection
    -   backend API protection
7.  **Full request lifecycle**
    -   Browser
    -   React
    -   FastAPI
    -   SQL Server
    -   FastAPI
    -   JWT
    -   React

Only after you are comfortable with those should we build:

``` text
Super Admin
     ↓
User Management
     ↓
Create User
     ↓
Assign Role
     ↓
New User Login
```

That will be the natural next stage of GBMS.

# Appendix A --- Exact line-by-line explanation: `main.py`

The following is the actual `main.py` content from the uploaded project,
with an explanation for each line. Blank lines are marked as `(blank)`
so the numbering remains aligned.

### Line 1

``` python
# main.py
```

A comment naming this module. This file is currently the main FastAPI
application file, so it contains configuration, DB access, JWT helpers,
auth endpoints, and the dashboard endpoint.

### Line 2

``` python
import os
```

Imports Python's `os` module so environment variables can be read.

### Line 3

``` python
from datetime import datetime, timedelta, timezone
```

Imports `datetime`, `timedelta`, and `timezone` for creating JWT
timestamps such as `iat` and `exp`.

### Line 4

``` python
from pathlib import Path
```

Imports `Path` so the code can build the path to the `.env` file
reliably.

### Line 5

``` python
```

### Line 6

``` python
import jwt
```

Imports the PyJWT library as `jwt`. It creates and verifies the signed
JWTs used by GBMS.

### Line 7

``` python
import pyodbc
```

Imports `pyodbc`, the Python driver used to connect FastAPI to Microsoft
SQL Server.

### Line 8

``` python
from argon2 import PasswordHasher
```

Imports Argon2's `PasswordHasher`, which is used to hash passwords and
verify submitted passwords against stored hashes.

### Line 9

``` python
from argon2.exceptions import VerificationError, VerifyMismatchError
```

Imports the Argon2 verification exceptions used when a password does not
match or a hash cannot be verified.

### Line 10

``` python
from dotenv import load_dotenv
```

Imports `load_dotenv`, which loads variables from the backend `.env`
file into the process environment.

### Line 11

``` python
from fastapi import Depends, FastAPI, HTTPException, status
```

Imports FastAPI classes. `FastAPI` creates the app, `Depends` injects
dependencies such as the current user, `HTTPException` sends controlled
HTTP errors, and `status` provides HTTP status constants.

### Line 12

``` python
from fastapi.middleware.cors import CORSMiddleware
```

Imports FastAPI's CORS middleware so the React development server is
allowed to call the FastAPI server.

### Line 13

``` python
from fastapi.security import OAuth2PasswordBearer
```

Imports `OAuth2PasswordBearer`, which extracts a Bearer token from the
`Authorization` header and makes it available to FastAPI dependencies.

### Line 14

``` python
from pydantic import BaseModel, Field
```

Imports Pydantic's `BaseModel` and `Field` for validating the login
request body.

### Line 15

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 16

``` python
load_dotenv(Path(__file__).with_name('.env'))
```

Loads `.env` from the same directory as `main.py`. This is how the JWT
secret and SQL Server settings become available through `os.getenv()`.

### Line 17

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 18

``` python
JWT_SECRET = os.getenv('JWT_SECRET_KEY', '')
```

Reads `JWT_SECRET_KEY`. This secret signs and later verifies GBMS JWTs.
It must be private.

### Line 19

``` python
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
```

Reads the JWT signing algorithm, defaulting to HS256 if the variable is
absent.

### Line 20

``` python
TOKEN_MINUTES = int(os.getenv('ACCESS_TOKEN_MINUTES', '30'))
```

Reads the access-token lifetime in minutes, defaulting to 30 minutes.

### Line 21

``` python
DB_SERVER = os.getenv('DB_SERVER', r'AbdulMoiz\sqlserver16')
```

Reads the SQL Server host/instance name.

### Line 22

``` python
DB_NAME = os.getenv('DB_NAME', 'GBMS')
```

Reads the SQL Server database name, defaulting to `GBMS`.

### Line 23

``` python
DB_DRIVER = os.getenv('DB_DRIVER', 'ODBC Driver 18 for SQL Server')
```

Reads the installed ODBC driver name.

### Line 24

``` python
DB_USER = os.getenv('DB_USER', '')
```

Reads optional SQL Server username. If blank, the application uses
Windows/Trusted authentication.

### Line 25

``` python
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
```

Reads optional SQL Server password.

### Line 26

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 27

``` python
if not JWT_SECRET or JWT_SECRET == 'replace-with-a-long-random-secret':
```

Checks that a real JWT secret has been configured.

### Line 28

``` python
    raise RuntimeError('Set JWT_SECRET_KEY to a private random value in FastAPI (BackEnd)/.env')
```

Stops startup with a clear error if the JWT secret is missing or still
the example placeholder. This prevents the app from accidentally running
with a known secret.

### Line 29

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 30

``` python
password_hasher = PasswordHasher()
```

Creates one Argon2 password-hashing helper that can hash and verify
passwords.

### Line 31

``` python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')
```

Creates a FastAPI OAuth2 bearer-token extractor. It expects an
`Authorization: Bearer <token>` header and documents the login endpoint
as the token URL.

### Line 32

``` python
app = FastAPI(title='GBMS API', version='1.0.0')
```

Creates the FastAPI application object and gives it a title and version.

### Line 33

``` python
allowed_origins = [origin.strip() for origin in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if origin.strip()]
```

Reads comma-separated allowed frontend origins from the environment and
converts them into a Python list.

### Line 34

``` python
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])
```

Adds CORS middleware. Only the configured origins are allowed,
credentials are enabled, and only GET/POST plus
Authorization/Content-Type are allowed.

### Line 35

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 36

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 37

``` python
def get_connection():
```

Defines the central SQL Server connection function used by the API.

### Line 38

``` python
    if DB_USER and DB_PASSWORD:
```

Checks whether SQL authentication credentials were supplied.

### Line 39

``` python
        auth = f'UID={DB_USER};PWD={DB_PASSWORD};'
```

Builds SQL-authentication connection parameters when username and
password are present.

### Line 40

``` python
    else:
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 41

``` python
        auth = 'Trusted_Connection=yes;'
```

Otherwise selects Windows/Trusted Connection authentication.

### Line 42

``` python
    connection_string = f'DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};{auth}TrustServerCertificate=yes;'
```

Builds the ODBC connection string, including server, database,
authentication mode, and `TrustServerCertificate=yes`.

### Line 43

``` python
    try:
```

Starts a small error-handling block around the DB connection.

### Line 44

``` python
        return pyodbc.connect(connection_string, timeout=5)
```

Opens the SQL Server connection with a five-second timeout.

### Line 45

``` python
    except pyodbc.Error as exc:
```

Catches pyodbc connection errors.

### Line 46

``` python
        raise HTTPException(status_code=503, detail='Database is unavailable. Check the GBMS database connection settings.') from exc
```

Converts a DB connection failure into an HTTP 503 response instead of
exposing the raw database exception.

### Line 47

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 48

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 49

``` python
def public_user(row):
```

Defines a helper that converts a database user row into the safe user
object returned to the frontend.

### Line 50

``` python
    return {'user_id': row[0], 'username': row[1], 'full_name': row[2], 'email': row[3], 'role_name': row[4]}
```

Maps the selected SQL columns to JSON-friendly names. Notice that
`PasswordHash` is deliberately not returned.

### Line 51

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 52

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 53

``` python
class LoginPayload(BaseModel):
```

Defines the shape of the login request body.

### Line 54

``` python
    username: str = Field(min_length=1, max_length=80)
```

Requires a username between 1 and 80 characters.

### Line 55

``` python
    password: str = Field(min_length=1, max_length=1024)
```

Requires a password between 1 and 1024 characters.

### Line 56

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 57

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 58

``` python
def make_token(user):
```

Defines the function that creates a GBMS access token.

### Line 59

``` python
    now = datetime.now(timezone.utc)
```

Gets the current UTC time.

### Line 60

``` python
    return jwt.encode({'sub': str(user['user_id']), 'iat': now, 'exp': now + timedelta(minutes=TOKEN_MINUTES), 'type': 'access'}, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

Creates a signed JWT containing the user ID (`sub`), issued-at time
(`iat`), expiration (`exp`), and token type, then signs it with the
configured secret and algorithm.

### Line 61

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 62

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 63

``` python
def get_current_user(token: str = Depends(oauth2_scheme)):
```

Defines the protected-user dependency. Any endpoint using
`Depends(get_current_user)` automatically requires a valid Bearer JWT.

### Line 64

``` python
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Your session is invalid or has expired.', headers={'WWW-Authenticate': 'Bearer'})
```

Creates the standard 401 error used for missing, invalid, or expired
sessions and includes the Bearer authentication challenge header.

### Line 65

``` python
    try:
```

Starts JWT decoding error handling.

### Line 66

``` python
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={'require': ['sub', 'iat', 'exp', 'type']})
```

Decodes and verifies the token signature, checks the configured
algorithm, and requires the `sub`, `iat`, `exp`, and `type` claims.

### Line 67

``` python
        if claims.get('type') != 'access':
```

Reads the custom token type claim.

### Line 68

``` python
            raise unauthorized
```

Rejects the token if it is not an access token.

### Line 69

``` python
        user_id = int(claims['sub'])
```

Converts the JWT subject into the integer SQL Server UserID.

### Line 70

``` python
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
```

Catches JWT errors and invalid subject values.

### Line 71

``` python
        raise unauthorized from exc
```

Raises the standard unauthorized response instead of leaking token
details.

### Line 72

``` python
    with get_connection() as connection:
```

Opens a SQL Server connection while the current-user lookup is
performed.

### Line 73

``` python
        row = connection.cursor().execute('''SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName, u.AccountStatus
```

Starts the SQL query joining Users to Roles so the backend can
reconstruct the authenticated user's safe identity.

### Line 74

``` python
            FROM dbo.Users u JOIN dbo.Roles r ON r.RoleID=u.RoleID WHERE u.UserID=?''', user_id).fetchone()
```

Finishes the query: match the user ID from the JWT against
`Users.UserID`. The `?` is a pyodbc parameter placeholder, so `user_id`
is passed safely rather than string-concatenated.

### Line 75

``` python
    if not row:
```

Checks whether the database returned a user.

### Line 76

``` python
        raise unauthorized
```

Rejects the JWT if the referenced user no longer exists.

### Line 77

``` python
    if row[5] != 'ACTIVE':
```

Checks the current database account status.

### Line 78

``` python
        raise HTTPException(status_code=403, detail='This account is not active. Contact your administrator.')
```

Blocks inactive/suspended accounts even if their JWT has not expired.

### Line 79

``` python
    return public_user(row)
```

Returns the safe public-user object to the protected endpoint.

### Line 80

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 81

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 82

``` python
@app.get('/health')
```

Defines a simple health-check endpoint.

### Line 83

``` python
def health():
```

Handles GET `/health`.

### Line 84

``` python
    return {'status': 'ok'}
```

Returns a small JSON response proving the API process is alive.

### Line 85

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 86

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 87

``` python
@app.post('/api/v1/auth/login')
```

Defines the login endpoint at `POST /api/v1/auth/login`.

### Line 88

``` python
def login(payload: LoginPayload):
```

FastAPI parses and validates the JSON request into the `LoginPayload`
object.

### Line 89

``` python
    with get_connection() as connection:
```

Opens SQL Server for the login lookup.

### Line 90

``` python
        row = connection.cursor().execute('''SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
```

Starts the login SELECT. It retrieves user identity fields and joins the
user's role.

### Line 91

``` python
            u.AccountStatus, u.PasswordHash FROM dbo.Users u JOIN dbo.Roles r ON r.RoleID=u.RoleID
```

Also selects account status and the password hash. The hash is needed
only internally for verification.

### Line 92

``` python
            WHERE u.Username=?''', payload.username.strip()).fetchone()
```

Finds the row by username using a parameterized query.

### Line 93

``` python
    if not row:
```

Checks whether the username was found.

### Line 94

``` python
        raise HTTPException(status_code=401, detail='Invalid username or password.')
```

Returns the same generic error for an unknown username as for a wrong
password.

### Line 95

``` python
    try:
```

Starts password verification error handling.

### Line 96

``` python
        password_hasher.verify(row[6], payload.password)
```

Argon2 verifies the submitted password against the stored password hash.

### Line 97

``` python
    except (VerifyMismatchError, VerificationError, ValueError):
```

Catches password mismatch/verification errors.

### Line 98

``` python
        raise HTTPException(status_code=401, detail='Invalid username or password.')
```

Returns the same generic 401 response so attackers do not learn whether
a username exists.

### Line 99

``` python
    if row[5] != 'ACTIVE':
```

Checks whether the account is active after the password is correct.

### Line 100

``` python
        raise HTTPException(status_code=403, detail='This account is not active. Contact your administrator.')
```

Returns 403 when the account is not active.

### Line 101

``` python
    user = public_user(row)
```

Converts the DB row into the safe user object.

### Line 102

``` python
    return {'access_token': make_token(user), 'token_type': 'bearer', 'expires_in': TOKEN_MINUTES * 60, 'user': user}
```

Returns the JWT, token type, lifetime, and safe user data to React.

### Line 103

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 104

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 105

``` python
@app.get('/api/v1/auth/me')
```

Defines the authenticated-user endpoint `GET /api/v1/auth/me`.

### Line 106

``` python
def me(user=Depends(get_current_user)):
```

Requires `get_current_user`; FastAPI therefore verifies the Bearer JWT
before this function runs.

### Line 107

``` python
    return user
```

Returns the authenticated user's safe information.

### Line 108

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 109

``` python
```

This line is part of the surrounding code block; its purpose follows
directly from the neighboring lines described above.

### Line 110

``` python
@app.get('/api/v1/dashboard')
```

Defines the protected dashboard endpoint.

### Line 111

``` python
def dashboard(user=Depends(get_current_user)):
```

Again requires a valid JWT and returns the authenticated user.

### Line 112

``` python
    return {'message': 'You have authenticated access to the GBMS workspace.', 'user': user}
```

Returns a small dashboard response proving the protected authentication
chain works.

# Appendix B --- Exact line-by-line explanation: `seed_admin.py`

### Line 1

``` python
from getpass import getpass
```

Imports `getpass` so the admin password can be entered without being
echoed to the terminal.

### Line 2

``` python
```

This line closes or continues the surrounding Python statement described
above.

### Line 3

``` python
import pyodbc
```

Imports pyodbc for direct SQL Server access during the one-time seed
operation.

### Line 4

``` python
from argon2 import PasswordHasher
```

Imports the same Argon2 password hasher used by the API.

### Line 5

``` python
```

This line closes or continues the surrounding Python statement described
above.

### Line 6

``` python
from main import DB_NAME, DB_SERVER, DB_DRIVER, DB_USER, DB_PASSWORD
```

Imports the database configuration values from `main.py` so the seed
script connects to the same GBMS database.

### Line 7

``` python
```

This line closes or continues the surrounding Python statement described
above.

### Line 8

``` python
```

This line closes or continues the surrounding Python statement described
above.

### Line 9

``` python
def main():
```

Defines the seed script's main function.

### Line 10

``` python
    username = input('Admin username: ').strip()
```

Prompts for the initial admin username.

### Line 11

``` python
    full_name = input('Admin full name: ').strip()
```

Prompts for the admin's display name.

### Line 12

``` python
    email = input('Admin email: ').strip()
```

Prompts for the admin email.

### Line 13

``` python
    password = getpass('Admin password: ')
```

Prompts for the password without displaying it.

### Line 14

``` python
    if not username or not full_name or not email or len(password) < 12:
```

Validates that all required values exist and requires a password of at
least 12 characters.

### Line 15

``` python
        raise SystemExit('Enter all fields and use a password of at least 12 characters.')
```

Stops with an explanatory message if the seed input is invalid.

### Line 16

``` python
    auth = f'UID={DB_USER};PWD={DB_PASSWORD};' if DB_USER and DB_PASSWORD else 'Trusted_Connection=yes;'
```

Chooses SQL authentication when credentials are present, otherwise
Windows Trusted Connection.

### Line 17

``` python
    connection = pyodbc.connect(f'DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};{auth}TrustServerCertificate=yes;')
```

Opens the SQL Server connection using the same server/database/driver
settings as the API.

### Line 18

``` python
    hashed = PasswordHasher().hash(password)
```

Hashes the password with Argon2 before it is stored. The plain password
is never written to SQL Server.

### Line 19

``` python
    with connection:
```

Begins the connection context so the transaction/connection is managed
safely.

### Line 20

``` python
        cursor = connection.cursor()
```

Creates a database cursor for executing SQL.

### Line 21

``` python
        cursor.execute("SELECT RoleID FROM dbo.Roles WHERE RoleName='SUPER_ADMIN'")
```

Looks up the `SUPER_ADMIN` role ID.

### Line 22

``` python
        role = cursor.fetchone()
```

Reads the role row returned by SQL Server.

### Line 23

``` python
        if not role:
```

Checks that the required role exists.

### Line 24

``` python
            raise SystemExit('SUPER_ADMIN role is missing. Run auth_schema.sql first.')
```

Stops and tells the developer to run the schema script if the role is
missing.

### Line 25

``` python
        cursor.execute('''IF NOT EXISTS (SELECT 1 FROM dbo.Users WHERE Username=?)
```

Starts a conditional insert: only insert if this username does not
already exist.

### Line 26

``` python
            INSERT dbo.Users (Username, FullName, Email, PasswordHash, RoleID, AccountStatus)
```

Specifies the Users columns being inserted.

### Line 27

``` python
            VALUES (?, ?, ?, ?, ?, 'ACTIVE')''', username, username, full_name, email, hashed, role[0])
```

Inserts the username, name, email, Argon2 hash, role ID, and ACTIVE
status. The `?` placeholders are bound to the following Python
arguments.

### Line 28

``` python
        if cursor.rowcount == 0:
```

Checks whether an INSERT actually occurred.

### Line 29

``` python
            print('That username already exists; no changes were made.')
```

Reports that the username already exists when nothing was inserted.

### Line 30

``` python
        else:
```

This line closes or continues the surrounding Python statement described
above.

### Line 31

``` python
            print('Super administrator created.')
```

Reports successful Super Admin creation.

### Line 32

``` python
```

This line closes or continues the surrounding Python statement described
above.

### Line 33

``` python
```

This line closes or continues the surrounding Python statement described
above.

### Line 34

``` python
if __name__ == '__main__':
```

Standard Python entry-point guard: only execute `main()` when this file
is run directly.

### Line 35

``` python
    main()
```

This line closes or continues the surrounding Python statement described
above.

# Appendix C --- Exact line-by-line explanation: `AuthContext.jsx`

### Line 1

``` jsx
import { useCallback, useEffect, useMemo, useState } from 'react'
```

Imports React hooks used by the authentication provider: `useCallback`
for stable functions, `useEffect` for session validation, `useMemo` for
the context value, and `useState` for auth state.

### Line 2

``` jsx
import { authService } from '../services/authService'
```

Imports the centralized `authService`, which is responsible for making
HTTP requests to FastAPI.

### Line 3

``` jsx
import { AuthContext } from './authContext'
```

Imports the React context object created in `authContext.js`.

### Line 4

``` jsx
```

This line closes or continues the surrounding authentication-provider
code.

### Line 5

``` jsx
const TOKEN_KEY = 'gbms_access_token'
```

Defines the key used by `sessionStorage` to store the access token.

### Line 6

``` jsx
```

This line closes or continues the surrounding authentication-provider
code.

### Line 7

``` jsx
export function AuthProvider({ children }) {
```

Defines `AuthProvider`, the component that makes authentication state
available to the entire React tree.

### Line 8

``` jsx
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY))
```

Initializes `token` from `sessionStorage`. If the browser tab already
has a token, React starts with that token.

### Line 9

``` jsx
  const [user, setUser] = useState(null)
```

Initializes `user` as unknown until `/auth/me` verifies the token and
returns the current user.

### Line 10

``` jsx
  const [isLoading, setIsLoading] = useState(Boolean(sessionStorage.getItem(TOKEN_KEY)))
```

If a token exists, starts in loading state because the app must verify
it with the backend before trusting it.

### Line 11

``` jsx
```

This line closes or continues the surrounding authentication-provider
code.

### Line 12

``` jsx
  useEffect(() => {
```

Runs whenever `token` changes.

### Line 13

``` jsx
    if (!token) return
```

If there is no token, there is nothing to verify, so the effect stops.

### Line 14

``` jsx
    let active = true
```

Creates an `active` flag to avoid updating React state after the effect
has been cleaned up.

### Line 15

``` jsx
    authService.me(token).then((data) => {
```

Calls the backend `/auth/me` through `authService` using the stored
token.

### Line 16

``` jsx
      if (active) setUser(data)
```

If the component is still active, saves the verified user returned by
the backend.

### Line 17

``` jsx
    }).catch(() => {
```

If verification fails, removes the stale token and clears authentication
state.

### Line 18

``` jsx
      sessionStorage.removeItem(TOKEN_KEY)
```

When verification finishes, clears the loading state.

### Line 19

``` jsx
      if (active) { setToken(null); setUser(null) }
```

Marks the effect as inactive during cleanup.

### Line 20

``` jsx
    }).finally(() => { if (active) setIsLoading(false) })
```

Closes the effect and declares `token` as its dependency.

### Line 21

``` jsx
    return () => { active = false }
```

This line closes or continues the surrounding authentication-provider
code.

### Line 22

``` jsx
  }, [token])
```

Defines the login function exposed to components.

### Line 23

``` jsx
```

Calls the FastAPI login endpoint through `authService`.

### Line 24

``` jsx
  const login = useCallback(async (credentials) => {
```

Stores the returned access token in `sessionStorage`.

### Line 25

``` jsx
    const result = await authService.login(credentials)
```

Copies the token into React state.

### Line 26

``` jsx
    sessionStorage.setItem(TOKEN_KEY, result.access_token)
```

Copies the backend-returned user object into React state.

### Line 27

``` jsx
    setToken(result.access_token)
```

Keeps the login function stable because it has no changing dependencies.

### Line 28

``` jsx
    setUser(result.user)
```

This line closes or continues the surrounding authentication-provider
code.

### Line 29

``` jsx
  }, [])
```

Defines logout.

### Line 30

``` jsx
```

Removes the token from the current browser tab's session storage.

### Line 31

``` jsx
  const logout = useCallback(() => {
```

Clears the token from React state.

### Line 32

``` jsx
    sessionStorage.removeItem(TOKEN_KEY)
```

Clears the current user from React state.

### Line 33

``` jsx
    setToken(null)
```

Keeps the logout function stable.

### Line 34

``` jsx
    setUser(null)
```

This line closes or continues the surrounding authentication-provider
code.

### Line 35

``` jsx
  }, [])
```

Builds the object exposed through React Context.

### Line 36

``` jsx
```

Provides authentication state and functions to every descendant
component.

### Line 37

``` jsx
  const value = useMemo(() => ({ token, user, isLoading, login, logout }), [token, user, isLoading, login, logout])
```

Closes the provider.

### Line 38

``` jsx
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
```

This line closes or continues the surrounding authentication-provider
code.

### Line 39

``` jsx
}
```

This line closes or continues the surrounding authentication-provider
code.

### Line 40

``` jsx
```

This line closes or continues the surrounding authentication-provider
code.

# Appendix D --- Exact line-by-line explanation: `authContext.js`

### Line 1

``` javascript
import { createContext } from 'react'
```

Imports React's `createContext` function.

### Line 2

``` javascript
```

This line is part of the small context definition described above.

### Line 3

``` javascript
export const AuthContext = createContext(null)
```

Creates the shared authentication context. `null` is the initial value
so `useAuth` can detect misuse outside the provider.

# Appendix E --- Exact line-by-line explanation: `useAuth.js`

### Line 1

``` javascript
import { useContext } from 'react'
```

Imports React's `useContext`.

### Line 2

``` javascript
import { AuthContext } from './authContext'
```

Imports the shared `AuthContext`.

### Line 3

``` javascript
```

This line belongs to the custom authentication hook.

### Line 4

``` javascript
export function useAuth() {
```

Defines a small custom hook so components can access authentication
without importing the context directly.

### Line 5

``` javascript
  const context = useContext(AuthContext)
```

Reads the current context.

### Line 6

``` javascript
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
```

Throws a helpful error if a component tries to use authentication
outside `AuthProvider`.

### Line 7

``` javascript
  return context
```

Returns the context value.

### Line 8

``` javascript
}
```

This line belongs to the custom authentication hook.

# Appendix F --- Exact line-by-line explanation: `ProtectedRoute.jsx`

### Line 1

``` jsx
import { Navigate, Outlet } from 'react-router-dom'
```

Imports `Navigate` for redirects and `Outlet` for rendering the nested
protected route.

### Line 2

``` jsx
import { useAuth } from './useAuth'
```

Imports the project's `useAuth` hook.

### Line 3

``` jsx
```

This line is part of the protected route logic.

### Line 4

``` jsx
export default function ProtectedRoute() {
```

Defines the route guard component.

### Line 5

``` jsx
  const { user, isLoading } = useAuth()
```

Reads `user` and `isLoading` from the authentication context.

### Line 6

``` jsx
  if (isLoading) return <main className="grid min-h-screen place-items-center bg-slate-50 text-slate-600">Loading workspace…</main>
```

While the stored token is being verified with FastAPI, shows a loading
screen instead of prematurely redirecting.

### Line 7

``` jsx
  return user ? <Outlet /> : <Navigate to="/" replace />
```

Once loading is complete, renders the nested route if a verified user
exists; otherwise redirects to `/`.

### Line 8

``` jsx
}
```

This line is part of the protected route logic.

# Appendix G --- Exact line-by-line explanation: `authService.js`

### Line 1

``` javascript
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
```

Reads the API base URL from Vite's environment variables, with a local
FastAPI fallback.

### Line 2

``` javascript
```

Defines a reusable HTTP helper and destructures the optional JWT token
from the options.

### Line 3

``` javascript
async function request(path, { token, ...options } = {}) {
```

Declares a variable that will hold the fetch response.

### Line 4

``` javascript
  let response
```

Starts network-error handling.

### Line 5

``` javascript
  try {
```

Calls the requested FastAPI endpoint and builds the request headers.

### Line 6

``` javascript
    response = await fetch(`${API_BASE}${path}`, {
```

Adds JSON content type only when a request body exists.

### Line 7

``` javascript
      ...options,
```

Adds `Authorization: Bearer <token>` when a token was supplied.

### Line 8

``` javascript
      headers: {
```

Allows caller-supplied headers to override earlier headers.

### Line 9

``` javascript
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
```

Closes the fetch call.

### Line 10

``` javascript
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
```

Catches network failures.

### Line 11

``` javascript
        ...options.headers,
```

Converts the browser's generic fetch TypeError into a useful GBMS
server-unavailable message.

### Line 12

``` javascript
      },
```

Rethrows other errors.

### Line 13

``` javascript
    })
```

Closes the network error handling.

### Line 14

``` javascript
  } catch (error) {
```

Attempts to parse the response as JSON; if there is no JSON body, uses
an empty object.

### Line 15

``` javascript
    if (error instanceof TypeError) throw new Error('Cannot reach the GBMS server. Make sure FastAPI is running.', { cause: error })
```

Checks HTTP success status.

### Line 16

``` javascript
    throw error
```

Extracts the backend's `detail` message when it is a string, otherwise
uses a generic error.

### Line 17

``` javascript
  }
```

Creates a JavaScript Error containing the backend message.

### Line 18

``` javascript
  const body = await response.json().catch(() => ({}))
```

Attaches the HTTP status code to the error object.

### Line 19

``` javascript
  if (!response.ok) {
```

Throws the error so the caller can display it.

### Line 20

``` javascript
    const detail = typeof body.detail === 'string' ? body.detail : 'The request could not be completed.'
```

Returns the parsed JSON body for successful requests.

### Line 21

``` javascript
    const error = new Error(detail)
```

This line is part of the reusable HTTP/authentication service.

### Line 22

``` javascript
    error.status = response.status
```

This line is part of the reusable HTTP/authentication service.

### Line 23

``` javascript
    throw error
```

Exports the centralized authentication API methods.

### Line 24

``` javascript
  }
```

Calls `POST /api/v1/auth/login` with JSON credentials.

### Line 25

``` javascript
  return body
```

Calls `GET /api/v1/auth/me` with the JWT.

### Line 26

``` javascript
}
```

Calls `GET /api/v1/dashboard` with the JWT.

### Line 27

``` javascript
```

This line is part of the reusable HTTP/authentication service.

### Line 28

``` javascript
export const authService = {
```

This line is part of the reusable HTTP/authentication service.

### Line 29

``` javascript
  login: (credentials) => request('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
```

This line is part of the reusable HTTP/authentication service.

### Line 30

``` javascript
  me: (token) => request('/api/v1/auth/me', { token }),
```

This line is part of the reusable HTTP/authentication service.

### Line 31

``` javascript
  dashboard: (token) => request('/api/v1/dashboard', { token }),
```

This line is part of the reusable HTTP/authentication service.

### Line 32

``` javascript
}
```

This line is part of the reusable HTTP/authentication service.

# Appendix H --- Exact line-by-line explanation: `Dashboard.jsx`

### Line 1

``` jsx
import { useEffect, useState } from 'react'
```

Imports React hooks for loading the dashboard API response.

### Line 2

``` jsx
import { useNavigate } from 'react-router-dom'
```

Imports `useNavigate` for redirecting after logout.

### Line 3

``` jsx
import { LogOut, ShieldCheck } from 'lucide-react'
```

Imports two Lucide icons used by the dashboard UI.

### Line 4

``` jsx
import { useAuth } from '../auth/useAuth'
```

Imports authentication state and actions.

### Line 5

``` jsx
import { authService } from '../services/authService'
```

Imports the centralized API service.

### Line 6

``` jsx
```

This line belongs to the protected dashboard UI or its API request flow.

### Line 7

``` jsx
export default function DashboardPage() {
```

Gets the JWT, verified user, and logout function from the auth context.

### Line 8

``` jsx
  const { token, user, logout } = useAuth()
```

Gets React Router's navigation function.

### Line 9

``` jsx
  const navigate = useNavigate()
```

Creates state for the backend dashboard response.

### Line 10

``` jsx
  const [dashboard, setDashboard] = useState(null)
```

Creates state for displaying an API error.

### Line 11

``` jsx
  const [error, setError] = useState('')
```

Runs when the JWT changes and requests the protected dashboard endpoint.

### Line 12

``` jsx
  useEffect(() => {
```

Stores a successful dashboard response.

### Line 13

``` jsx
    authService.dashboard(token).then(setDashboard).catch((failure) => setError(failure.message))
```

Stores the error message if the protected API call fails.

### Line 14

``` jsx
  }, [token])
```

Closes the effect.

### Line 15

``` jsx
  const signOut = () => { logout(); navigate('/', { replace: true }) }
```

Defines sign-out: clear auth state, then replace the current route with
`/`.

### Line 16

``` jsx
```

This line belongs to the protected dashboard UI or its API request flow.

### Line 17

``` jsx
  return <main className="min-h-screen bg-slate-50 text-slate-800">
```

Renders the protected dashboard page.

### Line 18

``` jsx
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
```

Dashboard header.

### Line 19

``` jsx
      <a href="/" className="font-bold tracking-wide text-sky-800">GBMS <span className="font-normal text-slate-500">Workspace</span></a>
```

Uses a link back to the landing page and labels the workspace.

### Line 20

``` jsx
      <button onClick={signOut} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium hover:bg-slate-50"><LogOut size={16} /> Sign out</button>
```

Logout button calls `signOut`.

### Line 21

``` jsx
    </div></header>
```

This line belongs to the protected dashboard UI or its API request flow.

### Line 22

``` jsx
    <section className="mx-auto max-w-6xl px-6 py-12">
```

Main dashboard section.

### Line 23

``` jsx
      <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">Secure workspace</p>
```

Shows the security/workspace label.

### Line 24

``` jsx
      <h1 className="mt-2 text-3xl font-semibold">Welcome, {user?.full_name || user?.username}</h1>
```

Displays the user's `full_name`, falling back to `username`.

### Line 25

``` jsx
      <p className="mt-2 text-slate-500">Your GBMS account is signed in and ready.</p>
```

Explains that the account is authenticated.

### Line 26

``` jsx
      {error && <p role="alert" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-800">{error}</p>}
```

Displays an API error if the protected dashboard request failed.

### Line 27

``` jsx
      {dashboard && <div className="mt-8 grid gap-5 sm:grid-cols-2">
```

Only renders the dashboard cards after the protected endpoint returned
data.

### Line 28

``` jsx
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><ShieldCheck className="text-sky-600" /><h2 className="mt-4 font-semibold">Account access</h2><p className="mt-1 text-sm text-slate-500">{dashboard.message}</p></div>
```

Shows the server's dashboard message.

### Line 29

``` jsx
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-sm text-slate-500">Signed in as</p><p className="mt-2 text-lg font-semibold">{user?.username}</p><p className="mt-1 text-sm text-slate-500">Role: {user?.role_name}</p></div>
```

Shows the authenticated username and role from the verified user object.

### Line 30

``` jsx
      </div>}
```

Closes the dashboard component.

### Line 31

``` jsx
    </section>
```

This line belongs to the protected dashboard UI or its API request flow.

### Line 32

``` jsx
  </main>
```

This line belongs to the protected dashboard UI or its API request flow.

### Line 33

``` jsx
}
```

This line belongs to the protected dashboard UI or its API request flow.

# Appendix I --- Authentication-related lines from `App.jsx`

The uploaded `App.jsx` also contains the complete landing-page
presentation code. That visual code is not part of authentication, so
this appendix focuses on the lines that connect the landing page to
authentication and the protected dashboard.

### Line 8

``` jsx
import { useAuth } from './auth/useAuth'
```

Imports the authentication hook used by the login popover.

### Line 9

``` jsx
import ProtectedRoute from './auth/ProtectedRoute'
```

Imports the protected-route component that guards `/dashboard`.

### Line 52

``` jsx
function LoginPopover({ open, onClose }) {
```

Begins the login popover component.

### Line 53

``` jsx
  const ref = useRef(null)
```

Creates a DOM ref so outside-click detection can identify the login
panel.

### Line 54

``` jsx
  const [message, setMessage] = useState('')
```

Stores a user-facing login error/status message.

### Line 55

``` jsx
  const [isSubmitting, setIsSubmitting] = useState(false)
```

Tracks whether the login request is currently running.

### Line 56

``` jsx
  const { login } = useAuth()
```

Gets the shared `login()` function from AuthContext.

### Line 57

``` jsx
  const navigate = useNavigate()
```

Gets React Router navigation.

### Line 58

``` jsx
```

Authentication-related application wiring.

### Line 59

``` jsx
  useEffect(() => {
```

Runs when the popover opens or its close callback changes.

### Line 60

``` jsx
    if (!open) return undefined
```

Does nothing when the login panel is closed.

### Line 61

``` jsx
    const handlePointer = (event) => { if (ref.current && !ref.current.contains(event.target)) onClose() }
```

Closes the login panel when a pointer event happens outside its DOM
element.

### Line 62

``` jsx
    const handleKey = (event) => { if (event.key === 'Escape') onClose() }
```

Closes the panel when Escape is pressed.

### Line 63

``` jsx
    document.addEventListener('pointerdown', handlePointer)
```

Registers the outside-click listener.

### Line 64

``` jsx
    document.addEventListener('keydown', handleKey)
```

Registers the Escape-key listener.

### Line 65

``` jsx
    return () => {
```

Begins cleanup.

### Line 66

``` jsx
      document.removeEventListener('pointerdown', handlePointer)
```

Removes the pointer listener.

### Line 67

``` jsx
      document.removeEventListener('keydown', handleKey)
```

Removes the key listener.

### Line 68

``` jsx
    }
```

Closes cleanup.

### Line 69

``` jsx
  }, [open, onClose])
```

Declares effect dependencies.

### Line 70

``` jsx
```

Authentication-related application wiring.

### Line 71

``` jsx
  if (!open) return null
```

Does not render the login panel while it is closed.

### Line 72

``` jsx
  return <section ref={ref} role="dialog" aria-modal="false" className="login-panel card bg-base-100 shadow-xl" aria-labelledby="login-title">
```

Renders the actual login dialog.

### Line 73

``` jsx
    <div className="card-body gap-0 p-6">
```

Starts the dialog's visual card container.

### Line 74

``` jsx
      <div className="mb-5 flex items-start justify-between">
```

Starts the dialog header.

### Line 75

``` jsx
        <div><span className="section-kicker">PRIVATE WORKSPACE</span><h2 id="login-title" className="mt-2 text-xl font-semibold tracking-tight text-[#283d4c]">Welcome back</h2><p className="mt-1 text-xs text-[#7d8b96]">Sign in with your organization account.</p></div>
```

Displays the login title and explanatory text.

### Line 76

``` jsx
        <button type="button" className="btn btn-ghost btn-square btn-sm text-[#798b98]" aria-label="Close login" onClick={onClose}><X size={18} /></button>
```

Close button calls `onClose`.

### Line 77

``` jsx
      </div>
```

Closes the header.

### Line 78

``` jsx
      <form onSubmit={async (event) => {
```

Starts the form submission handler.

### Line 79

``` jsx
        event.preventDefault()
```

Prevents the browser's default form submission.

### Line 80

``` jsx
        setMessage('')
```

Clears the previous error message.

### Line 81

``` jsx
        setIsSubmitting(true)
```

Marks the form as submitting.

### Line 82

``` jsx
        const formData = new FormData(event.currentTarget)
```

Reads username/password form values.

### Line 83

``` jsx
        try {
```

Starts successful/error handling.

### Line 84

``` jsx
          await login({ username: formData.get('username'), password: formData.get('password') })
```

Calls the central authentication function with the entered credentials.

### Line 85

``` jsx
          onClose()
```

Closes the login popover after successful authentication.

### Line 86

``` jsx
          navigate('/dashboard')
```

Navigates to the protected dashboard.

### Line 87

``` jsx
        } catch (error) {
```

Begins error handling.

### Line 88

``` jsx
          setMessage(error.message || 'Unable to sign in. Please try again.')
```

Displays the backend error message.

### Line 89

``` jsx
        } finally {
```

Begins the always-run cleanup.

### Line 90

``` jsx
          setIsSubmitting(false)
```

Re-enables the Login button after the request completes.

### Line 91

``` jsx
        }
```

Closes the `finally` block.

### Line 92

``` jsx
      }}>
```

Closes the form.

### Line 93

``` jsx
        <label htmlFor="gbms-username" className="mb-1.5 block text-xs font-semibold text-[#435464]">Username</label>
```

Creates the username label.

### Line 94

``` jsx
        <input id="gbms-username" name="username" autoComplete="username" required maxLength={80} className="input input-bordered w-full bg-white text-sm" placeholder="Enter your username" />
```

Creates the username input.

### Line 95

``` jsx
        <label htmlFor="gbms-password" className="mb-1.5 mt-4 block text-xs font-semibold text-[#435464]">Password</label>
```

Creates the password label.

### Line 96

``` jsx
        <input id="gbms-password" name="password" type="password" autoComplete="current-password" required maxLength={1024} className="input input-bordered w-full bg-white text-sm" placeholder="Enter your password" />
```

Creates the password input.

### Line 97

``` jsx
        <button type="submit" disabled={isSubmitting} className="btn btn-primary mt-5 w-full justify-between px-4">{isSubmitting ? 'Signing in…' : 'Login'} <ArrowRight size={17} /></button>
```

Submits the login form and disables the button while waiting.

### Line 98

``` jsx
        {message && <p className="alert mt-3 rounded-lg bg-[#edf6fb] px-3 py-2 text-xs text-[#386f92]" role="status">{message}</p>}
```

Displays the current login error/status message when present.

### Line 99

``` jsx
        <p className="mt-4 text-center text-[11px] leading-5 text-[#8997a2]">Workspace access is managed by your organization administrator.</p>
```

Explains that access is controlled by the organization administrator.

### Line 201

``` jsx
  return <><Navbar onLogin={openLogin} /><main><HeroSection onLogin={openLogin} /><CapabilitiesSection /><ModulesSection /><WorkflowSection /><CTASection onLogin={openLogin} /></main><Footer onLogin={openLogin} /><div className="global-login-anchor"><LoginPopover open={loginOpen} onClose={closeLogin} /></div></>
```

Mounts the login popover and wires it to the landing page's open/close
state.

### Line 207

``` jsx
    <Route element={<ProtectedRoute />}><Route path="/dashboard" element={<DashboardPage />} /></Route>
```

Wraps `/dashboard` in `ProtectedRoute`, so the dashboard cannot render
unless authentication is valid.

# Appendix J --- `main.jsx` wiring

### Line 1

``` jsx
import { StrictMode } from 'react'
```

Imports React StrictMode.

### Line 2

``` jsx
import { createRoot } from 'react-dom/client'
```

Imports React's root renderer.

### Line 3

``` jsx
import { BrowserRouter } from 'react-router-dom'
```

Imports BrowserRouter so URL routes such as `/dashboard` work.

### Line 4

``` jsx
import { AuthProvider } from './auth/AuthContext.jsx'
```

Imports AuthProvider so authentication state is available to the whole
application.

### Line 5

``` jsx
import './index.css'
```

Loads global CSS.

### Line 6

``` jsx
import App from './App.jsx'
```

Imports the root App component.

### Line 7

``` jsx
```

Part of the React application bootstrap.

### Line 8

``` jsx
createRoot(document.getElementById('root')).render(
```

Finds the HTML element with id `root` and creates the React root.

### Line 9

``` jsx
  <StrictMode>
```

Enables React Strict Mode for development checks.

### Line 10

``` jsx
    <BrowserRouter>
```

Provides routing to the entire app.

### Line 11

``` jsx
      <AuthProvider>
```

Provides authentication context to the entire app.

### Line 12

``` jsx
        <App />
```

Renders the application's route tree.

### Line 13

``` jsx
      </AuthProvider>
```

Closes the React tree.

### Line 14

``` jsx
    </BrowserRouter>
```

Closes the render call.

### Line 15

``` jsx
  </StrictMode>,
```

Part of the React application bootstrap.

### Line 16

``` jsx
)
```

Part of the React application bootstrap.

# Appendix K --- `.env.example` and dependencies

## Backend `.env.example`

``` env
# Copy this file to .env, then set a unique secret and database credentials.
JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=30
DB_SERVER=AbdulMoiz\sqlserver16
DB_NAME=GBMS
DB_DRIVER=ODBC Driver 18 for SQL Server
# Leave blank to use Windows authentication, or set both for SQL authentication.
DB_USER=
DB_PASSWORD=
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

-   `JWT_SECRET_KEY`: private signing key for JWTs.
-   `JWT_ALGORITHM`: JWT signing algorithm; current default is HS256.
-   `ACCESS_TOKEN_MINUTES`: access-token lifetime.
-   `DB_SERVER`: SQL Server instance.
-   `DB_NAME`: database name.
-   `DB_DRIVER`: installed ODBC driver.
-   `DB_USER` / `DB_PASSWORD`: optional SQL-auth credentials. Empty
    values mean Windows authentication in the current code.
-   `CORS_ORIGINS`: allowed React development origins.

## Backend requirements

``` text
fastapi==0.142.2
uvicorn==0.54.0
pyodbc==5.3.0
python-dotenv==1.2.4
PyJWT==2.10.1
argon2-cffi==25.1.0
```

`fastapi` runs the API framework, `uvicorn` serves it, `pyodbc` connects
SQL Server, `python-dotenv` loads `.env`, `PyJWT` handles JWTs, and
`argon2-cffi` handles password hashing.

------------------------------------------------------------------------

# Final study checklist

Before moving to the next GBMS phase, you should be able to answer these
without looking at the code:

1.  Where is the user's password stored?
2.  Why is it stored as a hash?
3.  Which library creates the password hash?
4.  Which endpoint receives username/password?
5.  Which SQL query finds the user?
6.  Why is `Users` joined to `Roles`?
7.  How does FastAPI verify the password?
8.  Where is the JWT created?
9.  What does the JWT `sub` contain?
10. What does `exp` do?
11. Where does React store the JWT in the current implementation?
12. How does React send the JWT to FastAPI?
13. What does `Authorization: Bearer ...` mean?
14. What is `get_current_user()`?
15. Why does it query SQL Server after decoding the JWT?
16. Why is `ProtectedRoute` not enough by itself?
17. What happens when the account becomes `SUSPENDED`?
18. What happens when the JWT expires?
19. What is the relationship between `Users.RoleID` and `Roles.RoleID`?
20. Why is there no public signup?
21. How is the initial Super Admin created?
22. Which part is authentication and which part is authorization?
23. What is still missing before full GBMS RBAC is complete?

If you can explain the answers and draw the flow from memory, you are
ready for the next phase: **Super Admin User Management + Roles +
Permissions**.

------------------------------------------------------------------------

# Dashboard shared layout update

This section describes the dashboard layout that wraps the existing
authenticated dashboard page. The landing page, login popover, and
FastAPI/JWT authentication flow remain the same.

## Authentication and route flow

The landing page's login form calls `useAuth().login()`. `AuthContext`
sends the username and password to FastAPI, stores the returned JWT in
`sessionStorage`, and keeps the authenticated user in React state. On
startup, `AuthContext` checks a stored token with the current-user API.
`ProtectedRoute` waits for that check and renders its child route through
`<Outlet />` only when a user is authenticated. Otherwise, it redirects
to `/`.

The route hierarchy in `src/App.jsx` is:

```text
/                         LandingPage
ProtectedRoute            checks authentication
└── AdminLayout           shared sidebar and topbar
    └── /dashboard        DashboardPage inside AdminLayout's Outlet
```

`src/main.jsx` creates one `BrowserRouter` and one `AuthProvider` around
the app. This makes route navigation and the existing authentication
context available to the landing page and protected pages without
creating duplicate providers.

## Shared layout responsibilities

- `src/Components/Layout/AdminLayout.jsx` places the sidebar beside the
  content column. Its `<Outlet />` is the insertion point where React
  Router renders the matched nested page. Without the outlet, the layout
  could appear while the dashboard content has nowhere to render.
- `src/Components/Layout/Sidebar.jsx` renders the GBMS navigation. On
  wide screens it stays at the left edge; on small screens it slides in
  when opened and can be closed with its close button, backdrop, or a
  navigation link.
- `src/Components/Layout/Topbar.jsx` contains the responsive menu button,
  a visual-only search field, a notification placeholder, and the
  authenticated user's name, initials, and role. The profile menu closes
  when the user clicks outside it or presses Escape.
- `src/pages/Dashboard/Dashboard.jsx` contains dashboard content only.
  It keeps the welcome message, user and role, protected dashboard API
  request, loading and error feedback, and account access cards. It does
  not add invented business metrics or repeat the topbar.

The topbar's Sign out action calls the existing `logout()` method. That
method clears the JWT from `sessionStorage` and clears the auth context;
the topbar then navigates to `/`. The dashboard does not keep a second
logout control or token store.

## Styling and responsive behavior

Tailwind flex classes keep the sidebar and content in two columns on
desktop. `min-w-0` lets the content column shrink instead of forcing
horizontal overflow, while `overflow-x-hidden` contains accidental
sideways overflow. The sidebar switches to a fixed slide-in panel on
mobile, controlled by a small state value in `AdminLayout`. Responsive
padding classes give dashboard content more room on wider screens.
Colors use the existing white, light-gray, and light-blue GBMS palette.

## Root pnpm store ignore rule

The repository root `.gitignore` excludes `.pnpm-store/` and nested
folders with the same name. pnpm's local store is a package cache, not
application source, so it should not be part of the project history.
Ignoring tells Git not to add untracked cache files; it does not remove
files that are already tracked. Tracked root-store entries were removed
from Git's index with a cached removal, which keeps the local store on
disk.

## Validation performed for this layout change

- `npm run lint` completed successfully.
- `npm run build` completed successfully.
- The route tree, component imports, and outlet nesting were inspected.
- The landing page and login popover remain in `src/App.jsx`.
- The mobile toggle is connected from the topbar through
  `AdminLayout` to the sidebar, and the profile menu calls the existing
  logout logic. These behaviors were checked in code; a browser-driven
  visual interaction test was not performed.
- Live JWT/SQL authentication was not re-tested as part of this layout
  change. The dashboard API still uses the existing protected API
  service.

------------------------------------------------------------------------

# Multi-company and inventory foundation

This section documents the company and product-catalogue work added to
GBMS. It builds on the current FastAPI, pyodbc, SQL Server, JWT, and
Argon2 setup. It does not add stock balances or the other ERP workflows.

## Platform users and company users

`SUPER_ADMIN` is a platform role. A Super Admin account has no
`CompanyID` and can use the company-management endpoints across the
platform. The React sidebar shows Company Management only for this role,
and FastAPI independently checks the role on every company-management
request.

`COMPANY_ADMIN`, `SUB_ADMIN`, and `INVENTORY_USER` are company-scoped
roles. Each user has one nullable `Users.CompanyID` foreign key; the
database trigger requires that all non-Super-Admin users have a company
and that Super Admin users have none. The foreign key prevents assignment
to a non-existent company. There is no user administration API yet, so
provisioning company accounts still needs a secure account-creation flow
that assigns the correct role and CompanyID and stores only an Argon2
password hash.

The JWT still identifies the user through its `sub` claim. It does not
prove a role or tenant. On each authenticated backend request,
`get_current_user()` reloads the user's status, current role, and company
from SQL Server. It rejects suspended/inactive accounts, company users
without a company, and users assigned to an inactive company. This means
changing a browser URL, request body, query string, or local state cannot
change the user's tenant.

## Database relationships

The migration is `SQL Server Query/Multi Company Inventory Migration.sql`.
It is additive and repeatable: it does not drop, recreate, truncate, or
reset the existing `Roles` or `Users` tables, user rows, IDs, or password
hashes. It adds:

- `Companies`: globally unique company name and stable company code,
  contact details, ACTIVE/INACTIVE status, and UTC timestamps.
- `Users.CompanyID`: nullable foreign key to `Companies`, plus an index.
- Additional role rows for `COMPANY_ADMIN`, `SUB_ADMIN`, and
  `INVENTORY_USER`, inserted only if missing. Existing `SUPER_ADMIN`
  data remains in place.
- `UnitsOfMeasure`: global reference data, shared by companies. The seed
  units are Piece, Kilogram, Metre, Yard, Roll, and Box.
- `ProductCategories`: each category belongs to one company; category
  names are unique within that company.
- `Products`: each product belongs to one company, has a company-unique
  SKU, product type, global unit, optional same-company category,
  non-negative decimal reorder level, active flag, and timestamps.

The composite foreign key from `(Products.CompanyID, Products.CategoryID)`
to the matching company/category key is a database-level guard against a
product referencing another company's category. Product SKU uniqueness
is `(CompanyID, SKU)`, so separate companies may use the same SKU.
Company names and codes are unique platform-wide. Quantities use
`DECIMAL(18,3)`; no on-hand quantity is stored because a stock ledger and
stock movement rules are a separate phase.

### Applying or checking the migration

The migration was applied to the configured `GBMS` SQL Server database
and immediately run a second time. Both executions completed. A read-only
check confirmed the four company/inventory tables, all four expected
roles, six global units, and the existing single Super Admin account.
There are currently no companies, product categories, or products, so the
new screens will show their empty states until records are added. To run
the migration manually from SSMS, connect to the `GBMS` database, open the
migration file, and execute it. With `sqlcmd` and Windows authentication,
run this from the repository root:

```powershell
sqlcmd -S 'AbdulMoiz\sqlserver16' -d GBMS -E -b -i '.\SQL Server Query\Multi Company Inventory Migration.sql'
```

Confirm the objects and role seed with:

```sql
USE GBMS;
SELECT name FROM sys.tables
WHERE name IN ('Companies', 'ProductCategories', 'Products', 'UnitsOfMeasure');
SELECT RoleName FROM dbo.Roles
WHERE RoleName IN ('SUPER_ADMIN', 'COMPANY_ADMIN', 'SUB_ADMIN', 'INVENTORY_USER');
SELECT u.CompanyID FROM dbo.Users AS u
JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
WHERE r.RoleName = 'SUPER_ADMIN';
```

The last query should leave the platform Super Admin's `CompanyID` null.
Do not assign that platform account to a tenant.

## Backend API and isolation

Company management is restricted by `require_super_admin`:

- `GET /api/v1/companies?search=&limit=25&offset=0` lists companies.
- `POST /api/v1/companies` creates a company.
- `GET /api/v1/companies/{company_id}` reads its details.
- `PUT /api/v1/companies/{company_id}` updates name, code, and contact
  fields.
- `PATCH /api/v1/companies/{company_id}/status` activates or deactivates
  a company.

Company inventory requires an active company-scoped user. The API
derives the company from that user's current database record, never from
a client-supplied CompanyID:

- `GET /api/v1/inventory/categories` lists the signed-in company's
  categories; `POST` creates one in that company.
- `GET /api/v1/inventory/units` lists shared active units.
- `GET /api/v1/inventory/products` lists only the user's company
  products and accepts `search`, `category_id`, `limit`, and `offset`.
- `POST /api/v1/inventory/products` creates a product in the user's
  company.
- `GET /api/v1/inventory/products/{product_id}` reads a product only
  when it belongs to that company.
- `PUT /api/v1/inventory/products/{product_id}` updates only that
  company's product.
- `PATCH /api/v1/inventory/products/{product_id}/status` activates or
  deactivates only that company's product.

Product/category SQL always binds the CompanyID from the authenticated
user. Missing and other-tenant product IDs both return 404. The API uses
parameterized values for all user input. Search SQL identifiers and
update column names come from fixed server-side choices. Duplicate
company names/codes, category names within one company, or SKUs within
one company return a conflict response.

## Frontend routes and pages

The existing landing page and login popover stay public at `/`. The
protected route tree keeps the shared `AdminLayout`, then adds:

- `/companies`, allowed only for `SUPER_ADMIN`.
- `/inventory`, allowed only for `COMPANY_ADMIN`, `SUB_ADMIN`, and
  `INVENTORY_USER`.

These React checks improve navigation, but they are not the security
boundary; FastAPI repeats all role and tenant checks. The Company
Management page reads real API results and supports create, edit, search,
pagination, and confirmed status changes. Inventory reads company
categories and global units from FastAPI, and supports product create,
edit, search, category filtering, pagination, category creation, and
confirmed active/inactive changes. Both pages provide loading, empty,
success, validation/error states and do not substitute fake rows for
database results. The existing Sidebar shows the appropriate live
navigation for the role; not-yet-built modules are disabled and labelled
Coming Soon.

## Running and configuring the app

Keep real secrets in `FastAPI (BackEnd)/.env`; the checked-in
`.env.example` contains placeholders only. The existing `.env` sets the
SQL Server instance and JWT secret. From the repository root, run the
backend and frontend in separate terminals:

```powershell
Set-Location '.\FastAPI (BackEnd)'
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

```powershell
Set-Location '.\React (FrontEnd)\GBMS'
npm run dev
```

The frontend uses `VITE_API_BASE_URL` if it is set; otherwise it uses
`http://127.0.0.1:8000`. The UI does not contain database credentials.

## Tenant-isolation check for a company account

Once a company-scoped account is securely provisioned for Company A:

1. Sign in as that account and create a product. Confirm it appears in
   Company A's inventory.
2. Try another company's product ID with the same bearer token. The API
   should return 404 and should not reveal that other company's product.
3. Try sending `company_id` in a product create/update body. The request
   schema rejects extra fields; the backend uses only the company ID
   reloaded from the signed-in account.
4. Deactivate Company A. The next login and every later authenticated
   company operation should be rejected, even if the user still has a
   previously issued JWT.
5. Sign in as Super Admin and confirm company routes work while inventory
   routes remain denied unless a separate explicit platform feature is
   designed later.

The company-scoped account provisioning and full two-company end-to-end
isolation test remain future work; there is currently no user-management
UI or company-admin creation endpoint. The backend guards and schema are
in place so this can be added without trusting a CompanyID from React.

## Checks run for this implementation

- The SQL migration completed successfully twice against `GBMS`; a
  read-only check confirmed the four new tables and the existing Super
  Admin account.
- The FastAPI source compiled and imported, and OpenAPI registered the
  company and product routes.
- Frontend `npm run lint` and `npm run build` both completed successfully
  after the final UI changes.
- Seven focused database-free authorization/schema checks in
  `FastAPI (BackEnd)/test_company_inventory.py` passed with
  `python -m unittest -v test_company_inventory.py`.
- A read-only SQL Server query confirmed four seeded roles, six active
  units, and one Super Admin with no company assignment.
- The full company CRUD, company-user login, and cross-tenant product
  behavior have not been exercised end-to-end with separate company
  accounts.
