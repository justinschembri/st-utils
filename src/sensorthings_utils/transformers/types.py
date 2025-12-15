"""Result types from unpacking and transforming protocols."""
#standard
#external
from typing import Any
from dataclasses import dataclass
from pydantic import BaseModel
#internal

@dataclass(kw_only=True)
class FailedUnpack:
    """Sentinel class for failed unpacking."""
    sensor_id: str | None = None
    application_payload: Any = None

    @property
    def is_success(self) -> bool:
        return False

class SuccessfulUnpack(BaseModel):
    """A successfully unpacked uplink message from an application."""
    unpacked_payload: dict[str, dict[str, Any]]
    
    @property
    def sensor_ids(self):
        return self.unpacked_payload.keys()
