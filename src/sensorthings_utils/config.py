"""Global st-utils configuration, including credential management."""

# standard
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import List
import os
import sys
import base64
import dotenv

# ENVIRONMENT  #################################################################
CONTAINER_ENVIRONMENT = bool(os.getenv("CONTAINER_ENVIRONMENT"))
ST_UTILS_DEBUG = bool(os.getenv("ST_UTILS_DEBUG"))

# PATH DEFINITIONS #############################################################
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"
DEPLOY_DIR = ROOT_DIR / "deploy"
APPLICATION_CONFIG_FILE = next(DEPLOY_DIR.glob("application-configs.y*ml"), Path())
if not APPLICATION_CONFIG_FILE:
    raise FileNotFoundError(f"No application_configs.y*ml found in {DEPLOY_DIR}")
CONFIG_PATHS = DEPLOY_DIR / "sensor_configs"
CREDENTIALS_DIR = DEPLOY_DIR / "secrets" / "credentials"
TOKENS_DIR = DEPLOY_DIR / "secrets" / "tokens"
TEST_DATA_DIR = ROOT_DIR / "tests" / "sensorthings_utils" / "data"

# LOGGER DEFINITIONS ###########################################################
main_logger = logging.getLogger("main")
main_logger.setLevel(logging.INFO)
main_logger.propagate = False
# --
debug_logger = logging.getLogger("debug")
debug_logger.setLevel(logging.DEBUG)
debug_logger.propagate = False
# --
events_logger = logging.getLogger("events")
events_logger.setLevel(logging.INFO)
events_logger.propagate = False
# FORMATTERS ---
general_formatter = logging.Formatter(
    "%(asctime)s [%(name)s:%(module)s:%(lineno)d]: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S %z",
)
# HANDLERS ---
# console handlers -
general_console = logging.StreamHandler()
general_console.setLevel(logging.WARNING)
general_console.setFormatter(general_formatter)
# --
event_console = logging.StreamHandler(stream=sys.stdout)
event_console.setLevel(logging.INFO)
event_console.setFormatter(general_formatter)
# files handlers-
general_logfile = TimedRotatingFileHandler(
    filename=ROOT_DIR / "logs" / "general.log",
    when="midnight",
    backupCount=7,
    utc=True,
)
general_logfile.setLevel(logging.INFO)
general_logfile.setFormatter(general_formatter)
# --
debug_logfile_handler = logging.FileHandler(
    filename=ROOT_DIR / "logs" / "debug.log", mode = "w"
)
debug_logfile_handler.setLevel(logging.DEBUG)
debug_logfile_handler.setFormatter(general_formatter)
# ATTACH
# main logger:
if not main_logger.handlers:
    main_logger.addHandler(general_console)
    main_logger.addHandler(general_logfile)
# --
if not events_logger.handlers:
    events_logger.addHandler(event_console)
    events_logger.addHandler(general_logfile)
# --
if ST_UTILS_DEBUG:
    debug_logger.addHandler(debug_logfile_handler)
    main_logger.warning(
            f"Debug mode active, check {ROOT_DIR / 'logs' / 'debug.log'}"
            )

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
