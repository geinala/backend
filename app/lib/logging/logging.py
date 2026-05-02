
import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Mapping


class StructuredJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        
        log_entry: dict[str, Any] = {
            "timestamp": dt.isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
        }
        
        if isinstance(record.msg, dict):
            log_entry.update(record.msg) # type: ignore
        else:
            log_entry["message"] = record.getMessage()
            
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
    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        
        if isinstance(record.msg, Mapping):
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
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    logger.propagate = False
    
    if logger.handlers:
        return logger
    
    log_path_dir = Path(log_dir)
    log_path_dir.mkdir(parents=True, exist_ok=True)
    
    if use_json:
        formatter = StructuredJSONFormatter()
    else:
        formatter = SimpleTextFormatter()
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
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
    
    logger = logging.getLogger(name)
    if not logger.handlers:
        from app.configs.environment_configuration import get_environment_configuration
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


def _init_root_logger():
    try:
        from app.configs.environment_configuration import get_environment_configuration
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
        setup_logging(name="app")


root_logger = _init_root_logger()
