from fastapi import APIRouter, Depends, HTTPException

from app.core.access_control import (
    require_roles,
    require_csrf,
)
from app.models.user import Role

from app.schemas.stop_sequencing_schemas import (
    ApplyStopSequenceRequest,
    StopSequenceResponse,
)
from app.services.stop_sequencing_service import (
    SequenceNotFoundError,
    SequenceValidationError,
    SequenceConflictError,
    SequenceUnavailableError,
    get_saved_sequence,
    preview_sequence,
    apply_sequence,
)


router = APIRouter(
    prefix="/trips",
    tags=["Stop Sequencing"],
    dependencies=[
        Depends(
            require_roles(Role.ADMIN, Role.DISPATCHER)
        ),
    ],
)


SEQUENCE_ERRORS = (
    SequenceNotFoundError,
    SequenceValidationError,
    SequenceConflictError,
    SequenceUnavailableError,
)


def handle_sequence_error(exc):
    if isinstance(exc, SequenceNotFoundError):
        status_code = 404
    elif isinstance(exc, SequenceConflictError):
        status_code = 409
    elif isinstance(exc, SequenceUnavailableError):
        status_code = 503
    else:
        status_code = 422

    return HTTPException(
        status_code=status_code,
        detail=str(exc),
    )


@router.get(
    "/{trip_id}/stop-sequence",
    response_model=StopSequenceResponse,
)
async def get_sequence_endpoint(trip_id: str):
    try:
        return await get_saved_sequence(trip_id)
    except SEQUENCE_ERRORS as exc:
        raise handle_sequence_error(exc) from exc


@router.post(
    "/{trip_id}/stop-sequence/preview",
    response_model=StopSequenceResponse,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def preview_sequence_endpoint(trip_id: str):
    try:
        return await preview_sequence(trip_id)
    except SEQUENCE_ERRORS as exc:
        raise handle_sequence_error(exc) from exc


@router.post(
    "/{trip_id}/stop-sequence/apply",
    response_model=StopSequenceResponse,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def apply_sequence_endpoint(
    trip_id: str,
    data: ApplyStopSequenceRequest,
):
    try:
        return await apply_sequence(
            trip_id,
            data.preview_token,
        )
    except SEQUENCE_ERRORS as exc:
        raise handle_sequence_error(exc) from exc