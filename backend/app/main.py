from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "application": "FleetPulse",
        "message": "Backend is running successfully",
    }