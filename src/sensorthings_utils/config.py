# standard
import logging
from pathlib import Path
from typing import List

# external
# internal
from lnetatmo import ClientAuth

# directory setup

ROOT_DIRECTORY = Path(__file__).parent.parent.parent
CONFIG_PATHS = ROOT_DIRECTORY / "sensor_configs"
ENV_FILE = ROOT_DIRECTORY / ".env"


def generate_sensor_config_files() -> List[Path]:
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
