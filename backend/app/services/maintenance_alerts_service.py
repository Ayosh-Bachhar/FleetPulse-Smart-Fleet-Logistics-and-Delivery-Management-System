import asyncio
import re

from datetime import datetime, timezone

from bson import ObjectId

from app.models.vehicle import (
    Vehicle,
    VehicleStatus,
    is_vehicle_maintenance_due,
    is_vehicle_dispatchable,
)

from app.models.maintenance_record import (
    MaintenanceRecord,
    MaintenanceEvent,
)

from app.schemas.maintenance_alerts_schemas import (
    MaintenanceVehicleResponse,
    MaintenanceListResponse,
    MaintenanceRecordResponse,
    MaintenanceHistoryResponse,
)


_maintenance_write_lock = asyncio.Lock()


class MaintenanceVehicleNotFoundError(Exception):
    pass


class MaintenanceOperationError(Exception):
    pass


def now_utc():
    return datetime.now(timezone.utc)


def apply_distance(vehicle, distance_km):
    previously_due = is_vehicle_maintenance_due(vehicle)

    vehicle.odometer_km = round(
        vehicle.odometer_km + distance_km,
        3,
    )

    if is_vehicle_maintenance_due(vehicle):
        vehicle.maintenance_due = True

        if vehicle.status != VehicleStatus.INACTIVE:
            vehicle.status = VehicleStatus.MAINTENANCE

    return (
        not previously_due
        and is_vehicle_maintenance_due(vehicle)
    )


def apply_interval_change(vehicle, new_interval):
    previously_due = is_vehicle_maintenance_due(vehicle)

    vehicle.service_interval_km = new_interval

    if is_vehicle_maintenance_due(vehicle):
        vehicle.maintenance_due = True

        if vehicle.status != VehicleStatus.INACTIVE:
            vehicle.status = VehicleStatus.MAINTENANCE

    return (
        not previously_due
        and is_vehicle_maintenance_due(vehicle)
    )


def apply_service_completion(vehicle):
    if vehicle.status == VehicleStatus.IN_USE:
        raise MaintenanceOperationError(
            "Cannot complete service while vehicle is in use."
        )

    vehicle.last_service_km = vehicle.odometer_km
    vehicle.maintenance_due = False

    if vehicle.status == VehicleStatus.MAINTENANCE:
        vehicle.status = VehicleStatus.AVAILABLE


def maintenance_to_response(vehicle):
    since_service = max(
        0,
        vehicle.odometer_km - vehicle.last_service_km,
    )

    remaining = max(
        0,
        vehicle.service_interval_km - since_service,
    )

    progress = min(
        100,
        (since_service / vehicle.service_interval_km) * 100,
    )

    due = is_vehicle_maintenance_due(vehicle)

    return MaintenanceVehicleResponse(
        id=str(vehicle.id),
        registration_number=vehicle.registration_number,
        vehicle_type=vehicle.vehicle_type,
        status=vehicle.status,
        odometer_km=round(vehicle.odometer_km, 3),
        last_service_km=round(vehicle.last_service_km, 3),
        service_interval_km=vehicle.service_interval_km,
        kilometers_since_service=round(since_service, 3),
        kilometers_until_service=round(remaining, 3),
        service_progress_percent=round(progress, 1),
        maintenance_due=due,
        needs_attention=(
            due
            or vehicle.status == VehicleStatus.MAINTENANCE
        ),
        is_available=is_vehicle_dispatchable(vehicle),
        updated_at=vehicle.updated_at,
    )


def record_to_response(record):
    return MaintenanceRecordResponse(
        id=str(record.id),
        vehicle_id=str(record.vehicle_id),
        actor_user_id=str(record.actor_user_id),
        event_type=record.event_type,
        distance_km=record.distance_km,
        odometer_km=record.odometer_km,
        service_interval_km=record.service_interval_km,
        maintenance_triggered=record.maintenance_triggered,
        notes=record.notes,
        created_at=record.created_at,
    )


async def get_vehicle_document(vehicle_id):
    if not ObjectId.is_valid(vehicle_id):
        raise MaintenanceVehicleNotFoundError(
            "Vehicle not found."
        )

    vehicle = await Vehicle.get(ObjectId(vehicle_id))

    if vehicle is None:
        raise MaintenanceVehicleNotFoundError(
            "Vehicle not found."
        )

    return vehicle


async def list_maintenance(
    search=None,
    only_attention=False,
    page=1,
    page_size=10,
):
    filters = []

    if search and search.strip():
        safe_search = re.escape(search.strip())

        filters.append({
            "$or": [
                {
                    "registration_number": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
                {
                    "vehicle_type": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
            ]
        })

    if only_attention:
        filters.append({
            "$or": [
                {"maintenance_due": True},
                {"status": VehicleStatus.MAINTENANCE.value},
            ]
        })

    query = Vehicle.find(*filters)

    total = await query.count()

    vehicles = await (
        query.sort("registration_number")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    return MaintenanceListResponse(
        items=[
            maintenance_to_response(vehicle)
            for vehicle in vehicles
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_maintenance(vehicle_id):
    vehicle = await get_vehicle_document(vehicle_id)

    return maintenance_to_response(vehicle)


async def get_maintenance_history(
    vehicle_id,
    page=1,
    page_size=20,
):
    vehicle = await get_vehicle_document(vehicle_id)

    query = MaintenanceRecord.find(
        MaintenanceRecord.vehicle_id == vehicle.id
    )

    total = await query.count()

    records = await (
        query.sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    return MaintenanceHistoryResponse(
        items=[
            record_to_response(record)
            for record in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def save_maintenance_record(
    vehicle,
    actor_user_id,
    event_type,
    distance_km=0,
    triggered=False,
    notes=None,
):
    record = MaintenanceRecord(
        vehicle_id=vehicle.id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        distance_km=distance_km,
        odometer_km=vehicle.odometer_km,
        service_interval_km=vehicle.service_interval_km,
        maintenance_triggered=triggered,
        notes=notes,
    )

    await record.insert()


async def add_vehicle_distance(
    vehicle_id,
    data,
    actor_user_id,
):
    async with _maintenance_write_lock:
        vehicle = await get_vehicle_document(vehicle_id)

        triggered = apply_distance(
            vehicle,
            data.distance_km,
        )

        vehicle.updated_at = now_utc()
        await vehicle.save()

        await save_maintenance_record(
            vehicle=vehicle,
            actor_user_id=actor_user_id,
            event_type=MaintenanceEvent.DISTANCE_ADDED,
            distance_km=data.distance_km,
            triggered=triggered,
            notes=data.notes,
        )

        return maintenance_to_response(vehicle)


async def change_service_interval(
    vehicle_id,
    data,
    actor_user_id,
):
    async with _maintenance_write_lock:
        vehicle = await get_vehicle_document(vehicle_id)

        triggered = apply_interval_change(
            vehicle,
            data.service_interval_km,
        )

        vehicle.updated_at = now_utc()
        await vehicle.save()

        await save_maintenance_record(
            vehicle=vehicle,
            actor_user_id=actor_user_id,
            event_type=MaintenanceEvent.INTERVAL_CHANGED,
            triggered=triggered,
            notes=data.notes,
        )

        return maintenance_to_response(vehicle)


async def complete_vehicle_service(
    vehicle_id,
    data,
    actor_user_id,
):
    async with _maintenance_write_lock:
        vehicle = await get_vehicle_document(vehicle_id)

        apply_service_completion(vehicle)

        vehicle.updated_at = now_utc()
        await vehicle.save()

        await save_maintenance_record(
            vehicle=vehicle,
            actor_user_id=actor_user_id,
            event_type=MaintenanceEvent.SERVICE_COMPLETED,
            notes=data.notes,
        )

        return maintenance_to_response(vehicle)