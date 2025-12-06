"""
Structured Logging Configuration
=================================
JSON-formatted logging for token refresh and Railway operations.

All logs include:
- Timestamp (ISO 8601)
- Log level
- Logger name
- Message
- Extra context (when provided)

Security: Token values are automatically masked in logs.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger


class WithingsTokenFilter(logging.Filter):
    """
    Filter that masks sensitive token values in log messages.
    
    Prevents accidental exposure of access/refresh tokens in logs.
    """
    
    SENSITIVE_PATTERNS = [
        "access_token",
        "refresh_token",
        "client_secret",
        "authorization",
        "bearer"
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Mask sensitive data in log record."""
        # Mask in message
        if hasattr(record, 'msg') and record.msg:
            record.msg = self._mask_sensitive_data(str(record.msg))
        
        # Mask in args
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._mask_sensitive_data(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._mask_sensitive_data(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        
        return True
    
    def _mask_sensitive_data(self, text: str) -> str:
        """Mask any sensitive data found in text."""
        import re
        
        # Mask potential token patterns (long alphanumeric strings)
        # Pattern matches tokens that are typically 40+ chars
        text = re.sub(
            r'([a-zA-Z0-9]{40,})',
            lambda m: f"token_*****{m.group(1)[-3:]}",
            text
        )
        
        return text


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter with additional context fields.
    """
    
    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ):
        """Add custom fields to each log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO 8601 format
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Add standard fields
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        
        # Add service identifier
        log_record['service'] = 'withings-mcp'
        
        # Add environment
        log_record['environment'] = os.getenv('ENVIRONMENT', 'production')
        
        # Remove redundant fields
        log_record.pop('levelname', None)
        log_record.pop('name', None)


def setup_logging(
    level: Optional[str] = None,
    json_format: bool = True
) -> None:
    """
    Configure application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to LOG_LEVEL env var or INFO.
        json_format: Whether to use JSON format. Defaults to True in production.
    """
    log_level = level or os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Determine if we should use JSON format
    environment = os.getenv('ENVIRONMENT', 'production')
    use_json = json_format and environment != 'development'
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level, logging.INFO))
    
    if use_json:
        # JSON format for production
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(logger)s %(message)s'
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler.setFormatter(formatter)
    
    # Add token masking filter
    handler.addFilter(WithingsTokenFilter())
    
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('uvicorn').setLevel(logging.INFO)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    
    logging.info(
        f"Logging configured: level={log_level}, format={'json' if use_json else 'text'}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the token masking filter.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Ensure filter is applied
    if not any(isinstance(f, WithingsTokenFilter) for f in logger.filters):
        logger.addFilter(WithingsTokenFilter())
    
    return logger


# Convenience function for structured logging with context
def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    **context
) -> None:
    """
    Log a message with additional context fields.
    
    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error)
        message: Log message
        **context: Additional context fields to include
    
    Example:
        log_with_context(
            logger,
            'info',
            'Token refresh completed',
            user_id='12345',
            expires_in_hours=336
        )
    """
    log_method = getattr(logger, level.lower(), logger.info)
    
    # Format context into message for JSON logger to capture
    if context:
        context_str = ' '.join(f'{k}={v}' for k, v in context.items())
        full_message = f"{message} | {context_str}"
    else:
        full_message = message
    
    log_method(full_message, extra=context)
