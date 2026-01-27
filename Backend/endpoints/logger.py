"""
Endpoint Multi-Channel Logging Utility

Enhances standard Python logging with in-memory log accumulation. 
This allows endpoints to return detailed execution logs to the frontend 
while concurrently maintaining standard server-side log files.
"""

import logging
from typing import List
from datetime import datetime


class EndpointLogger:
    """
    Stateful logger that collects messages for inclusion in API responses.
    
    Combines the permanence of standard logging with the accessibility of 
    a per-request log buffer. This is essential for long-running operations
    where the user needs visibility into the current execution stage.
    
    Attributes:
        endpoint_name: Identifier used for the Python logger and metadata.
        logs: Ordered list of accumulated log strings.
        logger: Underlying standard logging.Logger instance.
        start_time: High-precision timestamp captured at initialization.
    """
    
    def __init__(self, endpoint_name: str):
        """
        Initialize a new logging session for an endpoint.
        
        Args:
            endpoint_name: Descriptive name for the API channel (e.g., "script_execution").
        """
        self.endpoint_name = endpoint_name
        self.logs: List[str] = []
        self.logger = logging.getLogger(f"endpoints.{endpoint_name}")
        self.start_time = datetime.now()
    

    # ============================================================================
    # LOGGING METHODS
    # ============================================================================

    def info(self, msg: str) -> None:
        """
        Record and broadcast an informational message.
        """
        self.logger.info(msg)
        self.logs.append(f"[INFO] {msg}")
    
    def error(self, msg: str, exc_info: bool = False) -> None:
        """
        Record a failure event with optional traceback detail.
        """
        self.logger.error(msg, exc_info=exc_info)
        self.logs.append(f"[ERROR] {msg}")
    
    def warning(self, msg: str) -> None:
        """
        Record a non-critical warning that may affect the result quality.
        """
        self.logger.warning(msg)
        self.logs.append(f"[WARN] {msg}")
    
    def debug(self, msg: str) -> None:
        """
        Record low-level debugging data. 
        
        Note: Debug messages are logged to the server logs but are 
        EXCLUDED from the final logs list returned to the user.
        """
        self.logger.debug(msg)
    

    # ============================================================================
    # STATE RETRIEVAL
    # ============================================================================

    def get_logs(self) -> List[str]:
        """
        Retrieve all accumulated messages, finalized with a duration summary.
        """
        duration = self.get_duration()
        return self.logs + [f"[COMPLETE] Total execution time: {duration:.2f}s"]
    
    def get_duration(self) -> float:
        """
        Calculate total execution time since this logger was instantiated.
        """
        return (datetime.now() - self.start_time).total_seconds()
