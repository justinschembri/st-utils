"""Path definitions for st-utils project."""

from pathlib import Path
import os
import dotenv

__all__ = [
    "ROOT_DIR",
    "ENV_FILE",
    "DEPLOY_DIR",
    "LOGS_DIR",
    "SENSOR_CONFIG_PATH",
    "CREDENTIALS_DIR",
    "TOKENS_DIR",
    "TEST_DATA_DIR",
    "APPLICATION_CONFIG_FILE",
    "START_SCRIPT",
    "STOP_SCRIPT"
]

ROOT_DIR = Path(__file__).parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"
dotenv.load_dotenv(ENV_FILE)
# Derived paths
DEPLOY_DIR = ROOT_DIR / "deploy"
START_SCRIPT = DEPLOY_DIR / "start-production.sh"
STOP_SCRIPT = DEPLOY_DIR / "stop-production.sh"
LOGS_DIR = ROOT_DIR / "logs"
SENSOR_CONFIG_PATH = Path(os.getenv("SENSOR_CONFIG_PATH", DEPLOY_DIR / "sensor_configs"))
CREDENTIALS_DIR = DEPLOY_DIR / "secrets" / "credentials"
TOKENS_DIR = DEPLOY_DIR / "secrets" / "tokens"
TEST_DATA_DIR = ROOT_DIR / "tests" / "sensorthings_utils" / "data"

# APPLICATION_CONFIG_FILE - find the first application-configs yaml/yml file
# Default to application-configs.yml if not found (allows creation)
APPLICATION_CONFIG_FILE = next(DEPLOY_DIR.glob("application-configs.y*ml"), DEPLOY_DIR / "application-configs.yml")

if __name__ == "__main__":
    print(
            f"{ROOT_DIR=} Exists: {ROOT_DIR.exists()}\n"
            f"{LOGS_DIR=} Exists: {LOGS_DIR.exists()}\n"
            f"{SENSOR_CONFIG_PATH=} Exists: {SENSOR_CONFIG_PATH.exists()}\n"
            f"{ENV_FILE=} Exists: {ENV_FILE.exists()}"
            )

