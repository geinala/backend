"""Logging configuration with structured JSON format and wide events support.

This module implements logging best practices with:
- Structured JSON logging for powerful debugging and analytics
- Wide events: one context-rich event per request/job with all relevant context
- High cardinality support: includes request IDs, job IDs, user context
- Business context: job status, parameters, outcomes
- Environment characteristics: service version, region, environment
"""

import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Mapping


class StructuredJSONFormatter(logging.Formatter):
    """Format log records as structured JSON for better analytics and debugging.
    
    Each log entry becomes a single JSON object with:
    - timestamp: ISO format datetime
    - level: Log level (INFO, ERROR, etc.)
    - logger: Module name
    - message: If structured data, already in record.__dict__
    - All context from record.__dict__ (request_id, job_id, duration_ms, etc.)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        If the message is a dict (wide event), include all fields.
        Otherwise, create a simple JSON with message.
        """
        # Start with common fields
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        
        log_entry: dict[str, Any] = {
            "timestamp": dt.isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
        }
        
        # If message is dict (wide event), merge all fields
        if isinstance(record.msg, dict):
            log_entry.update(record.msg) # type: ignore
        else:
            # Fallback for simple message strings
            log_entry["message"] = record.getMessage()
            
            # Include any exception info
            if record.exc_info:
                exc_type = record.exc_info[0]
                exc_value = record.exc_info[1]
                
                if exc_type is not None:
                    log_entry["exception"] = {
                        "type": exc_type.__name__,
                        "message": str(exc_value),
                    }
        
        return json.dumps(log_entry, default=str)


class SimpleTextFormatter(logging.Formatter):
    """Format log records as simple readable text for development.
    
    Format: "[TIMESTAMP] [LEVEL] [LOGGER] - MESSAGE"
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as readable text."""
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        
        if isinstance(record.msg, Mapping):
            # For wide events, show key metrics
            important_fields: list[str] = []
            
            for key in ["status", "outcome", "error", "duration_ms", "job_id"]:
                if key in record.msg: # type: ignore
                    important_fields.append(f"{key}={record.msg[key]}") # type: ignore
                    
            message = " | ".join(important_fields) if important_fields else str(record.msg) # type: ignore
        else:
            message = record.getMessage()
        
        return f"[{timestamp}] [{record.levelname}] [{record.name}] - {message}"


def setup_logging(
    name: str = "app",
    level: str = "INFO",
    log_dir: str = "logs",
    log_file: str = "app.log",
    max_bytes: int = 10485760,  # 10 MB
    backup_count: int = 5,
    enable_file: bool = False,
    use_json: bool = False,
) -> logging.Logger:
    """Set up logging with structured format and wide events support.
    
    Logs are emitted with full context for powerful debugging and analytics.
    
    Args:
        name: Logger name
        level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory where log files are stored
        log_file: Log file name
        max_bytes: Maximum file size before rotation (in bytes, default: 10 MB)
        backup_count: Number of backup files to keep
        enable_file: Whether to write logs to file (default: False for console-only)
        use_json: Use JSON format (True in production, False for development)
        
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
    
    # Choose formatter based on production vs development
    if use_json:
        formatter = StructuredJSONFormatter()
    else:
        formatter = SimpleTextFormatter()
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
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
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "app") -> logging.Logger:
    """Get or create a logger instance.
    
    Uses environment configuration for consistent setup.
    
    Args:
        name: Logger name (typically __name__ in modules)
        
    Returns:
        Logger instance ready for use
        
    Example:
        ```python
        from app.lib.logging import get_logger
        
        logger = get_logger(__name__)
        
        # Log wide event with full context
        logger.info({
            "request_id": "req_123",
            "job_id": "job_456",
            "status": "completed",
            "duration_ms": 1250,
            "outcome": "success"
        })
        ```
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
            use_json=config.ENVIRONMENT == "production",
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
