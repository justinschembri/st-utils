"""Path definitions for st-utils project."""

from pathlib import Path

__all__ = [
    "ROOT_DIR",
    "ENV_FILE",
    "DEPLOY_DIR",
    "LOGS_DIR",
    "CONFIG_PATHS",
    "CREDENTIALS_DIR",
    "TOKENS_DIR",
    "TEST_DATA_DIR",
    "APPLICATION_CONFIG_FILE",
]

ROOT_DIR = Path(__file__).parent.parent.parent
# Derived paths
ENV_FILE = ROOT_DIR / ".env"
DEPLOY_DIR = ROOT_DIR / "deploy"
LOGS_DIR = ROOT_DIR / "logs"
CONFIG_PATHS = DEPLOY_DIR / "sensor_configs"
CREDENTIALS_DIR = DEPLOY_DIR / "secrets" / "credentials"
TOKENS_DIR = DEPLOY_DIR / "secrets" / "tokens"
TEST_DATA_DIR = ROOT_DIR / "tests" / "sensorthings_utils" / "data"

# APPLICATION_CONFIG_FILE - find the first application-configs yaml/yml file
APPLICATION_CONFIG_FILE = next(DEPLOY_DIR.glob("application-configs.y*ml"), Path())
if not APPLICATION_CONFIG_FILE.exists():
    raise FileNotFoundError(f"No application_configs.y*ml found in {DEPLOY_DIR}")

if __name__ == "__main__":
    print(
            f"{ROOT_DIR=} Exists: {ROOT_DIR.exists()}\n"
            f"{LOGS_DIR=} Exists: {LOGS_DIR.exists()}\n"
            f"{CONFIG_PATHS=} Exists: {CONFIG_PATHS.exists()}\n"
            f"{ENV_FILE=} Exists: {ENV_FILE.exists()}"
            )

