# standard
from typing import Callable, Tuple, Any
from datetime import datetime
# external
from pydantic import BaseModel, model_validator
# internal
from .types import ObservedProperties
from ..sensor_things.core import Observation

class NativePayloadTransformer(BaseModel):
    """Transforms a native sensor payload into SensorThings Observations. """
    app_phenomenon_time: datetime | None = None
    TRANSFORM: dict[str, Callable] = {}
    NAME_TRANSFORM: dict[str, ObservedProperties]
    
    @model_validator(mode="after")
    def _validate_transformers(self):
        try:
            if not self.NAME_TRANSFORM:
                raise NotImplementedError(
                        f"{self.__class__} must implement a non-empty "
                        "NAME_TRANSFORMER."
                        )
        except AttributeError:
            raise AttributeError(
                    f"{self.__class__} must implement a NAME_TRANSFORM dict."
                    )
        return self

    @classmethod
    def from_unpack(
            cls, 
            observations:dict[str, Any], 
            app_phenomenon_time: datetime | None 
            ):
        payload = {
            k.lower(): v
            for k, v in observations.items()
        }
        app_payload = cls(**payload)
        app_payload.app_phenomenon_time = app_phenomenon_time
        return app_payload
    
    def _transform(self) -> dict[ObservedProperties, Any]:
        """Apply the transformations """
        for observed_property in self.TRANSFORM:
            value = getattr(self, observed_property)
            self.__setattr__(
                    observed_property, 
                    self.TRANSFORM[observed_property](value)
                    )

        transformed_results: dict[ObservedProperties, Any] = {}
        for observed_property, datastream in self.NAME_TRANSFORM.items(): 
            transformed_results[datastream] = getattr(self, observed_property)
        return transformed_results

    def to_stObservations(self) -> list[Tuple[Observation, ObservedProperties]]:
        """Return a tuple of observations and corresponding datastream."""
        transformed_results = self._transform()
        observations = []
        for datastream, value in transformed_results.items():
            if datastream == ObservedProperties.PHENOMENON_TIME:
                continue
            observation = Observation(
                result=value,
                phenomenonTime=(
                    transformed_results.get(ObservedProperties.PHENOMENON_TIME) 
                    or self.app_phenomenon_time
                    ),
            )
            observations.append((observation, datastream.value))
        return observations

