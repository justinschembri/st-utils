import sys
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from .paths import (
        ROOT_DIR,
        LOGS_DIR,
        )

ST_UTILS_DEBUG = bool(os.getenv("ST_UTILS_DEBUG"))
# LOGGER DEFINITIONS ###########################################################
def setup_loggers() -> None:
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
        filename=ROOT_DIR / "logs" / "debug.log", mode="w"
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
        main_logger.warning(f"Debug mode active, check {ROOT_DIR / 'logs' / 'debug.log'}")

    return None
