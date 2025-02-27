"""
Pure OGC SensorThings dataclasses.
"""

# standard
from typing import Optional, Any, Dict, List, Literal
from typing_extensions import Annotated, Self
from datetime import datetime

# external
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
    computed_field,
)

# internal
# TODO: #1 consider the implementation of ENUMS for SensorThingsObjects throughout?
SENSOR_THINGS_OBJECTS = [
    "sensors",
    "things",
    "locations",
    "datastreams",
    "observedProperties",
]


class SensorThingsObject(BaseModel):
    """
    Parent dataclass for all non-observation OGC Sensor Things Objects.

    Attribute names (and formatting) match those used by the SensorThings Data model,
    thus the use of camelCase.
    """

    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    iot_links: Dict[
        Literal["sensors", "things", "locations", "datastreams", "observedProperties"],
        List[str],
    ] = {}

    @computed_field
    @property
    def st_type(self) -> str:
        return self.__class__.__name__

    # TODO: #4 The state of iot_links as 'str' should be temporary or stored in another attribute.
    def __hash__(self) -> int:
        return hash((self.name, str(self.__class__)))

    def __repr__(self) -> str:
        return self.__repr_name__() + " (name=" + self.name + ")"

    def set_iot_link(
        self,
        entity: Literal[
            "sensors", "things", "locations", "datastreams", "observedProperties"
        ],
        instance: str,
        sensor_things_object: "SensorThingsObject",
    ) -> None:
        """Set an `iot_link` dict value."""
        set_index = self.iot_links[entity].index(instance)
        self.iot_links[entity][set_index] = sensor_things_object  # type: ignore


class Sensor(SensorThingsObject):
    encodingType: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    metadata: Optional[Any] = None
    id: Optional[int] = None


class Thing(SensorThingsObject):
    id: Optional[int] = Field(
        None, description="Generally assigned by the server."
    )  # TODO: #3 Do you really need an id field?


class Datastream(SensorThingsObject):
    observationType: str
    unitOfMeasurement: Optional[Dict[str, Any]] = Field(default_factory=dict)
    id: Optional[int] = Field(None, description="Generally assigned by the server.")


class Location(SensorThingsObject):
    encodingType: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    location: dict


class ObservedProperty(SensorThingsObject):
    definition: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]


class Observation(BaseModel):
    result: Any
    phenomenonTime: datetime | None
    iot_links: int | None = None
    resultTime: datetime | None = None
    validTime: "TimePeriod | None" = None

    @computed_field
    @property
    def st_type(self) -> str:
        return self.__class__.__name__


class TimePeriod(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def check_valid_time(self) -> Self:
        if self.end < self.start:
            raise ValueError("End period before start period.")
        return self
