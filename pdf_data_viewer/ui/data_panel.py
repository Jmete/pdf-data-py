"""Data panel for displaying extracted data and annotations with collapsible groups."""

from PySide6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QLabel, QTableWidget,
                              QTableWidgetItem, QPushButton, QHeaderView, QFrame,
                              QHBoxLayout, QToolButton, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QFont


from ..config import DATE_FIELDS
from ..utils.date_utils import standardize_date

class CollapsibleSection(QWidget):
    """A collapsible section widget that can be expanded or collapsed."""
    
    def __init__(self, title, parent=None):
        """
        Initialize the collapsible section.
        
        Args:
            title (str): Title for the section header
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header frame
        self.header_frame = QFrame()
        self.header_frame.setFrameShape(QFrame.StyledPanel)
        self.header_frame.setFrameShadow(QFrame.Raised)
        self.header_frame.setStyleSheet("background-color: #f0f0f0;")
        self.header_frame.setCursor(Qt.PointingHandCursor)
        
        # Header layout - make it more compact
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(5, 2, 5, 2)
        
        # Toggle button for expand/collapse
        self.toggle_button = QToolButton()
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setIconSize(QSize(16, 16))
        # Set arrows for expand/collapse (using text as fallback)
        self.toggle_button.setText("►")
        self.toggle_button.setFont(QFont('Arial', 9))
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.toggle_button.clicked.connect(self.toggle_content)
        
        # Title label
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont('Arial', 10, QFont.Bold))
        
        # Badge label for item count
        self.badge_label = QLabel("0")
        self.badge_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.badge_label.setStyleSheet("""
            padding: 2px 8px;
            background-color: #e0e0e0;
            border-radius: 10px;
        """)
        
        # Add widgets to header layout
        self.header_layout.addWidget(self.toggle_button)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.badge_label)
        
        # Content widget
        self.content = QWidget()
        self.content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)  # Fixed height
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(5, 2, 2, 2)  # Reduced margins
        self.content_layout.setSpacing(0)  # No spacing
        self.content.setVisible(False)  # Initially collapsed
        
        # Add widgets to main layout
        self.main_layout.addWidget(self.header_frame)
        self.main_layout.addWidget(self.content)
        
        # Connect header click to toggle
        self.header_frame.mousePressEvent = self.header_clicked
        
        # Styling
        self.setStyleSheet("""
            CollapsibleSection {
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                margin-bottom: 3px;
            }
        """)
        
        # Size policy to make the widget wrap its content tightly
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    
    def header_clicked(self, event):
        """Handle click on the header area."""
        self.toggle_content()
    
    def toggle_content(self):
        """Toggle the visibility of the content area."""
        self.content.setVisible(not self.content.isVisible())
        
        # Update toggle button text/icon
        if self.content.isVisible():
            self.toggle_button.setText("▼")
        else:
            self.toggle_button.setText("►")
    
    def set_badge_count(self, count):
        """Update the badge counter."""
        self.badge_label.setText(str(count))
    
    def add_widget(self, widget):
        """Add a widget to the content area."""
        self.content_layout.addWidget(widget)
    
    def expand(self):
        """Expand the section to show content."""
        self.content.setVisible(True)
        self.toggle_button.setText("▼")
    
    def collapse(self):
        """Collapse the section to hide content."""
        self.content.setVisible(False)
        self.toggle_button.setText("►")


class DataPanel(QScrollArea):
    """Panel for displaying extracted data and annotations using collapsible groups."""

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
        self.data_layout.setSpacing(5)  # Reduced spacing
        
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
        self.selected_text_display.setMinimumHeight(80)  # Slightly smaller
        self.data_layout.addWidget(self.selected_text_display)
        
        # Annotations sections
        self.annotations_label = QLabel("Annotations:")
        self.data_layout.addWidget(self.annotations_label)
        
        # We'll create the metadata section only when needed
        self.meta_section = None
        self.meta_table = None
        
        # Line items container - we'll add line item sections dynamically
        self.line_items_container = QWidget()
        self.line_items_layout = QVBoxLayout(self.line_items_container)
        self.line_items_layout.setContentsMargins(0, 0, 0, 0)
        self.line_items_layout.setSpacing(2)  # Compact spacing
        self.data_layout.addWidget(self.line_items_container)
        
        # Map to store line item sections by line item number
        self.line_item_sections = {}
        
        # Export button
        self.export_button = QPushButton("Export Annotations to CSV")
        self.data_layout.addWidget(self.export_button)
        
        # Add stretch at the end
        self.data_layout.addStretch()
        
        # Set as the panel's widget
        self.setWidget(self.data_content)
        
        # Store mapping between annotation index and its location (section, table, row)
        self.annotation_index_map = {}
        
    def create_table(self, headers):
        """Create a table with the given headers."""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        
        # Set last column as fixed width for delete button
        if "Delete" in headers:
            delete_col = headers.index("Delete")
            table.horizontalHeader().setSectionResizeMode(delete_col, QHeaderView.ResizeToContents)
        
        # Set stretch for the text column
        text_col = headers.index("Text") if "Text" in headers else 1
        table.horizontalHeader().setSectionResizeMode(text_col, QHeaderView.Stretch)
        
        # Set other columns to resize to contents
        for i in range(len(headers)):
            if i != text_col and (i != delete_col if "Delete" in headers else True):
                table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        # Connect cell clicked signal
        table.cellClicked.connect(self.onTableCellClicked)
        
        # Adjust row height to be more compact
        table.verticalHeader().setVisible(False)  # Hide row numbers
        table.verticalHeader().setDefaultSectionSize(22)  # Compact row height
        
        # Make table size to content
        table.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        return table
    
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
        """Clear all annotations from tables and remove line item sections."""
        # Clear metadata section if it exists
        if self.meta_section:
            self.data_layout.removeWidget(self.meta_section)
            self.meta_section.deleteLater()
            self.meta_section = None
            self.meta_table = None
        
        # Clear line items
        for section in self.line_item_sections.values():
            self.line_items_layout.removeWidget(section)
            section.deleteLater()
        
        self.line_item_sections = {}
        self.annotation_index_map = {}
    
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
        Update the annotations list with collapsible grouping.
        
        Args:
            annotations (list): List of annotation dictionaries
            on_delete_callback (function, optional): Callback for delete button clicks
        """
        # Clear existing annotations
        self.clearAnnotations()
        
        if not annotations:
            return
            
        # Group annotations by type and line item number
        meta_annotations = []
        line_item_annotations = {}
        
        for i, annot in enumerate(annotations):
            if 'type' not in annot or 'text' not in annot:
                continue
                
            if annot.get('type') == 'meta':
                meta_annotations.append((i, annot))
            elif annot.get('type') == 'line_item':
                line_num = annot.get('line_item_number', '')
                if line_num not in line_item_annotations:
                    line_item_annotations[line_num] = []
                line_item_annotations[line_num].append((i, annot))
        
        # Fill metadata section
        self._populate_meta_section(meta_annotations, on_delete_callback)
        
        # Fill line item sections
        self._populate_line_item_sections(line_item_annotations, on_delete_callback)
    
    def _populate_meta_section(self, meta_annotations, on_delete_callback):
        """Populate the metadata section with annotation data."""
        if not meta_annotations:
            # If there are no metadata annotations, remove the section if it exists
            if self.meta_section:
                self.data_layout.removeWidget(self.meta_section)
                self.meta_section.deleteLater()
                self.meta_section = None
                self.meta_table = None
            return
            
        # Create the metadata section if it doesn't exist
        if not self.meta_section:
            self.meta_section = CollapsibleSection("Metadata")
            self.meta_table = self.create_table(["Field", "Text", "Delete"])
            self.meta_section.add_widget(self.meta_table)
            # Insert at position right after annotations label
            index = self.data_layout.indexOf(self.annotations_label) + 1
            self.data_layout.insertWidget(index, self.meta_section)
        else:
            # Clear existing rows
            self.meta_table.setRowCount(0)
        
        for i, (index, annot) in enumerate(meta_annotations):
            row_position = self.meta_table.rowCount()
            self.meta_table.insertRow(row_position)
            
            # Field name
            field_item = QTableWidgetItem(annot.get('field', ''))
            self.meta_table.setItem(row_position, 0, field_item)
            
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
                text_item.setBackground(QColor(240, 240, 255))  # Light blue background
                
            self.meta_table.setItem(row_position, 1, text_item)
            
            # Delete button
            if on_delete_callback:
                delete_button = QPushButton("[x]")
                delete_button.setFixedWidth(30)
                delete_button.setFixedHeight(20)  # Make button smaller
                # Use a lambda to capture the current annotation index
                delete_func = lambda checked, idx=index: on_delete_callback(idx)
                delete_button.clicked.connect(delete_func)
                self.meta_table.setCellWidget(row_position, 2, delete_button)
            
            # Map row to annotation index
            self.annotation_index_map[f"meta_{row_position}"] = index
        
        # Update badge count
        self.meta_section.set_badge_count(len(meta_annotations))
        
        # Expand section if it has items
        if len(meta_annotations) > 0:
            self.meta_section.expand()
            
        # Calculate exact height needed for the table
        header_height = self.meta_table.horizontalHeader().height()
        row_count = self.meta_table.rowCount()
        row_height = self.meta_table.rowHeight(0)
        table_border = 2  # Border pixels
        total_table_height = header_height + (row_height * row_count) + table_border
        
        # Set the table height precisely
        self.meta_table.setFixedHeight(total_table_height)
        
        # Force layout update to apply the size constraints
        self.meta_table.updateGeometry()
        self.meta_section.content.updateGeometry()
        self.meta_section.updateGeometry()
    
    def _populate_line_item_sections(self, line_item_annotations, on_delete_callback):
        """Populate the line item sections with annotation data."""
        # Sort line item numbers numerically if possible
        sorted_line_items = sorted(line_item_annotations.keys(), 
                                 key=lambda x: int(x) if x.isdigit() else float('inf'))
        
        for line_num in sorted_line_items:
            # Create a section for this line item
            section_title = f"Line Item #{line_num}" if line_num else "Line Item (No Number)"
            section = CollapsibleSection(section_title)
            
            # Create a table for this line item's annotations
            table = self.create_table(["Field", "Text", "Delete"])
            section.add_widget(table)
            
            # Add the section to our layout
            self.line_items_layout.addWidget(section)
            self.line_item_sections[line_num] = section
            
            # Populate the table
            annotations = line_item_annotations[line_num]
            for i, (index, annot) in enumerate(annotations):
                row_position = table.rowCount()
                table.insertRow(row_position)
                
                # Field name
                field_item = QTableWidgetItem(annot.get('field', ''))
                table.setItem(row_position, 0, field_item)
                
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
                    text_item.setBackground(QColor(240, 240, 255))  # Light blue background
                    
                table.setItem(row_position, 1, text_item)
                
                # Delete button
                if on_delete_callback:
                    delete_button = QPushButton("[x]")
                    delete_button.setFixedWidth(30)
                    delete_button.setFixedHeight(20)  # Make button smaller
                    # Use a lambda to capture the current annotation index
                    delete_func = lambda checked, idx=index: on_delete_callback(idx)
                    delete_button.clicked.connect(delete_func)
                    table.setCellWidget(row_position, 2, delete_button)
                
                # Map row to annotation index
                self.annotation_index_map[f"line_{line_num}_{row_position}"] = index
            
            # Update badge count
            section.set_badge_count(len(annotations))
            
            # Expand section
            section.expand()
            
            # Calculate exact height needed for the table
            header_height = table.horizontalHeader().height()
            row_count = table.rowCount()
            row_height = table.rowHeight(0)
            table_border = 2  # Border pixels
            total_table_height = header_height + (row_height * row_count) + table_border
            
            # Set table height exactly
            table.setFixedHeight(total_table_height)
            
            # Force layout update to apply the size constraints
            table.updateGeometry()
            section.content.updateGeometry()
            section.updateGeometry()
    
    def onTableCellClicked(self, row, column):
        """
        Handle clicks on any annotation table.
        
        Args:
            row (int): Row index
            column (int): Column index
        """
        # Ignore clicks on the delete button column (column 2)
        if column == 2:
            return
        
        # Find which table was clicked
        sender = self.sender()
        
        # Determine the annotation index based on which table was clicked
        annotation_index = None
        
        if self.meta_table and sender == self.meta_table:
            key = f"meta_{row}"
            if key in self.annotation_index_map:
                annotation_index = self.annotation_index_map[key]
        else:
            # Find which line item table it is
            for line_num, section in self.line_item_sections.items():
                # Extract the table from the section
                table = None
                for i in range(section.content_layout.count()):
                    widget = section.content_layout.itemAt(i).widget()
                    if isinstance(widget, QTableWidget):
                        table = widget
                        break
                
                if table and sender == table:
                    key = f"line_{line_num}_{row}"
                    if key in self.annotation_index_map:
                        annotation_index = self.annotation_index_map[key]
                    break
        
        # Emit signal with annotation index if found
        if annotation_index is not None:
            self.annotationSelected.emit(annotation_index)