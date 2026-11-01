from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers.accounts.register_controller import (
    router as register_router,
)
from app.controllers.accounts.login_controller import (
    router as login_router,
)
from app.controllers.accounts.logout_controller import (
    router as logout_router,
)
from app.controllers.accounts.password_reset_controller import (
    router as password_reset_router,
)
from app.controllers.fleet_management_controller import (
    router as fleet_management_router,
)
from app.controllers.driver_management_controller import (
    router as driver_management_router,
)
from app.controllers.shift_roster_controller import (
    router as shift_roster_router,
)
from app.controllers.maintenance_alerts_controller import (
    router as maintenance_alerts_router,
)
from app.controllers.dispatch_planning_controller import (
    router as dispatch_planning_router,
)
from app.controllers.route_distance_and_time_controller import (
    router as route_distance_and_time_router,
)
from app.controllers.stop_sequencing_controller import (
    router as stop_sequencing_router,
)

from app.core.config import settings

from app.database.connection import (
    connect_to_database,
    close_database_connection,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_database()

    try:
        yield
    finally:
        await close_database_connection()


app = FastAPI(
    title="FleetPulse API",
    description="Smart Fleet Logistics and Delivery Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication
app.include_router(register_router, prefix="/api/v1")
app.include_router(login_router, prefix="/api/v1")
app.include_router(logout_router, prefix="/api/v1")
app.include_router(password_reset_router, prefix="/api/v1")

# F1 - Fleet Management
app.include_router(
    fleet_management_router,
    prefix="/api/v1",
)

# F2 - Driver Management
app.include_router(
    driver_management_router,
    prefix="/api/v1",
)


# F3 - Shift Roster
app.include_router(
    shift_roster_router,
    prefix="/api/v1",
)


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "application": "FleetPulse",
        "message": "Backend is running successfully",
    }


# F4 - Maintenance Alerts
app.include_router(
    maintenance_alerts_router,
    prefix="/api/v1",
)

# F11 - Dispatch Planning
app.include_router(
    dispatch_planning_router,
    prefix="/api/v1",
)

# F12 - Route Distance and Time
app.include_router(
    route_distance_and_time_router,
    prefix="/api/v1",
)

# F13 - Stop Sequencing
app.include_router(
    stop_sequencing_router,
    prefix="/api/v1",
)
