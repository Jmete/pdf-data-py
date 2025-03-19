"""Configuration settings for the PDF Data Viewer application."""

# Application settings
APP_NAME = "PDF Data Viewer"
APP_VERSION = "1.2.0"
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800

# PDF viewer settings
DEFAULT_ZOOM_FACTOR = 1.0
MIN_ZOOM = 0.1
MAX_ZOOM = 8.0
DEFAULT_DPI = 300
PAGE_GAP = 20  # Gap between pages in vertical view

# Annotation settings
HIGHLIGHT_COLOR = (0, 0, 255, 128)  # RGBA for annotations

# Database settings
import os

# Get the base directory of the package
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create a data directory inside the project
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Database file path
DB_PATH = os.path.join(DATA_DIR, "annotations.db")

# Default export directory
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# Date fields for standardization
DATE_FIELDS = ['rfq_date', 'due_date', 'requested_delivery_date']

# Metadata fields
META_FIELDS = [
    "document_name", "customer_name", "buyer_name", 
    "currency", "rfq_date", "due_date"
]

# Line item fields
LINE_ITEM_FIELDS = [
    "material_number", "part_number", "description",
    "full_description", "quantity", "unit_of_measure",
    "requested_delivery_date", "delivery_point", "manufacturer_name"
]
