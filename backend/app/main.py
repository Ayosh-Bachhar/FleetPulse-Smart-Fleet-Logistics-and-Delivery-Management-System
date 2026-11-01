import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Authentication Controllers
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

# F1 - Fleet Management
from app.controllers.fleet_management_controller import (
    router as fleet_management_router,
)

# F2 - Driver Management
from app.controllers.driver_management_controller import (
    router as driver_management_router,
)

# F3 - Shift Roster
from app.controllers.shift_roster_controller import (
    router as shift_roster_router,
)

# F4 - Maintenance Alerts
from app.controllers.maintenance_alerts_controller import (
    router as maintenance_alerts_router,
)

# F11 - Dispatch Planning
from app.controllers.dispatch_planning_controller import (
    router as dispatch_planning_router,
)

# F12 - Route Distance and Time
from app.controllers.route_distance_and_time_controller import (
    router as route_distance_and_time_router,
)

# F13 - Stop Sequencing
from app.controllers.stop_sequencing_controller import (
    router as stop_sequencing_router,
)

# F14 - Simulated GPS
from app.controllers.simulated_gps_controller import (
    router as simulated_gps_router,
)
from app.scheduler.gps_simulation_scheduler import (
    gps_simulation_loop,
)

# Configuration and Database
from app.core.config import settings

from app.database.connection import (
    connect_to_database,
    close_database_connection,
)


# Application Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_database()

    # F14 - Run GPS simulation every 5 seconds.
    gps_task = asyncio.create_task(
        gps_simulation_loop()
    )

    try:
        yield

    finally:
        # Stop GPS scheduler during application shutdown.
        gps_task.cancel()

        try:
            await gps_task
        except asyncio.CancelledError:
            pass

        await close_database_connection()


# FastAPI Application
app = FastAPI(
    title="FleetPulse API",
    description="Smart Fleet Logistics and Delivery Management System",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Authentication
app.include_router(
    register_router,
    prefix="/api/v1",
)
app.include_router(
    login_router,
    prefix="/api/v1",
)
app.include_router(
    logout_router,
    prefix="/api/v1",
)
app.include_router(
    password_reset_router,
    prefix="/api/v1",
)


# Health Check
@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "application": "FleetPulse",
        "message": "Backend is running successfully",
    }


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


# F14 - Simulated GPS
app.include_router(
    simulated_gps_router,
    prefix="/api/v1",
)
