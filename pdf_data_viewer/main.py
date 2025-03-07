"""Entry point for the PDF Data Viewer application."""

import sys
from PySide6.QtWidgets import QApplication
from .ui.main_window import MainWindow

def main():
    """
    Main entry point for the application.
    
    Returns:
        int: Exit code
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
