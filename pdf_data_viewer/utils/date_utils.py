"""Utilities for handling dates in the PDF Data Viewer."""

from dateutil.parser import parse
from datetime import datetime
import logging

# Get a logger for this module
logger = logging.getLogger(__name__)

def standardize_date(date_str, log_level='error'):
    """
    Convert various date formats to YYYY-MM-DD.
    
    Args:
        date_str (str): Date string in various formats
        log_level (str): Logging level for errors ('error', 'debug', 'none')
        
    Returns:
        str or None: Standardized date in YYYY-MM-DD format or None if parsing fails
    """
    if not date_str:
        return None
        
    # Clean the date string by removing brackets and extra whitespace
    cleaned_date_str = date_str.replace('[', '').replace(']', '').strip()
    
    # If the string is empty after cleaning, return None
    if not cleaned_date_str:
        return None
    
    try:
        date_obj = parse(cleaned_date_str)
        return date_obj.strftime("%Y-%m-%d")
    except Exception as e:
        # Log the error based on the requested log level
        error_msg = f"Error parsing date: {e}, text was: {date_str!r}"
        if log_level == 'error':
            logger.error(error_msg)
        elif log_level == 'debug':
            logger.debug(error_msg)
        # 'none' will not log anything
        return None