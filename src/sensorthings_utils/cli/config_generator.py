"""Generate sensor configuration files from templates."""

# standard
import yaml
from pathlib import Path
from typing import Any, Dict

# external
from rich.console import Console

# internal
from ..paths import SENSOR_CONFIG_PATH
from ..transformers.types import SupportedSensors

console = Console()


def _load_template(sensor_model: SupportedSensors) -> Dict[str, Any]:
    """Load template file for a sensor model."""
    # Try direct path first (for backward compatibility)
    template_path = SENSOR_CONFIG_PATH / f"template_{sensor_model.value}.yaml"
    
    # If not found, search recursively in subdirectories
    if not template_path.exists():
        # Extract model prefix (e.g., "netatmo" from "netatmo.nws03")
        model_prefix = sensor_model.value.split('.')[0]
        # Try in subdirectory matching the model prefix
        template_path = SENSOR_CONFIG_PATH / model_prefix / f"template_{sensor_model.value}.yaml"
        
        # If still not found, search recursively for any template matching the pattern
        if not template_path.exists():
            pattern = f"template_{sensor_model.value}.yaml"
            found_templates = list(SENSOR_CONFIG_PATH.rglob(pattern))
            if found_templates:
                template_path = found_templates[0]
            else:
                raise FileNotFoundError(
                    f"Template not found for {sensor_model.value}. "
                    f"Searched in {SENSOR_CONFIG_PATH} and subdirectories. "
                    f"Expected pattern: template_{sensor_model.value}.yaml"
                )
    
    with open(template_path, "r") as f:
        template = yaml.safe_load(f)
    return template


def _replace_placeholders(
    data: Any,
    sensor_id: str,
    thing_name: str,
    thing_description: str,
    location_name: str,
    location_description: str,
    longitude: float,
    latitude: float,
) -> Any:
    """Recursively replace placeholders in data structure."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Replace placeholder keys
            new_key = key
            if key == "<SENSOR_ID>":
                new_key = sensor_id
            elif key == "<THING_NAME>":
                new_key = thing_name
            elif key == "<LOCATION_NAME>":
                new_key = location_name
            
            result[new_key] = _replace_placeholders(
                value, sensor_id, thing_name, thing_description,
                location_name, location_description, longitude, latitude
            )
        return result
    elif isinstance(data, list):
        result = []
        for item in data:
            # Handle coordinate placeholders in lists
            if isinstance(item, str):
                if item == "<LONGITUDE>":
                    result.append(longitude)
                elif item == "<LATITUDE>":
                    result.append(latitude)
                else:
                    result.append(_replace_placeholders(
                        item, sensor_id, thing_name, thing_description,
                        location_name, location_description, longitude, latitude
                    ))
            else:
                result.append(_replace_placeholders(
                    item, sensor_id, thing_name, thing_description,
                    location_name, location_description, longitude, latitude
                ))
        return result
    elif isinstance(data, str):
        # Replace placeholder values
        data = data.replace("<SENSOR_ID>", sensor_id)
        data = data.replace("<THING_NAME>", thing_name)
        data = data.replace("<THING_DESCRIPTION>", thing_description)
        data = data.replace("<LOCATION_NAME>", location_name)
        data = data.replace("<LOCATION_DESCRIPTION>", location_description)
        return data
    else:
        return data


def generate_config_from_template(
    sensor_model: SupportedSensors,
    sensor_id: str,
    thing_name: str,
    thing_description: str,
    location_name: str,
    location_description: str,
    longitude: float,
    latitude: float,
    output_path: Path | None = None,
) -> Path:
    """Generate a sensor configuration file from a template.
    
    Args:
        sensor_model: The sensor model to generate config for
        sensor_id: Sensor ID/name (typically MAC address)
        thing_name: Name of the Thing being monitored
        thing_description: Description of the Thing
        location_name: Name of the Location
        location_description: Description of the Location
        longitude: Longitude coordinate
        latitude: Latitude coordinate
        output_path: Output file path (defaults to CONFIG_PATHS/{sensor_id}.yaml)
    
    Returns:
        Path to the generated configuration file
    """
    # Load template
    template = _load_template(sensor_model)
    
    # Replace placeholders
    config = _replace_placeholders(
        template, sensor_id, thing_name, thing_description,
        location_name, location_description, longitude, latitude
    )
    
    # Coordinates should already be replaced by _replace_placeholders, but ensure they're correct
    if "locations" in config:
        for loc_name, loc_data in config["locations"].items():
            if "location" in loc_data and "coordinates" in loc_data["location"]:
                coords = loc_data["location"]["coordinates"]
                # Ensure coordinates are a list of numbers
                if isinstance(coords, list) and len(coords) == 2:
                    # Check if placeholders weren't replaced (shouldn't happen after _replace_placeholders)
                    if any(isinstance(c, str) and ("<LONGITUDE>" in c or "<LATITUDE>" in c) for c in coords):
                        loc_data["location"]["coordinates"] = [longitude, latitude]
                elif not isinstance(coords, list) or len(coords) != 2:
                    loc_data["location"]["coordinates"] = [longitude, latitude]
    
    # Also replace in datastream iot_links
    if "datastreams" in config:
        for ds_name, ds_data in config["datastreams"].items():
            if "iot_links" in ds_data:
                if "sensors" in ds_data["iot_links"]:
                    ds_data["iot_links"]["sensors"] = [sensor_id]
                if "things" in ds_data["iot_links"]:
                    ds_data["iot_links"]["things"] = [thing_name]
    
    # Update sensor name in sensors section
    if "sensors" in config:
        sensor_key = sensor_model.value
        if sensor_key in config["sensors"]:
            config["sensors"][sensor_key]["name"] = sensor_id
    
    # Determine output path
    if output_path is None:
        output_path = SENSOR_CONFIG_PATH / f"{sensor_id}.yaml"
    else:
        output_path = Path(output_path)
    
    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    return output_path
