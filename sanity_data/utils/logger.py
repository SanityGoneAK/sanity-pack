import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

class CustomFormatter(logging.Formatter):
    """Custom formatter for different log levels"""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    FORMATS = {
        logging.DEBUG: grey + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.INFO: grey + "%(asctime)s - %(levelname)s - %(message)s" + reset,
        logging.WARNING: yellow + "%(asctime)s - %(levelname)s - %(message)s" + reset,
        logging.ERROR: red + "%(asctime)s - %(levelname)s - %(message)s" + reset,
        logging.CRITICAL: bold_red + "%(asctime)s - %(levelname)s - %(message)s" + reset
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logger(
    name: str = "sanity_data",
    level: int = logging.ERROR,
    log_to_file: bool = True,
    log_dir: Optional[Path] = None
) -> logging.Logger:
    """
    Set up a logger with console and file handlers.
    
    Args:
        name: Logger name
        level: Logging level (default: ERROR)
        log_to_file: Whether to log to file (default: True)
        log_dir: Directory to store log files (default: .logs in current directory)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter())
    logger.addHandler(console_handler)
    
    if log_to_file:
        # Create logs directory if it doesn't exist
        if log_dir is None:
            log_dir = Path(".logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create file handler with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{timestamp}.log"
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)
    
    return logger

# Create default logger instance
logger = setup_logger() 