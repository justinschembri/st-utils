# st-utils

## What is it?

**st-utils** (SensorThings Utilities) is an **Extract, Transform and Load**
Internet of Things (IoT) application with data interoperability as its founding
principle.

The application allows for observations from *hetereogeneous* sensor networks
into one normalized stream and structure which conforms with the [OGC
SensorThings](https://www.ogc.org/publications/standard/sensorthings/) standards
and data model: 

```mermaid
flowchart LR
    A@{ shape: processes, label: HTTP IoT Applications}
    B@{ shape: processes, label: MQTT IoT Applications}
    A e1@==> |data stream| C
    C@{ shape: fork, label: "st-utils"}
    B e2@==> |data stream| C
    e1@{ animate: true }
    e2@{ animate: true }
    C --> D[Transform to `OGC SensorThings` Data Model]
    D --> E[(Store)]
    E --> F[Serve]
```

`st-utils` is built on Franhofer's [FROST
Server](https://github.com/FraunhoferIOSB/FROST-Server) and adds a
transformation and management layer.

## System Requirements

The system requirements are fairly minimal:

- `Docker` and `Docker Compose`
- `git`
- `Python >=3.9`
- Internet access

## Deployment Requirements

Deployment requires and assumes the following:

### Upstream Data Sources

You must have authenticated access to one or more Upstream Data Sources.
st-utils supports ingestion from:

- RESTful APIs: Sources providing observations via HTTP GET/POST (e.g.,
  proprietary vendor clouds)

- MQTT Brokers: Sources publishing to topics (e.g., The Things Network). 

### Sensor Specifications and Architecture

The application assumes you have enough information about the sensor *and what
it is observing* to be able to specify enough information to populate the
SensorThings datamodel:

![](docs/readme_sensorThingsDataModel.png)

## Setup

The overall setup involves:

1. Cloning the repository,
2. Setting up mandatory internal credentials, 
3. Setting up external IoT applications and credentials,
4. Writing sensor configuration files.
5. Launching the system.

### Step 1: Clone the Repo and Create a Python Virtual Environment

```bash
git clone https://github.com/justinschembri/st-utils.git st-utils
cd st-utils
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
# alternatively, if using uv: uv sync
```

### Step 2: Mandatory Internal Credentials

To quickly set up your instance of `st-utils`, use the inbuilt tooling:

```bash
$ stu setup
```

Upon the first launch of the CLI, you will be guided through setting up mandatory internal credentials. The system uses default usernames (`sta-admin`) which you can accept or override:

- **FROST**: Credentials for the FROST server (needed for data access and writing)
  - Default username: `sta-admin`
- **PostgreSQL**: Credentials for the backend PostgreSQL database
  - Default username: `sta-admin`
- **MQTT**: Internal Mosquitto users (at least one user is required)
  - Default username: `sta-admin` (for the first user)
- **Tomcat**: Web application authentication (optional)
  - Leave empty to allow public access (no authentication required)
  - Default username: `sta-admin` (if creating users)

All credentials are stored in the `deploy/secrets/credentials` directory.

### Step 3: Configure Applications

After setting up internal credentials, you'll see the main menu. To configure IoT applications:

**Option [1] Add application to config**: This will:
1. Guide you through adding a new application (HTTP or MQTT)
2. Configure connection settings and authentication type
3. **Automatically** prompt you to set up credentials/tokens for the application

IoT applications you have access to must be configured. Having 'access' to an IoT application means you have the required credentials or tokens to pull data from the IoT application. This present version of st-utils supports two application platforms: *Netatmo* and the popular *TheThingsStack*.

**Option [2] Manage existing credentials and tokens**: Use this to modify or update any credentials (internal or application-level) after initial setup.

**Option [3] Show configured applications**: View the status of all configured applications and their credential setup status.

### Step 4: Configure Sensor Configurations

Each physical sensor in your network requires a configuration file that describes the sensor, its location, the thing it monitors, and the datastreams it produces. These files must be placed in the `deploy/sensor_configs/` directory.

**Quick Start (Recommended):**

For supported sensor models, use the template-based generator:

```bash
stu generate-config <sensor-model>
```

Where `<sensor-model>` is one of:
- `milesight.am103l`
- `milesight.am308l`
- `netatmo.nws03`

The CLI will prompt you for:
- Sensor ID/name (typically the device MAC address)
- Thing name and description
- Location name, description, and coordinates (longitude, latitude)

All standard datastreams and observedProperties are automatically populated from the template. See [Sensor Configuration Templates](docs/sensor-config-templates.md) for detailed information.

**Manual Configuration:**

If you need to create a configuration manually, template files are available at:
- `deploy/sensor_configs/template_milesight.am103l.yaml`
- `deploy/sensor_configs/template_milesight.am308l.yaml`
- `deploy/sensor_configs/template_netatmo.nws03.yaml`
- `deploy/sensor_configs/template.yaml` (generic template)

See [Sensor Configuration Templates](docs/sensor-config-templates.md) for detailed documentation on the configuration file structure and requirements.

**Validation:**

You can validate your sensor configuration files using:

```bash
stu validate <path-to-config-file.yaml>
```

Or validate all configuration files in the current directory:

```bash
stu validate
```

### Step 5

You can launch the application by running the production script
`deploy/start-production.sh`. You can visit the application
`http://localhost:8080`.

# Supported Applications

st-utils supports integration with the following IoT application platforms:

- **Netatmo**: HTTP-based connection to Netatmo weather station APIs
  - Connection class: `NetatmoConnection`
  - Authentication: Token-based (OAuth2)
  - Protocol: HTTP/S (REST API)

- **TheThingsStack (TTS)**: MQTT-based connection to The Things Network
  - Connection class: `TTSConnection`
  - Authentication: API key-based
  - Protocol: MQTT

# Supported Sensor Models

The following sensor models are currently supported:

- **Milesight AM103L** (`milesight.am103l`): Indoor Air Quality Sensor
  - Measurements: Battery level, CO₂, Humidity, Temperature
  - Protocol: LoRaWAN (via TheThingsStack)
  - [Product Information](https://www.milesight.com/iot/am103l/)

- **Milesight AM308L** (`milesight.am308l`): Indoor Air Quality Sensor (7-in-1)
  - Measurements: Battery level, CO₂, Humidity, Temperature, Light level, Motion (PIR), Particulate Matter (PM2.5, PM10), Pressure, TVOC
  - Protocol: LoRaWAN (via TheThingsStack)
  - [Product Information](https://www.milesight.com/iot/am308l/)

- **Netatmo NWS03** (`netatmo.nws03`): Home Weather Station
  - Measurements: Temperature, CO₂, Humidity, Noise, Pressure
  - Protocol: Wi-Fi (via Netatmo API)
  - [Product Information](https://www.netatmo.com/en-eu/smart-weather-station)



