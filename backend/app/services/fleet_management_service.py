import re
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError


from app.models.vehicle import (
    Vehicle,
    VehicleStatus,
    is_vehicle_maintenance_due,
    is_vehicle_dispatchable,
)

from app.schemas.fleet_management_schemas import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    VehicleListResponse,
)


class VehicleAlreadyExistsError(Exception):
    pass


class VehicleNotFoundError(Exception):
    pass

class VehicleMaintenanceBlockedError(Exception):
    pass


def vehicle_to_response(vehicle: Vehicle) -> VehicleResponse:
    return VehicleResponse(
        id=str(vehicle.id),
        registration_number=vehicle.registration_number,
        vehicle_type=vehicle.vehicle_type,
        capacity_kg=vehicle.capacity_kg,
        volume_capacity_m3=vehicle.volume_capacity_m3,
        fuel_type=vehicle.fuel_type,
        status=vehicle.status,
        is_available=is_vehicle_dispatchable(vehicle),

        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


async def create_vehicle(
    data: VehicleCreate,
) -> VehicleResponse:

    existing = await Vehicle.find_one(
        Vehicle.registration_number == data.registration_number
    )

    if existing:
        raise VehicleAlreadyExistsError(
            "A vehicle with this registration already exists."
        )

    vehicle = Vehicle(
        **data.model_dump()
    )

    try:
        await vehicle.insert()
    except DuplicateKeyError as exc:
        raise VehicleAlreadyExistsError(
            "A vehicle with this registration already exists."
        ) from exc

    return vehicle_to_response(vehicle)


async def list_vehicles(
    search: str | None = None,
    vehicle_status: VehicleStatus | None = None,
    page: int = 1,
    page_size: int = 10,
) -> VehicleListResponse:

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
                {
                    "fuel_type": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
            ]
        })

    if vehicle_status is not None:
        filters.append({
            "status": vehicle_status.value
        })

    query = Vehicle.find(*filters)

    total = await query.count()

    vehicles = await (
        query.sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    return VehicleListResponse(
        items=[
            vehicle_to_response(vehicle)
            for vehicle in vehicles
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_vehicle(
    vehicle_id: str,
) -> VehicleResponse:

    vehicle = await get_vehicle_document(vehicle_id)

    return vehicle_to_response(vehicle)


async def get_vehicle_document(vehicle_id: str) -> Vehicle:
    if not ObjectId.is_valid(vehicle_id):
        raise VehicleNotFoundError("Vehicle not found.")

    vehicle = await Vehicle.get(ObjectId(vehicle_id))

    if vehicle is None:
        raise VehicleNotFoundError("Vehicle not found.")

    return vehicle


async def update_vehicle(
    vehicle_id: str,
    data: VehicleUpdate,
) -> VehicleResponse:

    vehicle = await get_vehicle_document(vehicle_id)

    changes = data.model_dump(exclude_unset=True)

    requested_status = changes.get("status")

    if (
        vehicle.status == VehicleStatus.MAINTENANCE
        or is_vehicle_maintenance_due(vehicle)
    ) and requested_status in (
        VehicleStatus.AVAILABLE,
        VehicleStatus.IN_USE,
    ):
        raise VehicleMaintenanceBlockedError(
            "Vehicle requires maintenance clearance. "
            "Complete service through Maintenance Alerts."
        )

    new_registration = changes.get(
        "registration_number"
    )

    if (
        new_registration is not None
        and new_registration != vehicle.registration_number
    ):
        existing = await Vehicle.find_one(
            Vehicle.registration_number == new_registration
        )

        if existing:
            raise VehicleAlreadyExistsError(
                "A vehicle with this registration already exists."
            )

    for field_name, value in changes.items():
        setattr(vehicle, field_name, value)

    vehicle.updated_at = datetime.now(timezone.utc)

    try:
        await vehicle.save()
    except DuplicateKeyError as exc:
        raise VehicleAlreadyExistsError(
            "A vehicle with this registration already exists."
        ) from exc

    return vehicle_to_response(vehicle)