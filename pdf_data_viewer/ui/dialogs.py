"""Dialog boxes for the PDF Data Viewer application."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QGroupBox, QRadioButton,
                              QButtonGroup, QComboBox, QLineEdit, QLabel, QDialogButtonBox)
from ..config import META_FIELDS, LINE_ITEM_FIELDS

class AnnotationFieldDialog(QDialog):
    """Dialog for selecting the field type for annotations."""
    
    def __init__(self, parent=None, last_line_item_number=""):
        """
        Initialize the dialog.
        
        Args:
            parent (QWidget, optional): Parent widget
            last_line_item_number (str, optional): Last used line item number
        """
        super().__init__(parent)
        self.setWindowTitle("Annotation Field Selection")
        self.setMinimumWidth(400)
        
        # Store the last line item number used
        self.last_line_item_number = last_line_item_number
        
        # Create the dialog layout
        self.main_layout = QVBoxLayout(self)
        
        # Create radio button group for data type selection
        self.type_group_box = QGroupBox("Annotation Type")
        self.type_layout = QVBoxLayout()
        
        self.meta_radio = QRadioButton("Meta Data")
        self.line_item_radio = QRadioButton("Line Item Data")
        
        self.type_button_group = QButtonGroup(self)
        self.type_button_group.addButton(self.meta_radio, 1)
        self.type_button_group.addButton(self.line_item_radio, 2)
        
        self.type_layout.addWidget(self.meta_radio)
        self.type_layout.addWidget(self.line_item_radio)
        self.type_group_box.setLayout(self.type_layout)
        
        # Create field selection combo box
        self.field_layout = QFormLayout()
        self.field_combo = QComboBox()
        self.field_layout.addRow("Field:", self.field_combo)
        
        # Create line item number input (initially hidden)
        self.line_item_number_input = QLineEdit()
        self.line_item_number_input.setText(self.last_line_item_number)
        self.line_item_number_label = QLabel("Line Item Number:")
        self.field_layout.addRow(self.line_item_number_label, self.line_item_number_input)
        
        # Add the form to the main layout
        self.main_layout.addWidget(self.type_group_box)
        self.main_layout.addLayout(self.field_layout)
        
        # Add OK and Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)
        
        # Connect radio buttons to update available fields
        self.meta_radio.toggled.connect(self.updateFieldOptions)
        
        # Default to meta data selected
        self.meta_radio.setChecked(True)
        self.updateFieldOptions()
        
    def updateFieldOptions(self):
        """Update field options based on selected type."""
        self.field_combo.clear()
        
        if self.meta_radio.isChecked():
            self.field_combo.addItems(META_FIELDS)
            self.line_item_number_label.setVisible(False)
            self.line_item_number_input.setVisible(False)
        else:
            self.field_combo.addItems(LINE_ITEM_FIELDS)
            self.line_item_number_label.setVisible(True)
            self.line_item_number_input.setVisible(True)
            
    def getFieldInfo(self):
        """
        Get the selected field information.
        
        Returns:
            dict: Field information
        """
        if self.meta_radio.isChecked():
            return {
                'type': 'meta',
                'field': self.field_combo.currentText(),
                'line_item_number': ''
            }
        else:
            return {
                'type': 'line_item',
                'field': self.field_combo.currentText(),
                'line_item_number': self.line_item_number_input.text()
            }
