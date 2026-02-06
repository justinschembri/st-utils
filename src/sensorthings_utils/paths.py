"""Path definitions for st-utils project."""

from pathlib import Path
import os
import dotenv

__all__ = [
    "ROOT_DIR",
    "ENV_FILE",
    "DEPLOY_DIR",
    "LOGS_DIR",
    "VARIABLE_SENSOR_CONFIG_PATH",
    "CREDENTIALS_DIR",
    "TOKENS_DIR",
    "TEST_DATA_DIR",
    "VARIABLE_APPLICATION_CONFIG_FILE",
    "START_SCRIPT",
    "STOP_SCRIPT"
]

ROOT_DIR = Path(__file__).parent.parent.parent
# Derived paths
DEPLOY_DIR = ROOT_DIR / "deploy"
ENV_FILE = DEPLOY_DIR / ".env"
START_SCRIPT = DEPLOY_DIR / "start-production.sh"
STOP_SCRIPT = DEPLOY_DIR / "stop-production.sh"
LOGS_DIR = ROOT_DIR / "logs"
CREDENTIALS_DIR = DEPLOY_DIR / "secrets" / "credentials"
TOKENS_DIR = DEPLOY_DIR / "secrets" / "tokens"
TEST_DATA_DIR = ROOT_DIR / "tests" / "sensorthings_utils" / "data"

# it is suggested that the sensor and application configuration files live 
# outside the st-utils codebase and are tracked independently. For this reason,
# we need a fixed RUNTIME deploy path and a VARIABLE.
dotenv.load_dotenv(ENV_FILE)
RUNTIME_SENSOR_CONFIG_PATH = DEPLOY_DIR / "sensor_configs"
VARIABLE_SENSOR_CONFIG_PATH = Path(
        os.getenv(
            "SENSOR_CONFIG_PATH", RUNTIME_SENSOR_CONFIG_PATH)
        )
RUNTIME_APPLICATION_CONFIG_FILE = next(
            DEPLOY_DIR.glob("application-configs.y*ml"),
            DEPLOY_DIR / "application-configs.yml"
            )
VARIABLE_APPLICATION_CONFIG_FILE = Path(
        os.getenv(
            "APPLICATION_CONFIG_FILE", RUNTIME_APPLICATION_CONFIG_FILE)
    )

if __name__ == "__main__":
    print(
            f"{ROOT_DIR=} Exists: {ROOT_DIR.exists()}\n"
            f"{LOGS_DIR=} Exists: {LOGS_DIR.exists()}\n"
            f"{VARIABLE_SENSOR_CONFIG_PATH=} Exists: {VARIABLE_SENSOR_CONFIG_PATH.exists()}\n"
            f"{ENV_FILE=} Exists: {ENV_FILE.exists()}"
            )

