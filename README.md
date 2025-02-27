# st-utils

## What is it?

**st-utils** (SensorThings Utilities) is a suite of tools for managing networks of *heterogeneous* sensors using the [OGC SensorThings](https://www.ogc.org/publications/standard/sensorthings/) data model.

## Table of Contents

- [st-utils](#st-utils)
  - [What is it?](#what-is-it)
  - [Table of Contents](#table-of-contents)
  - [Requirements](#requirements)
  - [Installation](#installation)
    - [Using UV](#using-uv)
    - [Using Pip](#using-pip)
  - [Sensors](#sensors)
  - [YAML Sensor Configuration Files](#yaml-sensor-configuration-files)
    - [Add a YAML Template for New Sensor Support](#add-a-yaml-template-for-new-sensor-support)
    - [Add Real World Sensor Configurations](#add-real-world-sensor-configurations)
  - [Extract, Transform and Stream Functions](#extract-transform-and-stream-functions)
    - [Extract Function](#extract-function)
    - [Transform Function](#transform-function)
    - [Stream Function](#stream-function)
  - [Supported Sensor Models](#supported-sensor-models)

## Requirements

**st-utils** requires the following: 

- **Python 3.13**
- A running instance of [FROST Server](https://github.com/FraunhoferIOSB/FROST-Server) must be available; follow the [instructions](https://fraunhoferiosb.github.io/FROST-Server/deployment/tomcat.html) for installation. `FROST Server` will handle connections and transactions with a `PostgreSQL` database with the `PostGIS` extension (all included in the instructions above).
- An `.env` file at the project root with the following environment variables:
    - `FROST_ENDPOINT` = "\<END POINT URL\>" , e.g.:

```bash
FROST_ENDPOINT=http://localhost:8080/FROST-Server.HTTP-2.5.3/v1.1
```
- Sensors, of course (see [Sensors](#sensors))

## Installation

### Using UV

```bash
uv venv --python=3.13
uv pip install git+<URL>
```

### Using Pip

```bash
python -m venv venv
source venv/bin/activate
pip install git+<URL>
```

## Sensors

Methods for accessing sensor observations vary across sensor brands. Some models will handle remote storage and provide web-based such as dashboards and APIs. Other configurations may include data-loggers, and more "DIY" solutions such as Arduino are also valid. Furthermore, the observations themselves are likely to use varying serialization schemas.

What **st-utils** offers is a standarized way of *Extracting, Transforming and Loading* (ETL) the data from a wide network of sensors. Support for various sensors brands is added progressively, requires the development of:

- A `YAML` configuration file template for a specific sensor brand ([Creating a YAML Config](#sensor-yaml-configuration-files))
- The design of 3 functions in a separate python file:
  - `_extract`
  - `_transform`
  - `stream`

For example, support for the Netatmo NWS03 is provided by `/sensor_configs/netatmo/netatmo_nws03.yaml`. The `netatmo.stream` function wraps `_extract` and `_transform` methods in the `netatmo.py` file.

## YAML Sensor Configuration Files

`YAML` is a human-readable, nested data structure similar to `JSON`. `st-utils` expects a configuration file to contain at five top-level keys, namely: `sensors`, `things`, `locations`, `datastreams` and `observedProperties`. A high-level template is provided in [`\sensor_configs`](sensor_configs/template.yaml). These five keys are equivalent to the main objects in the SensorThings datamodel:

![](docs/readme_sensorThingsDataModel.png)

Sensor configuration files are generally created twice:

1. When general support for a new sensor is added,
2. When initializing an actual sensor arrangement, 

### Add a YAML Template for New Sensor Support

To add support for a new sensor typology:

1. Make a new directory in the [`\sensor_configs`](sensor_configs), whose name should match the sensor name,
2. Using the general [template](sensor_configs/template.yaml), fill out the fields in the `sensors` and `datastreams` items.
3. Place a `.gitignore` to ignore all files in these directories, except for the template

### Add Real World Sensor Configurations

Using the template which has just been created (or one provided, if support for your sensor is already available), set up a real world sensor arrangement. Each file represents ONE sensor object and all its associations. Thus if you are setting up 10 sensors, you should expect to 10 sensor config files. `Locations`, `Things`, `ObservedProperties` MAY be common among different sensors, just make sure that the items are identical. The function which parses the configuration file will infer the items are the same, and not create two identical locations.

1. Copy the template, the filename should be the sensor MAC address,
2. Fill out all the details that remain pending, make sure to copy and paste identical items from one file to another to avoid creating duplicate entities later on.

## Extract, Transform and Stream Functions

Since every sensor is expected to be just a little bit different, a separate set of logic must be prepared for each newly supported sensor typology. In order to standardize the approach, for each new sensor we expect three functions: `_extract`, `_transform` and `stream`.

### Extract Function

The `_extract` function handles querying the observations from a sensor's data infrastructure. It shall return a `Dict[str, Dict[str, Any]]` object. The primary key should be some unique identifier: if multiple sensors are being queried there should be no confusion as to what data belongs to what sensor. All sensors should be queried at the same time, thus one object will be returned where each key is the unique reference to a specific sensor. The nested `Dict` should have keys which are the references to the datastreams available by that sensor and values which are the respective observation results.

### Transform Function

The `_transform` function essentially maps out the sensor native keys to the respective names of the datastreams found in the earlier prepared `YAML` configuration files. For example:

```python
# keys = sensor native key
# values = datastream names
NETATMO_TO_DATASTREAM_MAP = {
    "Temperature": "temperature_indoor",
    "CO2": "co2",
    "Humidity": "humidity",
    "Noise": "noise",
    "Pressure": "pressure",
    "AbsolutePressure": "absolute_pressure",
}
```

The `_transform` shall take a `Dict[str, Any]` and return a NamedTuple with fields `sensor_name (str)`, `datastream_name (str)`, `result (Any)`, `result_time (datetime)`.

### Stream Function

The stream function is a wrapper around the the `_extract` and `_transform` functions and returns a `Tuple[Observations, ...]`, and expects a `sleep_time (int)`.

## Supported Sensor Models

The following sensors are currently supported:

- [Netatmo Home Weather Station (NWS03)](https://www.netatmo.com/en-eu/smart-weather-station)



