"""
Error logging utility for the betting system.
Logs all errors and warnings to a file while keeping console output minimal.
"""

import logging
from pathlib import Path
from datetime import datetime
import sys

class ErrorLogger:
    """Centralized error logging to file."""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super(ErrorLogger, cls).__new__(cls)
            cls._instance._setup_logger()
        return cls._instance
    
    def _setup_logger(self):
        """Setup the file logger."""
        # Create logs directory
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self._logger = logging.getLogger('betting_system')
        self._logger.setLevel(logging.DEBUG)
        
        # Remove any existing handlers
        self._logger.handlers = []
        
        # Create file handler with rotation by date
        log_file = log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.WARNING)
        
        # Create detailed file handler for all logs (debug level)
        debug_log_file = log_dir / f"debug_{datetime.now().strftime('%Y%m%d')}.log"
        debug_handler = logging.FileHandler(debug_log_file)
        debug_handler.setLevel(logging.DEBUG)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(detailed_formatter)
        debug_handler.setFormatter(detailed_formatter)
        
        # Add handlers
        self._logger.addHandler(file_handler)
        self._logger.addHandler(debug_handler)
    
    def error(self, message: str, exc_info=None):
        """Log an error message."""
        self._logger.error(message, exc_info=exc_info)
    
    def warning(self, message: str):
        """Log a warning message."""
        self._logger.warning(message)
    
    def info(self, message: str):
        """Log an info message."""
        self._logger.info(message)
    
    def debug(self, message: str):
        """Log a debug message."""
        self._logger.debug(message)
    
    def exception(self, message: str):
        """Log an exception with traceback."""
        self._logger.exception(message)


# Global instance
logger = ErrorLogger()
