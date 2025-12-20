"""Result types from unpacking and transforming protocols."""
#standard
#external
from typing import Any
from pydantic import BaseModel
#internal

# type definitions
SensorID = str

class SuccessfulUnpack(BaseModel):
    """A successfully unpacked uplink message from an application."""
    unpacked_payload: dict[SensorID, dict[str, Any]]
    
    def __bool__(self) -> bool:
        """A successful unpack is truthy."""
        return True

    def items(self):
        return self.unpacked_payload.items()

    @property
    def sensor_ids(self):
        return self.unpacked_payload.keys()
