# Sensor Configuration Templates

This document provides detailed information about sensor configuration files and the template-based generation system.

## Overview

Each physical sensor in your network requires a YAML configuration file that describes:
- The sensor hardware and its capabilities
- The physical thing being monitored (building, room, component, etc.)
- The geographic location where measurements are taken
- The datastreams (data streams) produced by the sensor
- The observed properties (what is being measured)

## Template-Based Generation

For supported sensor models, you can use the CLI to generate configuration files from templates:

```bash
stu generate-config <sensor-model>
```

Supported sensor models:
- `milesight.am103l` - Milesight AM103L Indoor Air Quality Sensor
- `milesight.am308l` - Milesight AM308L Indoor Air Quality Sensor (7-in-1)
- `netatmo.nws03` - Netatmo NWS03 Home Weather Station

The generator will prompt you for user-specific information:
- **Sensor ID/Name**: Typically the device MAC address (e.g., `24E124707D378803` or `70:ee:50:7f:9d:32`)
- **Thing Name**: Name of the physical thing being monitored (e.g., "Room 120", "Apartment 3")
- **Thing Description**: Description of the thing
- **Location Name**: Name of the geographic location
- **Location Description**: Description of the location
- **Longitude**: Longitude coordinate (decimal degrees, -180 to 180)
- **Latitude**: Latitude coordinate (decimal degrees, -90 to 90)

All standard datastreams, observedProperties, units of measurement, and sensor properties are automatically populated from the template.

## Template Files

Template files are located in `deploy/sensor_configs/`:
- `template_milesight.am103l.yaml`
- `template_milesight.am308l.yaml`
- `template_netatmo.nws03.yaml`
- `template.yaml` (generic template for custom sensors)

Templates are tracked in git, while generated configuration files (specific to your sensors) are ignored.

## File Structure

Each sensor configuration file must contain the following sections:

### 1. Sensors Section

Defines the physical sensor hardware:

```yaml
sensors:
  <sensor-key>:  # Format: <model>.<type> (e.g., milesight.am103l) or MAC address
    name: <sensor-name>  # Typically matches the device MAC address
    description: <description>
    metadata: <url-or-none>
    encodingType: <encoding-type>
    properties: <properties-dict-or-null>
    iot_links:
      datastreams: <list-of-datastream-names>
```

Key points:
- The sensor key can be in `<model>.<type>` format or a MAC address
- The sensor `name` field should typically match the device MAC address
- The `name` field must also match the filename (without `.yaml` extension)
- `iot_links.datastreams` lists all datastream names this sensor produces

### 2. Things Section

Defines the physical thing being monitored:

```yaml
things:
  <thing-name>:
    name: <thing-name>  # Must match the key above
    description: <description>
    properties: <properties-dict-or-null>
    iot_links:
      datastreams: <list-of-datastream-names>
      locations: <list-of-location-names>
```

### 3. Locations Section

Defines the geographic location:

```yaml
locations:
  <location-name>:
    name: <location-name>  # Must match the key above
    description: <description>
    properties: <properties-dict-or-null>
    encodingType: application/geo+json
    location:
      type: <geometry-type>  # Point, Polygon, LineString, etc.
      coordinates: [<longitude>, <latitude>]  # GeoJSON format
    iot_links:
      things: <list-of-thing-names>
```

Important:
- Coordinates must follow GeoJSON format: `[longitude, latitude]` for Point type
- Longitude: -180 to 180 (e.g., 4.37034)
- Latitude: -90 to 90 (e.g., 52.00482)

### 4. Datastreams Section

Defines the data streams produced by the sensor:

```yaml
datastreams:
  <datastream-name>:
    name: <datastream-name>  # Must match the key above
    description: <description>
    observationType: instant  # Typically "instant" for real-time sensors
    unitOfMeasurement:
      name: <unit-name>
      symbol: <unit-symbol>
      definition: <ucum-url>
    observedArea:
      type: <geometry-type>
      coordinates: <coordinates-or-null>
    phenomenon_time: null  # Typically null for instant observations
    result_time: null  # Typically null for instant observations
    properties: <properties-dict-or-null>
    iot_links:
      observedProperties: [<observed-property-name>]
      sensors: [<sensor-name>]
      things: [<thing-name>]
```

Key points:
- Each datastream name must appear in the sensor's `iot_links.datastreams` list
- Each datastream links to exactly one observedProperty, one sensor, and one thing
- Use YAML anchors (`&`) and aliases (`*`) to avoid repetition (e.g., for shared `observedArea` or `unitOfMeasurement`)

### 5. ObservedProperties Section

Defines the properties being observed:

```yaml
observedProperties:
  <observed-property-name>:
    name: <observed-property-name>  # Must match the key above
    definition: <definition-url>
    description: <description>
    properties: <properties-dict-or-null>
```

Important:
- ObservedProperties do NOT have `iot_links`
- Each datastream must reference exactly one observedProperty

## Key Requirements and Best Practices

### File Naming

- **One sensor per file**: Each configuration file describes exactly one sensor
- **Filename convention**: The filename should match the sensor name (typically the device MAC address)
- Example: Sensor name `24E124707D378803` → filename `24E124707D378803.yaml`

### iot_links

- All `iot_links` references must use entity **names** (not keys)
- Example: If your sensor key is `milesight.am103l` but the sensor name is `24E124707D378803`, use `24E124707D378803` in iot_links

### YAML Anchors and Aliases

Use YAML anchors (`&`) and aliases (`*`) to avoid repetition:

```yaml
datastreams:
  temperature:
    unitOfMeasurement: &temperature
      name: degree Celsius
      symbol: °C
      definition: https://unitsofmeasure.org/ucum#para-30
    observedArea: &observedArea
      type: Polygon
      coordinates: null
  
  humidity:
    unitOfMeasurement:  # Different unit, no alias
      name: percent
      symbol: "%"
      definition: https://unitsofmeasure.org/ucum#para-29
    observedArea: *observedArea  # Reuse the anchor
```

### Validation

Each configuration file must:
- Have all required sections (sensors, things, locations, datastreams, observedProperties)
- Have matching entity names in iot_links
- Have exactly one datastream per datastream name listed in the sensor's iot_links
- Have valid GeoJSON coordinates
- Reference valid observedProperties, sensors, and things

Validate your configuration files:

```bash
stu validate <path-to-config-file.yaml>
```

Or validate all configuration files in the current directory:

```bash
stu validate
```

## Standard Datastreams by Sensor Model

### Milesight AM103L

- `battery_level` - Battery level of the sensor
- `co2` - CO₂ levels
- `humidity` - Humidity levels
- `temperature_indoor` - Indoor temperature

### Milesight AM308L

- `battery_level` - Battery level of the sensor
- `co2` - CO₂ levels
- `humidity` - Humidity levels
- `temperature_indoor` - Indoor temperature
- `light_level` - Light levels
- `passive_infrared` - Motion detection (PIR)
- `particulate_matter_10` - PM10 levels
- `particulate_matter_2_5` - PM2.5 levels
- `gauge_pressure` - Pressure levels
- `total_volatile_organic_compounds` - TVOC levels

### Netatmo NWS03

- `temperature_indoor` - Indoor temperature
- `humidity` - Humidity levels
- `co2` - CO₂ levels
- `gauge_pressure` - Gauge pressure
- `absolute_pressure` - Absolute pressure
- `noise` - Noise levels

## Example: Generating a Configuration

```bash
$ stu generate-config milesight.am103l

Generating configuration for milesight.am103l
==================================================
Sensor ID/Name (typically MAC address): 24E124707D378803

Thing Configuration:
Thing name: Room 120
Thing description: An office room in the Architecture Faculty

Location Configuration:
Location name: TU Delft BK.01.West.120
Location description: Room 120 on the First Floor of the West Wing
Longitude: 4.37034
Latitude: 52.00482

✓ Configuration generated successfully: deploy/sensor_configs/24E124707D378803.yaml

Next steps:
  1. Review the configuration file
  2. Validate it using: stu validate deploy/sensor_configs/24E124707D378803.yaml
```

## Manual Template Usage

If you prefer to create configurations manually:

1. Copy a template file:
   ```bash
   cp deploy/sensor_configs/template_milesight.am103l.yaml deploy/sensor_configs/<your-sensor-name>.yaml
   ```

2. Replace placeholders:
   - `<SENSOR_ID>` → Your sensor ID/name (e.g., MAC address)
   - `<THING_NAME>` → Your thing name
   - `<THING_DESCRIPTION>` → Your thing description
   - `<LOCATION_NAME>` → Your location name
   - `<LOCATION_DESCRIPTION>` → Your location description
   - `<LONGITUDE>` → Longitude coordinate
   - `<LATITUDE>` → Latitude coordinate

3. Validate the file:
   ```bash
   stu validate deploy/sensor_configs/<your-sensor-name>.yaml
   ```

## Troubleshooting

### Common Errors

**"Template not found"**
- Ensure you're using a supported sensor model name
- Check that template files exist in `deploy/sensor_configs/`

**"Validation failed"**
- Check that all iot_links references use entity names (not keys)
- Ensure coordinates are in GeoJSON format: `[longitude, latitude]`
- Verify that all referenced entities (sensors, things, locations, observedProperties) exist

**"Sensor name mismatch"**
- The sensor `name` field must match the filename (without `.yaml` extension)
- All iot_links must reference the sensor by its `name`, not its key

For more help, see the validation error messages or consult the example configuration files in `deploy/sensor_configs/`.
