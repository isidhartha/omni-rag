"""Structured logging setup for OmniRAG."""
from __future__ import annotations

import logging
import sys
from typing import Optional


def configure_logging(level: str = "INFO", service_name: str = "omnirag") -> logging.Logger:
    """Configure structured logging with consistent format."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    if not root_logger.handlers:
        root_logger.addHandler(handler)

    return get_logger(service_name)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger instance."""
    return logging.getLogger(name)
