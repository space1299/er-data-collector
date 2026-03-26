"""
Usage:
    from common.logger import setup_logger
    logger = setup_logger("collector", "./logs/collector.log")
    logger.info("hello")

Notes:
    - logs can go to console and file at the same time
    - file logging uses size-based rotation
    - when `log_file` is omitted, `ER_DATA_LOG_FILE` is used
"""

import logging
import os
import sys
from logging import Logger
from logging.handlers import RotatingFileHandler
from typing import Optional, Union

__all__ = ["setup_logger"]

_LEVEL_MAP = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}

_DEFAULT_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _as_level(level: Union[int, str]) -> int:
    if isinstance(level, int):
        return level
    return _LEVEL_MAP.get(str(level).upper(), logging.INFO)


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path or "")
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def _ensure_utf8_stream(stream):
    try:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return stream


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: Union[int, str] = "INFO",
    *,
    console: bool = True,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    fmt: str = _DEFAULT_FMT,
    datefmt: str = _DEFAULT_DATEFMT,
    propagate: bool = False,
) -> Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        logger.setLevel(_as_level(level))
        logger.propagate = propagate
        for handler in logger.handlers:
            handler.setLevel(_as_level(level))
        return logger

    if log_file is None:
        log_file = os.getenv("ER_DATA_LOG_FILE")

    logger.setLevel(_as_level(level))
    logger.propagate = propagate

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    if console:
        stream = _ensure_utf8_stream(sys.stdout)
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setLevel(_as_level(level))
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if log_file:
        try:
            _ensure_dir(log_file)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
                delay=True,
            )
            file_handler.setLevel(_as_level(level))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass

    return logger
