"""Data panel for displaying extracted data and annotations."""

from PySide6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QLabel, QTableWidget,
                              QTableWidgetItem, QPushButton, QHeaderView)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor


from ..config import DATE_FIELDS
from ..utils.date_utils import standardize_date

class DataPanel(QScrollArea):
    """Panel for displaying extracted data and annotations."""

    # Signal for index of selected annotation
    annotationSelected = Signal(int)
    
    def __init__(self, parent=None):
        """
        Initialize the data panel.
        
        Args:
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.setWidgetResizable(True)
        
        # Data content widget
        self.data_content = QWidget()
        self.data_layout = QVBoxLayout(self.data_content)
        
        # Info label
        self.data_label = QLabel("Data extracted from PDF will appear here")
        self.data_layout.addWidget(self.data_label)
        
        # Selected text section
        self.selected_text_label = QLabel("Selected Text:")
        self.data_layout.addWidget(self.selected_text_label)
        
        self.selected_text_display = QLabel("No text selected")
        self.selected_text_display.setWordWrap(True)
        self.selected_text_display.setFrameShape(QLabel.Panel)
        self.selected_text_display.setFrameShadow(QLabel.Sunken)
        self.selected_text_display.setMinimumHeight(100)
        self.data_layout.addWidget(self.selected_text_display)
        
        # Annotations section
        self.annotations_label = QLabel("Annotations:")
        self.data_layout.addWidget(self.annotations_label)
        
        # Annotations table
        self.annotations_list = QTableWidget()
        self.annotations_list.setColumnCount(6)
        self.annotations_list.setHorizontalHeaderLabels(
            ["Page", "Type", "Item #", "Field", "Text", "Delete"]
        )
        self.annotations_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.annotations_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.annotations_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.annotations_list.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.annotations_list.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.annotations_list.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.data_layout.addWidget(self.annotations_list)

        # Connect cell clicked signal to our handler
        self.annotations_list.cellClicked.connect(self.onAnnotationCellClicked)
        self.data_layout.addWidget(self.annotations_list)
        
        # Export button
        self.export_button = QPushButton("Export Annotations to CSV")
        self.data_layout.addWidget(self.export_button)
        
        # Set as the panel's widget
        self.setWidget(self.data_content)
    
    def updatePDFInfo(self, doc):
        """
        Update the panel with PDF information.
        
        Args:
            doc: PDF document handler
        """
        if not doc or not doc.doc:
            self.data_label.setText("No PDF loaded")
            return
            
        # Create info text
        info_text = "PDF Information:\n"
        info_text += f"Pages: {doc.page_count}\n"
        
        # Add metadata if available
        metadata = doc.get_metadata()
        if metadata:
            if metadata.get('title'):
                info_text += f"Title: {metadata.get('title')}\n"
            if metadata.get('author'):
                info_text += f"Author: {metadata.get('author')}\n"
            if metadata.get('subject'):
                info_text += f"Subject: {metadata.get('subject')}\n"
                
        # Update display
        self.data_label.setText(info_text)
        self.clearSelection()
        self.clearAnnotations()
    
    def clearSelection(self):
        """Clear the selected text display."""
        self.selected_text_display.setText("No text selected")
    
    def clearAnnotations(self):
        """Clear the annotations list."""
        self.annotations_list.setRowCount(0)
    
    def updateSelectedText(self, text):
        """
        Update the selected text display.
        
        Args:
            text (str): Selected text
        """
        if text:
            self.selected_text_display.setText(text)
    
    def updateAnnotationsList(self, annotations, on_delete_callback=None):
        """
        Update the annotations list.
        
        Args:
            annotations (list): List of annotation dictionaries
            on_delete_callback (function, optional): Callback for delete button clicks
        """
        # Clear the list
        self.annotations_list.setRowCount(0)
        
        # Debug multi-page annotations
        multipage_count = sum(1 for a in annotations if a.get('is_multipage', False))
        print(f"Displaying {len(annotations)} annotations, of which {multipage_count} are multi-page")
        
        # Add each annotation
        for i, annot in enumerate(annotations):
            if 'page' not in annot or 'text' not in annot:
                continue
                
            row_position = self.annotations_list.rowCount()
            self.annotations_list.insertRow(row_position)
            
            # Page number (1-based)
            page_item = QTableWidgetItem(str(annot['page'] + 1))
            self.annotations_list.setItem(row_position, 0, page_item)
            
            # Annotation type
            type_text = annot.get('type', '')
            if annot.get('is_multipage', False):
                position = annot.get('multipage_position', '')
                multipage_type = annot.get('multipage_type', '')
                if position is not None and multipage_type:
                    type_text += f" ({position}/{multipage_type})"
                    print(f"Adding type text with multi-page info: {type_text}")
            type_item = QTableWidgetItem(type_text)
            self.annotations_list.setItem(row_position, 1, type_item)
            
            # Line item number
            line_item_num = QTableWidgetItem(annot.get('line_item_number', ''))
            self.annotations_list.setItem(row_position, 2, line_item_num)
            
            # Field name
            field_item = QTableWidgetItem(annot.get('field', ''))
            self.annotations_list.setItem(row_position, 3, field_item)
            
            # Text content (with date formatting if applicable)
            display_text = annot['text']
            
            if annot.get('field') in DATE_FIELDS:
                if 'standardized_date' in annot and annot['standardized_date']:
                    display_text = f"{annot['text']} → {annot['standardized_date']}"
                else:
                    # Try to standardize now
                    std_date = standardize_date(annot['text'])
                    if std_date:
                        display_text = f"{annot['text']} → {std_date}"
            
            # Truncate if too long
            if len(display_text) > 50:
                display_text = display_text[:47] + "..."
                
            text_item = QTableWidgetItem(display_text)
            
            # Make multi-page annotations visually distinct
            if annot.get('is_multipage', False):
                print(f"Setting blue background for multi-page annotation (row {row_position})")
                text_item.setBackground(QColor(240, 240, 255))  # Light blue background
                
            self.annotations_list.setItem(row_position, 4, text_item)
            
            # Delete button
            if on_delete_callback:
                delete_button = QPushButton("[x]")
                delete_button.setFixedWidth(30)
                # Use a lambda to capture the current index
                delete_func = lambda checked, idx=i: on_delete_callback(idx)
                delete_button.clicked.connect(delete_func)
                self.annotations_list.setCellWidget(row_position, 5, delete_button)
        
        # Resize columns
        self.annotations_list.resizeColumnsToContents()

    def onAnnotationCellClicked(self, row, column):
        """
        Handle clicks on the annotation list.
        
        Args:
            row (int): Row index
            column (int): Column index
        """
        # Ignore clicks on the delete button column (column 5)
        if column == 5:
            return
        
        # Emit signal with annotation index
        self.annotationSelected.emit(row)
