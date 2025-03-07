# PDF Data Viewer

A Python application for viewing PDF files and extracting structured data through annotations.

## Features

- High-quality PDF viewing with support for multiple pages
- Text selection and annotation capabilities
- Data extraction from PDFs with field mapping
- Date standardization for extracted data
- SQLite database storage for annotations
- CSV export for extracted data

## Requirements

- Python 3.9+
- PySide6
- PyMuPDF (fitz)
- python-dateutil

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pdf-data-py.git
cd pdf-data-py
```

2. Install the package:
```bash
pip install -e .
```

## Usage

Run the application:
```bash
python -m pdf_data_viewer.main
```

Or use the entry point:
```bash
pdf-data-viewer
```

## Data Extraction

The application supports the extraction of the following data types:

### Metadata
- Document name
- Customer name
- Buyer name
- Currency
- RFQ date
- Due date

### Line Item Data
- Line item number
- Material number
- Part number
- Description
- Full description
- Quantity
- Unit of measure
- Requested delivery date
- Delivery point
- Manufacturer name

## Development

### Project Structure
```
pdf-data-py/
├── data/                     # Data directory
│   ├── annotations.db        # SQLite database file
│   └── exports/              # CSV export directory
└── pdf_data_viewer/          # Main package
    ├── core/                 # Core functionality
    ├── database/             # Database operations
    ├── ui/                   # User interface
    └── utils/                # Utility functions
```

### Building from source

```bash
python setup.py build
```

## License

[MIT License](LICENSE)
