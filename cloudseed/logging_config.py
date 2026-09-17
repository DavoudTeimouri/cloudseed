"""
Logging configuration for CloudSeed CLI.
"""

import logging
import json
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
            "name": record.name,
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


_log_level = logging.INFO
_json_format = False


def set_log_level(level):
    global _log_level
    _log_level = level
    _apply_logging_config()


def set_json_logs(enable):
    global _json_format
    _json_format = enable
    _apply_logging_config()


def _apply_logging_config():
    logger = logging.getLogger()
    logger.setLevel(_log_level)

    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    if _json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    handler.setFormatter(formatter)
    logger.addHandler(handler)