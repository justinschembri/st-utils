"""Global st-utils configuration, including credential management."""

# standard
import json
from pathlib import Path
from typing import List
import os
import base64
import dotenv
from .paths import (
        CONFIG_PATHS,
        CREDENTIALS_DIR,
        ENV_FILE,
        )
# ENVIRONMENT  #################################################################
CONTAINER_ENVIRONMENT = bool(os.getenv("CONTAINER_ENVIRONMENT"))
if not os.getenv("CONTAINER_ENVIRONMENT"):
    dotenv.load_dotenv(ENV_FILE)  # docker-compose makes .env redundant


def get_frost_credentials() -> tuple[str, str]:
    """Read FROST password from Docker secret or environment variable."""
    if CONTAINER_ENVIRONMENT:
        secret_file = Path("/run/secrets/frost_credentials") 
    else:
        secret_file = CREDENTIALS_DIR / "frost_credentials.json"
    try:
        with open(secret_file, "r") as f:
            credentials = json.load(f)
    except Exception:
        print("Error with FROST_CREDENTIALS, start stu setup.")
        from .cli.credentials import setup_frost_credentials
        setup_frost_credentials()
        with open(secret_file, "r") as f:
            credentials = json.load(f)

    return (credentials["frost_username"], credentials["frost_password"])


# Use it:
FROST_USER, FROST_PASSWORD = get_frost_credentials()
FROST_CREDENTIALS = base64.b64encode(f"{FROST_USER}:{FROST_PASSWORD}".encode()).decode(
    "utf-8"
)
FROST_ENDPOINT_DEFAULT = "http://localhost:8080/FROST-Server/v1.1"


def generate_sensor_config_files() -> List[Path]:
    """
    Return path to yaml configs found in `CONFIG_PATHS`.

    :return: List of all the (non template) yaml or yml files user places in
        `CONFIG_PATHS`
    :rtype: List[Path]
    """
    sensor_configs: List[Path] = []
    for f in CONFIG_PATHS.rglob("*.*ml"):
        if "template" not in f.stem:
            sensor_configs.append(f)

    if not sensor_configs:
        raise AttributeError(f"No sensor configs found in {CONFIG_PATHS}.")

    return sensor_configs



