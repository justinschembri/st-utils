"""Global st-utils configuration, including credential management."""

# standard
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import List
import os
import base64
import dotenv

# ENVIRONMENT VARIABLES ########################################################
CONTAINER_ENVIRONMENT = bool(os.getenv("CONTAINER_ENVIRONMENT"))
DEBUG = bool(os.getenv("DEBUG"))

# PATH DEFINITIONS #############################################################
ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_PATHS = ROOT_DIR / "sensor_configs"
ENV_FILE = ROOT_DIR / ".env"
CREDENTIALS_DIR = ROOT_DIR / "deploy" / "secrets" / "credentials"
TOKENS_DIR = ROOT_DIR / "deploy" / "secrets" / "tokens"
TEST_DATA_DIR = ROOT_DIR / "tests" / "sensorthings_utils" / "data"

# LOGGER DEFINITIONS ########################################################### 
LOGGERS = [
        "root",
        "debug",
        "network_monitor",
        "main",
        "warnings"
        ]
# Root Logger ------------------------------------------------------------------
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Debug Logger -----------------------------------------------------------------
debug_logger = logging.getLogger("debug")
debug_logger.setLevel(logging.DEBUG)
# Network Monitor Logger -------------------------------------------------------
network_monitor_logger = logging.getLogger("network_monitor")
network_monitor_logger.setLevel(logging.INFO)
# Main Logger ------------------------------------------------------------------
main_logger = logging.getLogger("main")
main_logger.setLevel(logging.INFO)
# Warning Logger ---------------------------------------------------------------
warning_logger = logging.getLogger("warnings")
warning_logger.setLevel(logging.WARNING)
# File Handler (general)--------------------------------------------------------
general_logfile_name = "general.log"
logfile = Path(ROOT_DIR / ("logs/" + general_logfile_name))
logfile.parent.mkdir(exist_ok=True)
file_handler = TimedRotatingFileHandler(
    filename=logfile, when="midnight", interval=1, backupCount=30, encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(asctime)s [%(name)s:%(lineno)d]: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(file_formatter)
# File Handler (debug)----------------------------------------------------------
debug_logfile_name = "debug.log"
logfile = Path(ROOT_DIR / ("logs/" + debug_logfile_name))
logfile.parent.mkdir(exist_ok=True)
debug_handler = logging.FileHandler(filename=logfile)
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter(
    "%(asctime)s [%(module)s:%(lineno)d]: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
debug_handler.setFormatter(debug_formatter)
# Console Handlers -------------------------------------------------------------
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
console_formatter = logging.Formatter(
    "%(asctime)s [%(module)s:%(lineno)d]: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_handler.setFormatter(console_formatter)
# Attach Handlers --------------------------------------------------------------
root_logger.addHandler(file_handler)
debug_logger.addHandler(debug_handler)
network_monitor_logger.addHandler(console_handler)
main_logger.addHandler(console_handler)
if DEBUG:
    debug_logger.addHandler(console_handler)

# environment set up
# use of `or` to set defaults for env variables when not set in a docker-compose or .env
if not os.getenv("CONTAINER_ENVIRONMENT"):
    dotenv.load_dotenv(ENV_FILE)  # docker-compose makes .env redundant

def get_frost_password() -> str | None:
    """Read FROST password from Docker secret or environment variable."""
    if not CONTAINER_ENVIRONMENT:
        return os.getenv("FROST_PASSWORD")
    secret_file = Path("/run/secrets/FROST_PASSWORD")

    return secret_file.read_text().strip()

# Use it:
FROST_USER = os.getenv("FROST_USER") or "sta-manager"
FROST_PASSWORD = get_frost_password()

debug_logger.debug(f"{FROST_USER}")
debug_logger.debug(f"{FROST_PASSWORD}")

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


SENSOR_CONFIG_FILES = generate_sensor_config_files()

if __name__ == "__main__":
    print(f"{ROOT_DIR=} Exists: {ROOT_DIR.exists()}")
    print(f"{CONFIG_PATHS=} Exists: {CONFIG_PATHS.exists()}")
    print(f"{ENV_FILE=} Exists: {ENV_FILE.exists()}")

