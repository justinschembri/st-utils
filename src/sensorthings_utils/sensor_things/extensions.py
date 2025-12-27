"""
Extensions and wrappers to facilitate OGC SensorThings compliant implementations.
"""

# standard
from typing import Dict, List, Any, Type, Literal, Optional, Tuple, TYPE_CHECKING
from pathlib import Path
import logging

# external
import yaml

from sensorthings_utils.exceptions import FailedSensorConfigValidation
from sensorthings_utils.transformers.types import SensorID, SupportedSensors

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
from ..monitor import netmon

debug_logger = logging.getLogger("debug")
# typing and type-checking
if TYPE_CHECKING:
    ...

__all__ = ["SensorConfig", "SensorArrangement"]

main_logger = logging.getLogger("main")


class SensorConfig:
    """
    Dict-like sensor-configuration structure.

    Class is responsible for parsing, validating and serving sensor configuration.

    Args
        - data (Dict[str, Any]) - contents of the sensor config.
        - is_valid (bool)
        - model (str) - sensor model
        - name (str) - sensor name
    """

    def __init__(self, filepath: str | Path) -> None:
        self._filepath = Path(filepath)
        self.data: Dict[str, Any] = self._load()
        self.is_valid = self.check_validity()[0]
        self._set_metadata()
        # below metadata attrs set by fn above
        self.model: SupportedSensors
        self.name: SensorID

    def _set_metadata(self) -> None:
        """Set sensor metadata attrs."""
        model = next(iter(self.data["sensors"]))
        self.model = SupportedSensors(model)
        self.name = self.data["sensors"][self.model.value]["name"]

    def _load(self) -> Dict:
        """Safely load configuration file."""
        with open(self._filepath, "r") as file:
            data = yaml.safe_load(file)
        return data

    # TODO: poor logic to be rewritten.
    def __getitem__(self, key) -> Any:
        if self.check_validity is None:
            self.check_validity()
        if self.check_validity is False:
            main_logger.error(
                f"The SensorConfig {self._filepath.name} is invalid."
                + " Passing to other functions may cuase unexpected "
                + " behaviour."
            )
        return self.data.get(key)

    def check_validity(self) -> Tuple[bool, list[str]]:
        """
        Run a number of validation checks on a configuration file, return True
        if config is valid.
        """
        valid_entity_contents = self._validate_entity_contents(self.data)
        valid_entity_sizes = self._validate_entity_sizes(self.data)
        valid_iot_link = self._validate_iot_links(self.data)

        if not all(
            [
                valid_entity_contents[0],
                valid_entity_sizes[0],
                valid_iot_link[0],
            ]
        ):
            main_error = f"{self._filepath.name} is an invalid config."
            main_logger.error(main_error)
            # errors returned from the validity functions are
            # tuples(bool, <error_msg> | None)
            errors = (
                [main_error]
                + valid_entity_contents[1]
                + valid_entity_sizes[1]
                + valid_iot_link[1]
            )

            netmon.add_count("sensor_config_fail", 1)
            return (False, errors)
        else:
            success_msg = f"{self._filepath.name} is a valid config."
            main_logger.info(success_msg)
            return (True, [success_msg])

    def _validate_entity_contents(
        self, unvalidated_data: Dict
    ) -> Tuple[bool, List[str]]:
        "Check that primary sensor things keys are there, and that the contents are as expected."
        expected_top_level_keys = [
            "sensors",
            "things",
            "locations",
            "datastreams",
            "observedProperties",
        ]
        expected_class_fields = {
            "sensors": {
                "name": str,
                "description": (str, dict),
                "properties": (str, dict),
                "encodingType": str,
                "metadata": str,
                "iot_links": dict,
            },
            "things": {
                "name": str,
                "description": str,
                "properties": (str, dict, type(None)),
                "iot_links": dict,
            },
            "locations": {
                "name": str,
                "description": str,
                "properties": (str, dict, type(None)),
                "encodingType": str,
                "location": dict,
                "iot_links": dict,
            },
            "datastreams": {
                "name": str,
                "description": str,
                "observationType": str,
                "unitOfMeasurement": dict,
                "observedArea": dict,
                "phenomenon_time": (str, type(None)),
                "result_time": (str, type(None)),
                "properties": (dict, type(None)),
                "iot_links": dict,
            },
            "observedProperties": {
                "name": str,
                "definition": str,
                "description": str,
                "properties": (str, type(None)),
            },
        }
        # entity is going to be sensors, things, locations, etc.
        invalid = False
        error_list = []
        for key in expected_top_level_keys:
            # Check if all top level keys are there:
            if (actual_entity := unvalidated_data.get(key)) is None:
                error = f"{self._filepath.stem} is missing primary key: {key}. \
                    Will not continue with validation."
                main_logger.error(error)
                error_list.append(error)
                return (False, error_list)
            # Check if return of top level keys is correct:
            if not isinstance(actual_entity, dict):
                error = f"{self._filepath.stem} returned {type(actual_entity)} \
                    not dict. Will not continue with validation."
                main_logger.error(error)
                error_list.append(error)
                return (False, error_list)
            # item is going to be each entry, e.g., 70:33:50.. (sensor), "apartment" (location)
            expected_field_keys = set(expected_class_fields[key].keys())
            for field_key in actual_entity:
                if not isinstance(actual_entity[field_key], dict):
                    error = f"{self._filepath.stem}'s {field_key}'s children are of \
                        type {type(actual_entity[field_key])} not dict. \
                        Will not continue with validation."
                    main_logger.error(error)
                    error_list.append(error)
                    return (False, error_list)
                actual_field_keys = set(actual_entity[field_key].keys())
                missing_field_keys = expected_field_keys - actual_field_keys
                extra_field_keys = actual_field_keys - expected_field_keys
                if missing_field_keys:
                    error = f"{key}.{field_key} has missing keys: {missing_field_keys}."
                    error_list.append(error)
                    main_logger.error(error)
                    invalid = True
                if extra_field_keys:
                    error = f"{key}.{field_key} has extra keys: {extra_field_keys}."
                    main_logger.error(error)
                    error_list.append(error)
                    invalid = True
                for field in actual_entity[field_key]:
                    expected_type = expected_class_fields[key][field]
                    if not isinstance(actual_entity[field_key][field], expected_type):
                        error = (
                            f"{key}.{field_key}.{field} is of the wrong type "
                            + f"expected {expected_type}, got {type(actual_entity[field_key][field])}"
                        )
                        error_list.append(error)
                        main_logger.error(error)
                        invalid = True

        return (True, []) if not invalid else (False, error_list)

    def _validate_entity_sizes(
        self, unvalidated_data: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        Validate size of entities.

        A valid sensor config file should contain:

            - exactly one (1) sensor,

        """
        # TODO: unimplemented
        return (True, [])

    def _validate_iot_links(
        self, unvalidated_data: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """Validate a series of expected links between entities."""

        expected_iot_link_groups = {
            "sensors": ["datastreams"],
            "things": ["datastreams", "locations"],
            "locations": ["things"],
            "datastreams": ["observedProperties", "sensors", "things"],
        }

        invalid = False
        error_list = []
        # These first loops walk through entity groups (sensors, things, etc.)
        # and the entity instances in those group, checking that the iot_links
        # which are expected to be present in the config file are there.
        for entity_type, entity_instances in unvalidated_data.items():
            try:
                # observedProperties have no iot_links.
                if entity_type in ["observedProperties"]:
                    continue
                for entity, entity_fields in entity_instances.items():
                    passed_links = entity_fields["iot_links"]
                    exp_links = expected_iot_link_groups[entity_type]
                    extra_links = set(passed_links) - set(exp_links)
                    missing_links = set(exp_links) - set(passed_links)
                    if extra_links:
                        error = (
                            f"{self._filepath.name}.{entity_type}."
                            + f"{entity} has extra iot_links: "
                            + f"{extra_links}."
                        )
                        error_list.append(error)
                        main_logger.error(error)
                        invalid = True
                    if missing_links:
                        error = (
                            f"{self._filepath.name}.{entity_type}."
                            + f"{entity} is missing iot_link: "
                            f"{missing_links}."
                        )
                        error_list.append(error)
                        main_logger.error(error)
                        invalid = True
                    # The next loop confirms that the iot_link specified exist
                    # in the config file.
                    for declared_datastream, link_list in passed_links.items():
                        if not link_list:
                            error = (
                                f"{self._filepath.name}.{entity_type}."
                                + f"{entity} has an empty iot_link."
                            )
                            error_list.append(error)
                            main_logger.error(error)
                            invalid = True
                            continue
            except Exception as e:
                raise FailedSensorConfigValidation(
                    f"Unhandled exception in {self._filepath}: " f"{type(e)}:{e}."
                )
                # several lines removed here which can be reimplemented,
                # see 32392b2
        return (True, []) if not invalid else (False, error_list)


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
        "observedProperties": ObservedProperty,
    }

    name_mappings: Dict[
        str, Literal["Sensor", "Thing", "Location", "Datastream", "ObservedProperty"]
    ] = {
        "sensors": "Sensor",
        "things": "Thing",
        "locations": "Location",
        "datastreams": "Datastream",
        "observedProperties": "ObservedProperty",
    }

    def __init__(self, sensor_config: "SensorConfig"):
        self._sensor_config = sensor_config
        self._unlinked_arrangement: List["SensorThingsObject"] = self._initial_setup()
        # public:
        self.linked_arrangement: Tuple[SensorThingsObject, ...] = self._link_iot()

    def __repr__(self) -> str:
        return (
            f"SensorArrangement (Sensor={self.get_entities("Sensor")[0].name}, "
            + f"SensorThingsObjects={len(self.linked_arrangement)})"
        )

    def _initial_setup(self) -> List[SensorThingsObject]:
        """
        Return an unlinked list of SensorThingsObjects inferred from the class `arrangement_map`.

        Unpack the SensorConfig, unpack values into SensorThings objects.
        """
        unlinked_arrangement = []
        arrangement_map = self._sensor_config
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
    ) -> SensorThingsObject:
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
        raise KeyError(f"Keys {entity=}, {field=} and {instance=} not found.")

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
