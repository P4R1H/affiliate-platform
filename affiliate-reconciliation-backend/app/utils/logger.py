"""
Centralized logging configuration.
Provides structured logging for audit trails, performance monitoring, and debugging.
"""
import logging
import logging.config
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Converts log records to JSON format for easy parsing and analysis.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        extra_data = getattr(record, 'extra_data', None)
        if extra_data:
            log_entry.update(extra_data)
        
        # Add process/thread info for debugging
        log_entry.update({
            "process_id": record.process,
            "thread_id": record.thread,
        })
        
        return json.dumps(log_entry, ensure_ascii=False)

class StructuredLogger:
    """
    Wrapper around standard logger to provide structured logging methods.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log_with_extra(self, level: int, message: str, **kwargs):
        """Log with extra structured data."""
        extra_data = {k: v for k, v in kwargs.items() if v is not None}
        self.logger.log(level, message, extra={'extra_data': extra_data})
    
    def info(self, message: str, **kwargs):
        """Log info level with structured data."""
        self._log_with_extra(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning level with structured data."""
        self._log_with_extra(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error level with structured data."""
        self._log_with_extra(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug level with structured data."""
        self._log_with_extra(logging.DEBUG, message, **kwargs)

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True
) -> None:
    """
    Setup application logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        enable_console: Whether to log to console
    """
    
    # Ensure logs directory exists
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Base configuration
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
            },
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {},
        "loggers": {
            "app": {
                "level": log_level,
                "handlers": [],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": [],
                "propagate": False
            },
            "sqlalchemy.engine": {
                "level": "WARNING",  # Reduce SQL query noise
                "handlers": [],
                "propagate": False
            }
        },
        "root": {
            "level": log_level,
            "handlers": []
        }
    }
    
    # Console handler
    if enable_console:
        config["handlers"]["console"] = {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "standard",
            "level": log_level
        }
        config["loggers"]["app"]["handlers"].append("console")
        config["loggers"]["uvicorn"]["handlers"].append("console")
        config["loggers"]["sqlalchemy.engine"]["handlers"].append("console")
        config["root"]["handlers"].append("console")
    
    # File handler with JSON formatting
    if log_file:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "formatter": "json",
            "level": log_level
        }
        config["loggers"]["app"]["handlers"].append("file")
        config["loggers"]["uvicorn"]["handlers"].append("file")
        config["loggers"]["sqlalchemy.engine"]["handlers"].append("file")
        config["root"]["handlers"].append("file")
    
    # Apply configuration
    logging.config.dictConfig(config)

def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(f"app.{name}")

# Audit logging for business events
def log_business_event(
    event_type: str,
    details: Dict[str, Any],
    user_id: Optional[int] = None,
    request_id: Optional[str] = None
) -> None:
    """
    Log business events for audit trails.
    
    Args:
        event_type: Type of business event (e.g., 'affiliate_submission', 'reconciliation_completed')
        details: Event-specific details
        user_id: User/affiliate ID if applicable
        request_id: Request ID for tracing
    """
    audit_logger = get_logger("audit")
    audit_logger.info(
        f"Business event: {event_type}",
        event_type=event_type,
        user_id=user_id,
        request_id=request_id,
        **details
    )

# Performance logging
def log_performance(
    operation: str,
    duration_ms: float,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log performance metrics.
    
    Args:
        operation: Operation name
        duration_ms: Duration in milliseconds
        additional_data: Additional context data
    """
    perf_logger = get_logger("performance")
    data = {"duration_ms": duration_ms}
    if additional_data:
        data.update(additional_data)
    
    perf_logger.info(
        f"Performance: {operation}",
        operation=operation,
        **data
    )

