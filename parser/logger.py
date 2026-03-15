"""
RFQ Parser Logger
==================
Sets up weekly rotating log files for the RFQ parser.
Log files are stored in the logs/ folder at the project root.
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logger() -> logging.Logger:
    """
    Sets up and returns the RFQ parser logger.
    - Rotates every Monday (weekly)
    - Keeps 8 weeks of history
    - Writes to logs/rfq_parser.log
    - Also prints to console
    """

    # Create logs/ folder if it doesn't exist
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_path = logs_dir / "rfq_parser.log"

    # Create logger
    logger = logging.getLogger("rfq_parser")
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    # File handler — weekly rotation, keeps 8 weeks
    file_handler = TimedRotatingFileHandler(
        filename=str(log_path),
        when="W0",        # Rotate every Monday
        interval=1,
        backupCount=8,    # Keep 8 weeks of history
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler — prints to terminal
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Format — pipe separated
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Single logger instance shared across the project
logger = setup_logger()