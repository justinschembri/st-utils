# standard
import logging
from pathlib import Path

# external
# internal
from lnetatmo import ClientAuth

# directory setup

ROOT_DIRECTORY = Path(__file__).parent.parent.parent
ENV_FILE = ROOT_DIRECTORY / ".env"


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
    print(ROOT_DIRECTORY)
    print(f"{ENV_FILE} Status: {ENV_FILE.exists()}")
