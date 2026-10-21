# FleetPulse

**Smart Fleet Logistics and Delivery Management System**

FleetPulse is a university software engineering group project for managing fleets, drivers, delivery orders, dispatch, tracking, and operational reporting. The application follows **Model–View–Controller (MVC)** architecture: FastAPI controllers handle requests, service modules contain business logic, Beanie models handle MongoDB persistence, and React provides the user interface.

> **Current implementation:** The React↔FastAPI connectivity screen, `/api/v1/health`, MongoDB Atlas connection, and Beanie `Vehicle` model are working. Authentication, the 20 business features, and most models/controllers/services are currently scaffolds, **not finished features**.

## Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, Vite 8, JavaScript/JSX, Axios, React Router |
| Backend | Python 3.13, FastAPI, Uvicorn |
| Database | MongoDB Atlas (shared cloud database) |
| Object Document Mapper (ODM) | Beanie (using PyMongo's asynchronous client) |
| Planned authentication | JSON Web Tokens (JWT) in HTTP-only cookies, bcrypt password hashes, role-based access control |
| Version control | Git + GitHub; individual member branches |

## Prerequisites (each member's laptop)

- Windows with PowerShell and Visual Studio Code (commands below are for Windows).
- Git and a GitHub account with access to the FleetPulse repository.
- Python **3.13**, Node.js and npm installed.
- Internet access to reach MongoDB Atlas.
- A **database user** and **network access permission** provided by the Atlas project owner. **Local MongoDB Server is not needed** when using Atlas.

## Clone and configure

### 1. Clone the repository

```powershell
git clone https://github.com/Ayosh-Bachhar/FleetPulse-Smart-Fleet-Logistics-and-Delivery-Management-System.git
cd FleetPulse-Smart-Fleet-Logistics-and-Delivery-Management-System
```

Switch to your assigned branch (after it has been synchronized with `main`):

```powershell
git fetch origin
git switch Ayosh  # Replace Ayosh with Kawsar, Faiyaz, or Sakline as applicable
```

### 2. Install the Python backend dependencies

Run from the repository root:

```powershell
py -3.13 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

The command uses the virtual environment's Python directly; activating the environment is optional.

### 3. Configure MongoDB Atlas and backend secrets

The **Atlas project owner** must first:

1. Create a database user for each member, preferably restricted to `readWrite` on `fleetpulse_db`.
2. Add each member's current public IP address in **Atlas → Security → Network Access** (or configure an approved secure access method).
3. Share the Atlas cluster hostname, member-specific database username, and password privately, **not in GitHub, issues, screenshots, or pull requests**.

Each member then creates `backend/.env` from `backend/.env.example`:

```powershell
Copy-Item backend\.env.example backend\.env
```

Update `backend/.env` locally using the **actual** URI supplied by Atlas:

```dotenv
MONGODB_URL=mongodb+srv://YOUR_USERNAME:YOUR_URL_ENCODED_PASSWORD@YOUR_CLUSTER.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=fleetpulse_db
FRONTEND_URL=http://localhost:5173
JWT_SECRET_KEY=YOUR_OWN_LONG_RANDOM_SECRET
```

A password containing reserved URI characters (for example `@`, `#`, `/`, or `:`) must be URL-encoded. Use a strong random secret for JWT authentication. Never commit `backend/.env` (the repository `.gitignore` excludes it). Each teammate can use a different JWT secret for their **local** backend during development; once authentication is implemented, changing it will invalidate existing login tokens. The backend currently has no implemented login functionality.

**Important:** GitHub repository access **does not** grant MongoDB Atlas access. Teammates need Atlas credentials and network permission even if they can clone the code. Atlas database users do not automatically grant access to the Atlas website; dashboard access requires a separate project invitation.

### 4. Install frontend dependencies

From the repository root:

```powershell
npm --prefix frontend ci
```

The frontend API client defaults to `http://127.0.0.1:8000`. The optional `frontend/.env.example` shows how to set `VITE_API_BASE_URL` if necessary. You do not need to copy it when using the default.

## Run FleetPulse locally

Open **two separate PowerShell terminals**.

**Terminal 1 — Backend (from the repository root):**

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**Terminal 2 — Frontend (from the repository root):**

```powershell
npm --prefix frontend run dev
```

| URL | What to check |
| --- | --- |
| http://localhost:5173 | React application and connection-status screen |
| http://127.0.0.1:8000/api/v1/health | Backend health JSON |
| http://127.0.0.1:8000/docs | FastAPI interactive API documentation |
| Atlas → Database → Browse Collections | `fleetpulse_db` documents after inserting or seeding |

The backend's startup establishes the Atlas connection. A working health response indicates startup succeeded, but **database read/write** should be verified by running the seed script and checking Atlas.

## Seed demonstration data

Only the **Vehicle** Beanie model is implemented so far. The current working seed script populates the shared Atlas `vehicles` collection with **four clearly named sample vehicles**:

```powershell
# Run from the repository root:
cd backend
.\.venv\Scripts\python.exe -m scripts.seed_vehicles
```

Running it again will **skip vehicles with the same registration numbers**; it will not clear the database or overwrite those records. Since everyone connects to the same Atlas database, **only one team member needs to run it for the shared database**. Everyone else sees the same data.

The existing `seed_users.py`, `seed_orders.py`, and `seed_routes.py` files remain **pending** until their corresponding Beanie models and required field schemas are implemented. Do not run them yet. Once those models exist, add repeatable sample records and update this section. **Never seed real passwords as plain text**: user passwords must be hashed by the completed authentication code.

### Verify database data

In **MongoDB Atlas → Database → Browse Collections**, navigate to `fleetpulse_db` → `vehicles`. You should see the demo registrations `FP-DEMO-001` through `FP-DEMO-004`, plus any vehicles already inserted (for example, `FLEET-TEST-001`).

> **Shared-database caution:** Changes are visible to all members. Do not delete or reset collections casually. For destructive experiments, use a separate development/test database name and coordinate with the team. This Atlas-only configuration requires internet access during demonstration.

## Feature ownership

The following are **planned assignments**; they do not imply that the code has already been implemented.

| Member / branch | Assigned features | Additional responsibility |
| --- | --- | --- |
| Ayosh / `Ayosh` | F1 Fleet management; F2 Driver management; F3 Shift roster; F4 Maintenance alerts; F5 Fuel & mileage log | Registration, common setup and vehicle seeds |
| Kawsar / `Kawsar` | F6 Order intake; F7 Capacity check; F8 Pricing engine; F9 Order lifecycle; F10 Delivery proof | Login, order validation and seeds |
| Faiyaz / `Faiyaz` | F11 Dispatch planning; F12 Route distance/time; F13 Stop sequencing; F14 Simulated GPS; F15 ETA/delay prediction | Logout, scheduling and route testing |
| Sakline / `Sakline` | F16 Map view; F17 Public tracking; F18 Notifications; F19 Role dashboards; F20 Reports/CSV | Password reset, shared navigation and documentation/testing |

Registration, login, logout, and password reset are mandatory authentication features in addition to the 20 counted features. Planned external integrations include Calendarific, OpenWeather, GeoApify, Leaflet maps, and Discord webhooks; these integrations are **not yet implemented**.

## Git collaboration workflow

Each member works on **their own branch** and pushes their actual changes there. Only reviewed and tested work should be merged into `main`.

At the beginning of a work session, from the repository root:

```powershell
git fetch origin
git switch Ayosh    # Use your own assigned branch
git merge origin/main
```

After making and testing changes:

```powershell
git status
git add <paths-to-files-you-changed>
git commit -m "Describe the completed change"
git push -u origin Ayosh  # Use your own branch
```

Open a pull request into `main` for review. Resolve merge conflicts carefully and do not upload private `.env` files. If a teammate's environment breaks, check their local `.env`, Atlas network permissions, dependencies, and backend terminal errors before assuming an application bug.

## Project layout

```text
FleetPulse/
├── backend/
│   ├── app/
│   │   ├── controllers/        # FastAPI request handlers (planned)
│   │   ├── services/           # Business rules (planned)
│   │   ├── schemas/            # Request/response schemas (planned)
│   │   ├── models/             # Beanie documents (Vehicle implemented)
│   │   ├── database/           # Atlas connection and Beanie init
│   │   ├── core/               # Configuration/security foundation
│   │   ├── integrations/       # External API integrations (planned)
│   │   └── scheduler/          # GPS simulation (planned)
│   ├── scripts/               # Database seeding
│   ├── tests/                 # Backend tests (scaffold)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/features/          # React pages/components by feature (scaffold)
│   ├── src/api/               # Axios client
│   └── package.json
├── docs/                     # Project documentation
└── README.md
```

## Basic development checks

From the repository root:

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
.\backend\.venv\Scripts\python.exe -m pip check
```

The backend test files are currently placeholders, so an empty `pytest` run does **not** indicate that the application has been fully tested. As features are implemented, add real tests for each one.

## Current next steps

1. Verify every member's Atlas credentials/network access and ability to run both servers.
2. Implement the shared User model and authentication endpoints, then update `seed_users.py`.
3. Implement Order and Route models, then update `seed_orders.py` and `seed_routes.py`.
4. Implement and test the 20 planned features.
5. Create reproducible demo data and test the complete workflow on each member's laptop.