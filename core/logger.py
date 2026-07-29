"""
Logging system for AI Builder.
Provides structured logging to files and console.
Log output files are written to a 'logs/' directory created at runtime.
"""

import os
import logging
from pathlib import Path
from datetime import datetime


class Logger:
    """Centralized logger with file and console handlers."""

    _initialized = False

    def __init__(self, name="ai_builder", log_dir=None, level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if Logger._initialized:
            return
        Logger._initialized = True

        root_dir = Path(__file__).resolve().parent.parent
        log_dir = Path(log_dir) if log_dir else (root_dir / "logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"ai_builder_{datetime.now().strftime('%Y%m%d')}.log"

        # File handler
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(level)
        file_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_fmt = logging.Formatter("%(levelname)-8s | %(message)s")
        console_handler.setFormatter(console_fmt)

        # Add handlers to root logger so ALL named loggers inherit them
        root = logging.getLogger()
        root.setLevel(level)
        root.addHandler(file_handler)
        root.addHandler(console_handler)

    def debug(self, msg, extra=None):
        self.logger.debug(msg, extra=extra)

    def info(self, msg, extra=None):
        self.logger.info(msg, extra=extra)

    def warning(self, msg, extra=None):
        self.logger.warning(msg, extra=extra)

    def error(self, msg, extra=None):
        self.logger.error(msg, extra=extra)

    def critical(self, msg, extra=None):
        self.logger.critical(msg, extra=extra)

    def exception(self, msg, extra=None):
        self.logger.exception(msg, extra=extra)


def get_logger(name="ai_builder"):
    """Return a configured Logger instance."""
    return Logger(name=name)


# Module-level convenience logger
log = get_logger()