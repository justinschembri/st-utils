# standard
import logging
from pathlib import Path
from typing import List
import os
import base64
import dotenv

# internal
from lnetatmo import ClientAuth

# directory setup
ROOT_DIRECTORY = Path(__file__).parent.parent.parent
CONFIG_PATHS = ROOT_DIRECTORY / "sensor_configs"
ENV_FILE = ROOT_DIRECTORY / ".env"

# environment set up
# use of `or` to set defaults for env variables when not set in a docker-compose or .env
if not os.getenv("CONTAINER_ENVIRONMENT"):
    dotenv.load_dotenv(ENV_FILE)  # docker-compose makes .env redundant

FROST_USER = os.getenv("FROST_USER") or "sta-manager"
FROST_PASSWORD = os.getenv("FROST_PASSWORD")
FROST_CREDENTIALS = base64.b64encode(f"{FROST_USER}:{FROST_PASSWORD}".encode()).decode(
    "utf-8"
)
FROST_ENDPOINT = (
    os.getenv("FROST_ENDPOINT") or "http://localhost:8080/FROST-Server.HTTP-2.5.3/v1.1"
)
# set in a docker-compose file, constant is equivalent to None in non-container:
CONTAINER_ENVIRONMENT = os.getenv("CONTAINER_ENVIRONMENT")


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
    return sensor_configs


SENSOR_CONFIG_FILES = generate_sensor_config_files()


def netatmo_auth_check(authentication: ClientAuth) -> bool:
    """
    Check successful authentication with Netatmo.

    Refer to README for authentication set up.

    Return True if successful.
    """
    try:
        # lnetatmo will throw a TypeError
        authentication.renew_token()
    except TypeError as e:
        logging.critical(f"{e}")
        return False
    else:
        return True


if __name__ == "__main__":
    print(f"{ROOT_DIRECTORY} Exists: {ROOT_DIRECTORY.exists()}")
    print(f"{CONFIG_PATHS} Exists: {CONFIG_PATHS.exists()}")
    print(f"{ENV_FILE} Exists: {ENV_FILE.exists()}")
