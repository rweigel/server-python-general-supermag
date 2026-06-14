import os
import logging
from pathlib import Path


LOG_FORMAT = '%(name)s: %(message)s'


def configure_logging(name, level=logging.DEBUG, format_string=LOG_FORMAT):
  logging.basicConfig(level=level, format=format_string)
  logger = logging.getLogger(name)
  logger.setLevel(level)
  return logger


def set_logging_level(level, logger_names=None):
  logging.getLogger().setLevel(level)
  if logger_names is None:
    return

  for logger_name in logger_names:
    logging.getLogger(logger_name).setLevel(level)


def _path_relative_to_cwd(path):
  return Path(os.path.relpath(Path(path).resolve(), Path.cwd()))
