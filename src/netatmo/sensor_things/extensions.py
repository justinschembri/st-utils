"""
Extensions and wrappers to facilitate OGC SensorThings compliant implementations.
"""

# standard
from typing import Dict, List, Any, Type, Literal, Optional, Tuple, TYPE_CHECKING
from pathlib import Path

# external
import yaml

# internal
from .core import (
    Sensor,
    Thing,
    Datastream,
    Location,
    ObservedProperty,
    SensorThingsObject,
    SENSOR_THINGS_OBJECTS,
)

# typing and type-checking
if TYPE_CHECKING:
    ...

__all__ = ["SensorArrangementMap", "SensorArrangement"]


class SensorArrangementMap:
    """
    Dict-like dataclass originating from a parsed and validated sensor config file.

    The map essentially contains all the information required to set up a data model
    which represents the physical set up  of the sensor in the real world.
    """

    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self.config_dict: Dict = self._validate_structure(self._load())

    def _load(self) -> Dict:
        with open(self.filepath, "r") as file:
            data = yaml.safe_load(file)
        return data

    def __getitem__(self, key) -> Any:
        return self.config_dict.get(key)

    def _validate_structure(self, data: Dict) -> Dict:
        """Validating the data-structure of a config file"""
        if set(data.keys()) != set(SENSOR_THINGS_OBJECTS):
            raise ValueError(
                f"Invalid configuration file keys: {data.keys()} does not match + "
                f"{SENSOR_THINGS_OBJECTS}"
            )
        return data


class SensorArrangement:
    """
    Represents a single instance of the OGC SenorThings data model.

    An aggregation of 1 Sensor and 0 or more Things, Locations, Datastreams and
    ObservedProperties. Adherence to the datamodel implies this class includes: 1 Sensor,
    which may is linked to 0..* Datastreams. Each datastream is associated to 1 Thing
    and 1 ObservedProperty respectively. A Thing is associated with 0..* Locations. The
    class attributes consistently uses the plural form (i.e., sensors, things,
    datastreams etc.) although it will always include ONE sensor.
    """

    class_mappings: Dict[str, Type["SensorThingsObject"]] = {
        "sensors": Sensor,
        "things": Thing,
        "locations": Location,
        "datastreams": Datastream,
        "observed_properties": ObservedProperty,
    }

    name_mappings: Dict[
        str, Literal["Sensor", "Thing", "Location", "Datastream", "ObservedProperty"]
    ] = {
        "sensors": "Sensor",
        "things": "Thing",
        "locations": "Location",
        "datastreams": "Datastream",
        "observed_properties": "ObservedProperty",
    }

    def __init__(self, arrangement_map: "SensorArrangementMap"):
        self.arrangement_map = arrangement_map
        self._unlinked_arrangement: List["SensorThingsObject"] = self._initial_setup()
        self.linked_arrangement: Tuple[SensorThingsObject, ...] = self._link_iot()

    def __repr__(self) -> str:
        return (
            f"SensorArrangement (Sensor={self.get_entities("Sensor")[0].name}, "
            + f"SensorThingsObjects={len(self.linked_arrangement)})"
        )

    def _initial_setup(self) -> List[SensorThingsObject]:
        """
        Return an unlinked list of SensorThingsObjects inferred from the class `arrangement_map`.
        """
        unlinked_arrangement = []
        arrangement_map = self.arrangement_map
        for entity in SENSOR_THINGS_OBJECTS:
            names = [_ for _ in arrangement_map[entity].keys()]
            for i in names:
                unlinked_arrangement.append(
                    SensorArrangement.class_mappings[entity](
                        **arrangement_map[entity][i]
                    )
                )
        return unlinked_arrangement

    def _link_iot(self) -> Tuple[SensorThingsObject, ...]:
        """Replace str representations of iot_links with SensorThingsObjects."""
        unlinked_arrangement = self._unlinked_arrangement
        for sensor in unlinked_arrangement:
            for entity, instances in sensor.iot_links.items():
                for idx, i in enumerate(instances):
                    e = self.name_mappings[entity]
                    sensor.set_iot_link(entity, i, self.get(e, instance=i))
        return tuple(unlinked_arrangement)

    def get(
        self,
        entity: Literal[
            "Sensor", "Thing", "Location", "Datastream", "ObservedProperty"
        ],
        instance: str,
        field: Optional[str] = None,
    ):
        # this method is first called in the _link_iot function, before
        # self.linked_arrangement has been declared, so:
        query_arrangement = self._unlinked_arrangement or self.linked_arrangement
        for sensor_things_object in query_arrangement:
            if (
                sensor_things_object.__class__.__name__ == entity
                and sensor_things_object.name == instance
            ):
                if field:
                    return sensor_things_object.__dict__[field]
                elif not field:
                    return sensor_things_object  # type: ignore

        raise KeyError(f"Keys {entity}, {field} and {instance} not found.")

    def get_entities(
        self,
        entity: Literal[
            "Sensor", "Thing", "Location", "Datastream", "ObservedProperty"
        ],
    ) -> List["SensorThingsObject"]:
        entity_list = []
        for sensor_things_object in self.linked_arrangement:
            if sensor_things_object.__class__.__name__ == entity:
                entity_list.append(sensor_things_object)
        return entity_list
