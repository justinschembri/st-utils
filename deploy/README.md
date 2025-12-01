# Deployment Files

This directory contains a series of `docker-compose` files and initialization
scripts. The compose files are intended to be
[merged](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/).
Any merge operation **must** include the base compose file:
`docker-compose.base.yml`.  

In production, the compose stack usually merges the `base`, `auth`,
`persistent`, and `app` files.  The compose files are separated to allow
flexibility in test environments.

---

## TL;DR

- Always include `docker-compose.base.yml` in any merge.  
- Use `auth`, `persistent`, and `app` to extend the base for production.  
- Populate the `secrets` directory with required plain-text credentials.  
- Use `start-full.sh` to launch the complete production stack.

---

## Compose Files Overview

- `docker-compose.base.yml` → Base compose file with core services.  
- `docker-compose.auth.yml` → Adds authentication for `POST` requests to the
  FROST server.  
- `docker-compose.persistent.yml` → Adds a persistent Docker volume to the
  PostgreSQL database.  
- `docker-compose.app.yml` → Adds the Python application layer.  

---

## Credential Prerequisites

Most images require credentials, which should be placed in the `secrets`
directory as plain text files.

### Required for `base`

- `POSTGRES_PASSWORD.txt` → Plain-text password for the PostgreSQL database.  
- `MQTT_USERS.txt` → Plain-text single or multiline user/password pairs for MQTT
  users in `mosquitto`. Format:

```txt
<user_1>=<user_1_password>
<user_2>=<user_2_password>
...
```

### Required for `auth`

`FROST_USER_PASSWORD.txt` → Plain-text password used for authentication when
pushing data to the FROST server.

## Merging Multiple Compose Files

Non-base compose files add specific functionalities to the base stack.
For example, to add FROST authentication:

```
docker compose -f docker-compose.base.yml -f docker-compose.auth.yml up
```

To deploy the full production stack (base + auth + persistent + app):

```
docker compose \
  -f docker-compose.base.yml \
  -f docker-compose.auth.yml \
  -f docker-compose.persistent.yml \
  -f docker-compose.app.yml \
  up
```

The start-full.sh script launches this full production stack automatically.

## Compose File Functionalities

### `base`

Starts the core services: HTTP FROST server, MQTT server, and an ephemeral
PostgreSQL database.

### `auth`

Adds a basic authentication provider to the FROST server.  
Pushing data now requires a username and password in the HTTP headers.  

- **Default username:** `sta-manager`  
- **Password:** specified in [secrets](#credential-prerequisites)

### `persistent`

Makes the FROST database persistent using a Docker volume.

### `app`

Runs the Python application that communicates with registered sensors.

