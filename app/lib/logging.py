"""Logging configuration for the application."""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(
    name: str = "app",
    level: str = "INFO",
    log_dir: str = "logs",
    log_file: str = "app.log",
    max_bytes: int = 10485760,  # 10 MB
    backup_count: int = 5,
    enable_file: bool = False,
) -> logging.Logger:
    """Set up logging with console and optional file handlers.
    
    Args:
        name: Logger name
        level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory where log files are stored
        log_file: Log file name
        max_bytes: Maximum file size before rotation (in bytes, default: 10 MB)
        backup_count: Number of backup files to keep
        enable_file: Whether to write logs to file (default: False for console-only during development)
        
    Returns:
        Configured logger instance
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create logs directory if it doesn't exist
    log_path_dir = Path(log_dir)
    log_path_dir.mkdir(parents=True, exist_ok=True)
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation (optional, enabled in production)
    if enable_file:
        log_file_path = log_path_dir / log_file
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "app") -> logging.Logger:
    """Get or create a logger instance.
    
    Args:
        name: Logger name (typically __name__ in modules)
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Lazy load config only when needed
        from app.configs import get_environment_configuration
        config = get_environment_configuration()
        setup_logging(
            name=name,
            level=config.LOG_LEVEL,
            log_dir=config.LOG_DIR,
            log_file=config.LOG_FILE,
            max_bytes=config.LOG_MAX_BYTES,
            backup_count=config.LOG_BACKUP_COUNT,
            enable_file=config.ENABLE_FILE_LOGGING,
        )
    return logger


# Initialize root logger on module import
def _init_root_logger():
    """Initialize root logger with environment configuration."""
    try:
        from app.configs import get_environment_configuration
        config = get_environment_configuration()
        setup_logging(
            name="app",
            level=config.LOG_LEVEL,
            log_dir=config.LOG_DIR,
            log_file=config.LOG_FILE,
            max_bytes=config.LOG_MAX_BYTES,
            backup_count=config.LOG_BACKUP_COUNT,
        )
    except Exception:
        # Fallback to default logging if config not available
        setup_logging(name="app")


# Initialize on import
root_logger = _init_root_logger()
