from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel, Field


class RouteStop(BaseModel):
    order_id: PydanticObjectId
    kind: Literal["pickup", "delivery"]
    address: str = Field(min_length=3, max_length=500)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)