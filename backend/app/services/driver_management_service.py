import re
from datetime import date, datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.models.driver import (
    Driver,
    DriverLicenseClass,
    DriverStatus,
)
from app.models.user import User, Role
from app.models.vehicle import (
    Vehicle,
    VehicleStatus,
    is_vehicle_dispatchable,
)

from app.schemas.driver_management_schemas import (
    DriverCreate,
    DriverUpdate,
    DriverResponse,
    DriverListResponse,
    DriverCompatibilityResponse,
)


# Proposed project-specific license mapping.
# Coordinate changes with F11 Dispatch Planning.
LICENSE_VEHICLE_TYPES = {
    DriverLicenseClass.LIGHT: ("Mini Van",),
    DriverLicenseClass.MEDIUM: ("Mini Van", "Van"),
    DriverLicenseClass.HEAVY: ("Mini Van", "Van", "Truck"),
}


class DriverAlreadyExistsError(Exception):
    pass


class DriverNotFoundError(Exception):
    pass


class DriverUserError(Exception):
    pass


class DriverVehicleNotFoundError(Exception):
    pass


def allowed_vehicle_types(license_class):
    return list(LICENSE_VEHICLE_TYPES[license_class])


def is_license_compatible(license_class, vehicle_type):
    return vehicle_type.strip().casefold() in {
        item.casefold()
        for item in allowed_vehicle_types(license_class)
    }


def is_license_valid(driver, today=None):
    today = today or date.today()
    return driver.license_expiry >= today


def evaluate_driver_vehicle(driver, vehicle, today=None):
    license_compatible = is_license_compatible(
        driver.license_class,
        vehicle.vehicle_type,
    )

    if not license_compatible:
        return False, False, (
            "Driver license class does not permit "
            "this vehicle type."
        )

    if not is_license_valid(driver, today):
        return True, False, "Driver license has expired."

    if driver.status != DriverStatus.AVAILABLE:
        return True, False, "Driver is not available."

    if not is_vehicle_dispatchable(vehicle):
        return True, False, (
            "Vehicle is unavailable or requires maintenance."
        )

    return True, True, "Driver and vehicle are compatible."


async def resolve_driver_user(email, exclude_driver_id=None):
    if not email:
        return None

    user = await User.find_one(
        User.email == str(email).strip().lower()
    )

    if user is None:
        raise DriverUserError(
            "No user account exists with that email."
        )

    if user.role != Role.DRIVER or not user.is_active:
        raise DriverUserError(
            "Linked account must be an active Driver user."
        )

    existing_driver = await Driver.find_one(
        Driver.user_id == user.id
    )

    if (
        existing_driver is not None
        and str(existing_driver.id) != exclude_driver_id
    ):
        raise DriverAlreadyExistsError(
            "That user is already linked to another driver."
        )

    return user


async def driver_to_response(driver):
    linked_email = None

    if driver.user_id is not None:
        linked_user = await User.get(driver.user_id)
        if linked_user is not None:
            linked_email = str(linked_user.email)

    valid = is_license_valid(driver)

    return DriverResponse(
        id=str(driver.id),
        full_name=driver.full_name,
        phone=driver.phone,
        license_number=driver.license_number,
        license_class=driver.license_class,
        license_expiry=driver.license_expiry,
        status=driver.status,
        user_id=(
            str(driver.user_id)
            if driver.user_id is not None
            else None
        ),
        linked_user_email=linked_email,
        allowed_vehicle_types=allowed_vehicle_types(
            driver.license_class
        ),
        license_valid=valid,
        is_available=(
            driver.status == DriverStatus.AVAILABLE
            and valid
        ),
        created_at=driver.created_at,
        updated_at=driver.updated_at,
    )


async def get_driver_document(driver_id):
    if not ObjectId.is_valid(driver_id):
        raise DriverNotFoundError("Driver not found.")

    driver = await Driver.get(ObjectId(driver_id))

    if driver is None:
        raise DriverNotFoundError("Driver not found.")

    return driver


async def create_driver(data: DriverCreate):
    existing = await Driver.find_one(
        Driver.license_number == data.license_number
    )

    if existing is not None:
        raise DriverAlreadyExistsError(
            "A driver with this license already exists."
        )

    linked_user = await resolve_driver_user(
        data.linked_user_email
    )

    values = data.model_dump(
        exclude={"linked_user_email"}
    )

    driver = Driver(
        **values,
        user_id=linked_user.id if linked_user else None,
    )

    try:
        await driver.insert()
    except DuplicateKeyError as exc:
        raise DriverAlreadyExistsError(
            "Driver license or linked account already exists."
        ) from exc

    return await driver_to_response(driver)


async def list_drivers(
    search=None,
    driver_status=None,
    license_class=None,
    page=1,
    page_size=10,
):
    filters = []

    if search and search.strip():
        safe_search = re.escape(search.strip())

        filters.append({
            "$or": [
                {
                    "full_name": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
                {
                    "license_number": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
                {
                    "phone": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
            ]
        })

    if driver_status is not None:
        filters.append({
            "status": driver_status.value
        })

    if license_class is not None:
        filters.append({
            "license_class": license_class.value
        })

    query = Driver.find(*filters)

    total = await query.count()

    drivers = await (
        query.sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    return DriverListResponse(
        items=[
            await driver_to_response(driver)
            for driver in drivers
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_driver(driver_id):
    driver = await get_driver_document(driver_id)
    return await driver_to_response(driver)


async def update_driver(driver_id, data: DriverUpdate):
    driver = await get_driver_document(driver_id)

    changes = data.model_dump(
        exclude_unset=True,
        exclude={"linked_user_email"},
    )

    new_license = changes.get("license_number")

    if (
        new_license is not None
        and new_license != driver.license_number
    ):
        existing = await Driver.find_one(
            Driver.license_number == new_license
        )

        if existing is not None:
            raise DriverAlreadyExistsError(
                "A driver with this license already exists."
            )

    if "linked_user_email" in data.model_fields_set:
        linked_user = await resolve_driver_user(
            data.linked_user_email,
            exclude_driver_id=driver_id,
        )

        changes["user_id"] = (
            linked_user.id if linked_user else None
        )

    for field_name, value in changes.items():
        setattr(driver, field_name, value)

    driver.updated_at = datetime.now(timezone.utc)

    try:
        await driver.save()
    except DuplicateKeyError as exc:
        raise DriverAlreadyExistsError(
            "Driver license or linked account already exists."
        ) from exc

    return await driver_to_response(driver)


async def check_driver_compatibility(
    driver_id,
    vehicle_id,
):
    driver = await get_driver_document(driver_id)

    if not ObjectId.is_valid(vehicle_id):
        raise DriverVehicleNotFoundError(
            "Vehicle not found."
        )

    vehicle = await Vehicle.get(ObjectId(vehicle_id))

    if vehicle is None:
        raise DriverVehicleNotFoundError(
            "Vehicle not found."
        )

    compatible, eligible, reason = evaluate_driver_vehicle(
        driver,
        vehicle,
    )

    return DriverCompatibilityResponse(
        driver_id=str(driver.id),
        vehicle_id=str(vehicle.id),
        license_compatible=compatible,
        eligible_for_dispatch=eligible,
        reason=reason,
    )