"""
Endpoint logging utility with log accumulation.

Provides structured logging with automatic log collection for API responses.
Useful for endpoints that need to return detailed execution logs to the client.
"""
import logging
from typing import List
from datetime import datetime


class EndpointLogger:
    """
    Logger that accumulates messages for endpoint responses.
    
    Combines standard Python logging with message accumulation, allowing
    endpoints to return detailed execution logs to the client while also
    maintaining proper server-side logging.
    
    Attributes:
        endpoint_name: Name of the endpoint (used in logger name)
        logs: List of accumulated log messages
        logger: Standard Python logger instance
        start_time: Timestamp when logger was created
    
    Example:
        >>> logger = EndpointLogger("field_extraction")
        >>> logger.info("Processing started")
        >>> logger.info("Found 10 fields")
        >>> logger.error("Failed to parse field 5")
        >>> return {"logs": logger.get_logs(), "status": "complete"}
    """
    
    def __init__(self, endpoint_name: str):
        """
        Initialize endpoint logger.
        
        Args:
            endpoint_name: Name of the endpoint (e.g., "field_extraction")
        """
        self.endpoint_name = endpoint_name
        self.logs: List[str] = []
        self.logger = logging.getLogger(f"endpoints.{endpoint_name}")
        self.start_time = datetime.now()
    
    def info(self, msg: str) -> None:
        """
        Log info message.
        
        Args:
            msg: Message to log
        """
        self.logger.info(msg)
        self.logs.append(f"[INFO] {msg}")
    
    def error(self, msg: str, exc_info: bool = False) -> None:
        """
        Log error message.
        
        Args:
            msg: Message to log
            exc_info: Whether to include exception traceback
        """
        self.logger.error(msg, exc_info=exc_info)
        self.logs.append(f"[ERROR] {msg}")
    
    def warning(self, msg: str) -> None:
        """
        Log warning message.
        
        Args:
            msg: Message to log
        """
        self.logger.warning(msg)
        self.logs.append(f"[WARN] {msg}")
    
    def debug(self, msg: str) -> None:
        """
        Log debug message (not added to logs list).
        
        Debug messages are logged to the server but not included in
        the accumulated logs returned to the client.
        
        Args:
            msg: Message to log
        """
        self.logger.debug(msg)
    
    def get_logs(self) -> List[str]:
        """
        Get accumulated logs with execution time.
        
        Returns:
            List of log messages including final completion time
        """
        duration = (datetime.now() - self.start_time).total_seconds()
        return self.logs + [f"[COMPLETE] Total execution time: {duration:.2f}s"]
    
    def get_duration(self) -> float:
        """
        Get execution duration in seconds.
        
        Returns:
            Duration since logger was created
        """
        return (datetime.now() - self.start_time).total_seconds()
