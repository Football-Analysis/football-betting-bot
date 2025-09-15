import logging.config
import os
from .config import Config as conf
from json import load

APP_LOGGER_NAME = "post_and_in"

def setup_logging():
    config_path = os.path.join(os.path.dirname(__file__), "logging_config.json")
    with open(config_path, "r") as f:
        config = load(f)

    # override app logger level dynamically (e.g. from env var)
    config["loggers"][APP_LOGGER_NAME]["level"] = conf.LOGGING_LEVEL.upper()

    logging.config.dictConfig(config)

def get_logger(name: str | None = None):
    if name:
        return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")
    return logging.getLogger(APP_LOGGER_NAME)
