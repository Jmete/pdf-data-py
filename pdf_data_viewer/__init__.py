"""
PDF Data Viewer - A tool for viewing PDF files and extracting data through annotations.
"""

__version__ = "0.2.0"

# Set up logging
import logging
import os
import sys

# Determine project root directory (where setup.py is)
# If running as an installed package, use the current directory
if getattr(sys, 'frozen', False):
    # Running as a bundled executable
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    # Running from source
    MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(MODULE_DIR)  # Go up one level from the module directory

# Create logs directory at project root
logs_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(logs_dir, exist_ok=True)

# Configure logging
log_file = os.path.join(logs_dir, 'pdf_data_viewer.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Log the paths to verify everything is set up correctly
logger = logging.getLogger(__name__)
logger.info(f"Application started. Project root: {PROJECT_ROOT}")
logger.info(f"Log file location: {log_file}")