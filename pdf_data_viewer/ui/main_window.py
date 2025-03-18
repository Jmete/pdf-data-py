"""Main window for the PDF Data Viewer application."""

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QSplitter, QToolBar,
                              QFileDialog, QMessageBox, QLabel, QSlider,
                              QComboBox, QApplication, QDialog)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QKeySequence, QAction

import os
import fitz

from ..config import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, APP_NAME, EXPORT_DIR
from ..database.models import AnnotationDB
from ..core.pdf_handler import PDFDocument
from ..core.annotation_handler import AnnotationHandler
from .pdf_viewer import PDFViewer
from .data_panel import DataPanel
from .dialogs import AnnotationFieldDialog

class MainWindow(QMainWindow):
    """Main window for the PDF Data Viewer application."""
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        # Initialize database
        self.db = AnnotationDB()
        
        # Initialize PDF document and annotation handlers
        self.current_file = None
        
        # Set up UI
        self.initUI()
        
        # Enable focus for key events
        self.setFocusPolicy(Qt.StrongFocus)
    
    def initUI(self):
        """Initialize the user interface."""
        # Set window properties
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create toolbar
        self.createToolbar()
        
        # Create splitter for the two panels
        self.splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.splitter)
        
        # Initialize PDF viewer
        self.pdf_viewer = PDFViewer()
        
        # Initialize annotation handler
        self.annotation_handler = AnnotationHandler(self.pdf_viewer.pdf_doc)
        
        # Initialize data panel
        self.data_panel = DataPanel()
        
        # Connect signals
        self.connectSignals()
        
        # Add panels to splitter (2:1 ratio)
        self.splitter.addWidget(self.pdf_viewer)
        self.splitter.addWidget(self.data_panel)
        self.splitter.setSizes([2 * self.width() // 3, self.width() // 3])
        
        # Create menu bar
        self.createMenuBar()
        
        # Set up drag and drop
        self.setAcceptDrops(True)
        
        # Set initial focus
        self.pdf_viewer.setFocus()
        
        # Setup status bar
        self.statusBar().showMessage("Ready. Use Ctrl+Left click to select text/create annotations")
    
    def connectSignals(self):
        """Connect signals between components."""
        # PDF viewer signals
        self.pdf_viewer.textSelected.connect(self.onTextSelected)
        self.pdf_viewer.annotationAdded.connect(self.onAnnotationAdded)
        self.pdf_viewer.annotationRemoved.connect(self.updateAnnotationsList)
        self.pdf_viewer.statusUpdated.connect(self.updateStatus)
        
        # Data panel signals
        self.data_panel.export_button.clicked.connect(self.exportAnnotationsToCSV)
        self.data_panel.annotationSelected.connect(self.onAnnotationSelected)
    
    def createMenuBar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Open action
        open_action = QAction("&Open", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.openFile)
        file_menu.addAction(open_action)
        
        # Export action
        export_action = QAction("&Export Annotations to CSV", self)
        export_action.triggered.connect(self.exportAnnotationsToCSV)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        # Undo action
        self.undo_action = QAction("&Undo Annotation", self)
        self.undo_action.triggered.connect(self.undoLastAnnotation)
        edit_menu.addAction(self.undo_action)
    
    def createToolbar(self):
        """Create the application toolbar."""
        toolbar = QToolBar("PDF Controls")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
        
        # Open file button
        open_btn = QAction("Open PDF", self)
        open_btn.setShortcut(QKeySequence.Open)
        open_btn.triggered.connect(self.openFile)
        toolbar.addAction(open_btn)
        
        toolbar.addSeparator()
        
        # Zoom controls
        zoom_in_btn = QAction("Zoom In [+]", self)
        zoom_in_btn.setShortcut(QKeySequence.ZoomIn)
        zoom_in_btn.triggered.connect(self.zoomIn)
        toolbar.addAction(zoom_in_btn)
        
        zoom_out_btn = QAction("Zoom Out [-]", self)
        zoom_out_btn.setShortcut(QKeySequence.ZoomOut)
        zoom_out_btn.triggered.connect(self.zoomOut)
        toolbar.addAction(zoom_out_btn)
        
        # Zoom slider
        zoom_slider_label = QLabel("Zoom:")
        toolbar.addWidget(zoom_slider_label)
        
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(50, 800)  # 50% to 800%
        self.zoom_slider.setValue(200)  # 200% default
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self.onZoomSliderChange)
        toolbar.addWidget(self.zoom_slider)
        
        # Zoom percentage label
        self.zoom_label = QLabel("200%")
        self.zoom_label.setFixedWidth(50)
        toolbar.addWidget(self.zoom_label)
        
        toolbar.addSeparator()
        
        # Navigation buttons
        prev_btn = QAction("Previous", self)
        prev_btn.setShortcut(QKeySequence.MoveToPreviousPage)
        prev_btn.triggered.connect(self.previousPage)
        toolbar.addAction(prev_btn)
        
        next_btn = QAction("Next", self)
        next_btn.setShortcut(QKeySequence.MoveToNextPage)
        next_btn.triggered.connect(self.nextPage)
        toolbar.addAction(next_btn)
        
        toolbar.addSeparator()
        
        # Annotation button
        annotate_btn = QAction("Add Annotation", self)
        annotate_btn.setShortcut("Ctrl+A")
        annotate_btn.triggered.connect(self.addAnnotation)
        toolbar.addAction(annotate_btn)
        
        # Undo annotation button
        undo_btn = QAction("Undo Annotation", self)
        undo_btn.triggered.connect(self.undoLastAnnotation)
        toolbar.addAction(undo_btn)
        
        # Export button
        export_btn = QAction("Export to CSV", self)
        export_btn.triggered.connect(self.exportAnnotationsToCSV)
        toolbar.addAction(export_btn)
        
        toolbar.addSeparator()
        
        # Render quality selector
        quality_label = QLabel("Quality:")
        toolbar.addWidget(quality_label)
        
        self.quality_selector = QComboBox()
        self.quality_selector.addItems(["Standard", "High", "Very High"])
        self.quality_selector.setCurrentIndex(1)  # Default to High
        self.quality_selector.currentIndexChanged.connect(self.onQualityChange)
        toolbar.addWidget(self.quality_selector)
    
    def openFile(self):
        """Open a PDF file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF File", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.loadPDF(file_path)
    
    def loadPDF(self, file_path):
        """
        Load and display a PDF file.
        
        Args:
            file_path (str): Path to the PDF file
        """
        # Show loading indicator
        self.statusBar().showMessage(f"Loading {os.path.basename(file_path)}...")
        QApplication.processEvents()  # Allow UI to update
        
        if self.pdf_viewer.loadDocument(file_path):
            # Store current file path
            self.current_file = file_path
            
            # Clear previous annotations
            self.annotation_handler.clear_annotations()
            
            # Update UI
            self.statusBar().showMessage(f"Loaded: {os.path.basename(file_path)}")
            self.data_panel.updatePDFInfo(self.pdf_viewer.pdf_doc)
            
            # Update zoom slider
            self.zoom_slider.setValue(int(self.pdf_viewer.zoom_factor * 100))
            self.zoom_label.setText(f"{int(self.pdf_viewer.zoom_factor * 100)}%")
            
            # Load annotations from database
            self.loadAnnotationsFromDatabase()
        else:
            self.statusBar().showMessage(f"Failed to load PDF: {os.path.basename(file_path)}")
    
    def loadAnnotationsFromDatabase(self):
        """Load annotations for the current PDF from the database."""
        if not self.current_file:
            return
        
        # Get annotations from database
        db_annotations = self.db.get_annotations_for_file(self.current_file)
        
        if db_annotations:
            print(f"Found {len(db_annotations)} annotations in database")
            multipage_count = sum(1 for a in db_annotations if a.get('is_multipage', False))
            print(f"Of which {multipage_count} are part of multi-page annotations")
            
            for db_annot in db_annotations:
                # Convert rect tuple to fitz.Rect
                rect_x0, rect_y0, rect_x1, rect_y1 = db_annot['rect']
                rect = fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1)
                
                # Add highlight to PDF
                self.pdf_viewer.pdf_doc.add_highlight_annotation(db_annot['page'], rect)
                
                # Store annotation data
                annot = {
                    'id': db_annot['id'],
                    'page': db_annot['page'],
                    'rect': rect,
                    'rect_str': db_annot['rect_str'],
                    'text': db_annot['text'],
                    'type': db_annot.get('type', ''),
                    'field': db_annot.get('field', ''),
                    'line_item_number': db_annot.get('line_item_number', ''),
                    'file_name': db_annot.get('file_name', os.path.basename(self.current_file))
                }
                
                # Add standardized date if present
                if 'standardized_date' in db_annot:
                    annot['standardized_date'] = db_annot['standardized_date']
                
                # Add multi-page annotation data if present
                if 'is_multipage' in db_annot and db_annot['is_multipage']:
                    annot['is_multipage'] = True
                    annot['multipage_position'] = db_annot.get('multipage_position')
                    annot['multipage_type'] = db_annot.get('multipage_type', '')
                    annot['group_id'] = db_annot.get('group_id', '')
                    print(f"Loaded multi-page annotation: position={annot['multipage_position']}, type={annot['multipage_type']}")
                
                # Add to annotation handler's list
                self.annotation_handler.annotations.append(annot)
                
                # Re-render the page
                self.pdf_viewer.renderPage(db_annot['page'])
            
            # Update annotations list in UI
            self.updateAnnotationsList()
            self.statusBar().showMessage(f"Loaded {len(db_annotations)} annotations from database")
        else:
            self.updateAnnotationsList()
            self.statusBar().showMessage(f"No annotations found for {os.path.basename(self.current_file)}")
    
    def onTextSelected(self, text):
        """
        Handle text selection from PDF viewer.
        
        Args:
            text (str): Selected text
        """
        self.data_panel.updateSelectedText(text)

    def onAnnotationSelected(self, index):
        """
        Handle selection of an annotation in the data panel.
        
        Args:
            index (int): Index of the selected annotation
        """
        if 0 <= index < len(self.annotation_handler.annotations):
            annotation = self.annotation_handler.annotations[index]
            
            if 'page' in annotation and 'rect' in annotation:
                # Scroll to the annotation
                self.pdf_viewer.scrollToAnnotation(annotation['page'], annotation['rect'])
                
                # Update status
                self.statusBar().showMessage(f"Navigated to annotation on page {annotation['page'] + 1}")
    
    def onAnnotationAdded(self, annotation):
        """
        Handle annotation addition.
        
        Args:
            annotation (dict): Annotation data
        """
        # Show field selection dialog only for the first part of multi-page annotations
        # or for single-page annotations
        show_dialog = not annotation.get('is_multipage', False) or annotation.get('multipage_type') == 'start'
        field_info = None
        
        if show_dialog:
            dialog = AnnotationFieldDialog(self, self.annotation_handler.last_line_item_number)
            if dialog.exec() == QDialog.Accepted:
                # Get field info
                field_info = dialog.getFieldInfo()
                
                # Store for multi-page annotations if needed
                if annotation.get('is_multipage', False):
                    self.last_field_info = field_info
                    self.last_annotation_group_id = annotation.get('group_id')
                    
                    # Process date fields with the complete text
                    if 'complete_text' in annotation:
                        text_to_use = annotation['complete_text']
                    else:
                        text_to_use = annotation['text']
                    self._process_date_field(field_info, text_to_use)
            else:
                # Dialog cancelled, remove any partial annotations
                self._cleanup_annotation(annotation)
                return
        else:
            # For continuing multi-page annotations, use the stored field info
            if hasattr(self, 'last_field_info') and hasattr(self, 'last_annotation_group_id'):
                if annotation.get('group_id') == self.last_annotation_group_id:
                    field_info = self.last_field_info
                
        # Add the annotation
        if field_info or not show_dialog:
            # Use the actual text from each page
            text_to_use = annotation['text']
            
            # Create the annotation
            complete_annotation = self.annotation_handler.add_annotation(
                annotation['page'],
                annotation['rect'],
                text_to_use,
                field_info,
                is_multipage=annotation.get('is_multipage', False),
                multipage_position=annotation.get('multipage_position'),
                multipage_type=annotation.get('multipage_type', ''),
                group_id=annotation.get('group_id', '')
            )
            
            # Add to database
            if self.current_file:
                annotation_id = self.db.add_annotation(self.current_file, complete_annotation)
                
                # Store the database ID
                if annotation_id and self.annotation_handler.annotations:
                    self.annotation_handler.annotations[-1]['id'] = annotation_id
            
            # Re-render the page
            self.pdf_viewer.renderPage(annotation['page'])
            
            # Update UI
            self.updateAnnotationsList()
        else:
            # No field info, remove annotation highlight
            self._cleanup_annotation(annotation)

    def _process_date_field(self, field_info, text):
        """Process date fields."""
        date_fields = ['rfq_date', 'due_date', 'requested_delivery_date']
        if field_info.get('field') in date_fields:
            from ..utils.date_utils import standardize_date
            
            # Clean the text for date fields
            cleaned_text = text.replace('[', '').replace(']', '').strip()
            
            # Pre-standardize the date and add it to the field info
            std_date = standardize_date(cleaned_text, log_level='error')
            if std_date:
                field_info['standardized_date'] = std_date
            else:
                # Alert user if date standardization failed
                QMessageBox.warning(
                    self,
                    "Date Standardization Failed",
                    f"Could not convert '{cleaned_text}' to a standardized date format.\n\n"
                    f"The annotation will be saved, but the date won't be standardized.\n"
                    f"You may want to redo this annotation with clearer date text."
                )

    def _cleanup_annotation(self, annotation):
        """Remove annotation highlights when needed."""
        # Dialog cancelled, remove the annotation highlight
        self.pdf_viewer.pdf_doc.remove_annotation(annotation['page'])
        
        # For multi-page selections, we may need to remove annotations from other pages
        if annotation.get('is_multipage', False) and annotation.get('group_id'):
            # Find and remove all annotations with this group_id
            group_id = annotation.get('group_id')
            for page_idx in range(self.pdf_viewer.pdf_doc.page_count):
                if page_idx != annotation['page']:
                    # This is simplistic - we should ideally track which pages were annotated
                    self.pdf_viewer.pdf_doc.remove_annotation(page_idx)
        
        # Re-render the page
        self.pdf_viewer.renderPage(annotation['page'])
    
    def updateAnnotationsList(self):
        """Update the annotations list in the data panel."""
        self.data_panel.updateAnnotationsList(
            self.annotation_handler.annotations, 
            self.onDeleteAnnotation
        )
    
    def onDeleteAnnotation(self, index):
        """
        Handle annotation deletion.
        
        Args:
            index (int): Annotation index to delete
        """
        if not self.annotation_handler.annotations or index >= len(self.annotation_handler.annotations):
            self.statusBar().showMessage(f"Invalid annotation index: {index}")
            return
        
        # Get the annotation
        annotation = self.annotation_handler.annotations[index]
        
        # Remove from PDF and list
        if self.annotation_handler.remove_annotation_by_index(index):
            # Remove from database if we have an ID
            if 'id' in annotation:
                success = self.db.remove_annotation(annotation['id'])
                if success:
                    self.statusBar().showMessage(f"Annotation {index} deleted")
                else:
                    self.statusBar().showMessage(f"Warning: Annotation removed from PDF but failed to delete from database")
            else:
                self.statusBar().showMessage(f"Annotation {index} deleted (no database ID)")
            
            # Re-render the page
            self.pdf_viewer.renderPage(annotation['page'])
            
            # Update UI
            self.updateAnnotationsList()
        else:
            self.statusBar().showMessage(f"Failed to remove annotation {index}")
    
    def undoLastAnnotation(self):
        """Remove the last annotation."""
        if not self.annotation_handler.annotations:
            self.statusBar().showMessage("No annotations to undo")
            return False
        
        # Get the last annotation
        last_annot = self.annotation_handler.annotations[-1]
        
        # Remove it
        if self.annotation_handler.remove_last_annotation():
            # Remove from database if it has an ID
            if 'id' in last_annot:
                success = self.db.remove_annotation(last_annot['id'])
                if not success:
                    print(f"Warning: Failed to remove annotation ID {last_annot.get('id')} from database")
            
            # Re-render the page
            self.pdf_viewer.renderPage(last_annot['page'])
            
            # Update UI
            self.updateAnnotationsList()
            self.statusBar().showMessage("Last annotation removed")
            return True
        else:
            self.statusBar().showMessage("Failed to remove annotation")
            return False
    
    def exportAnnotationsToCSV(self):
        """Export annotations for the current PDF to CSV."""
        if not self.current_file:
            QMessageBox.warning(self, "Export Error", "No PDF file is currently loaded.")
            return
        
        # Get filename for export
        file_name = os.path.basename(self.current_file).replace(".pdf", "_annotations.csv")
        default_path = os.path.join(EXPORT_DIR, file_name)
        
        # Make sure export directory exists
        os.makedirs(EXPORT_DIR, exist_ok=True)
        
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Export Annotations to CSV", default_path, "CSV Files (*.csv)"
        )
        
        if not output_path:
            return
        
        # Export using the database
        success = self.db.export_annotations_to_csv(self.current_file, output_path)
        
        if success:
            QMessageBox.information(self, "Export Successful", 
                                  f"Annotations exported to {output_path}")
        else:
            QMessageBox.warning(self, "Export Failed", 
                              "Failed to export annotations or no annotations to export.")
    
    def zoomIn(self):
        """Zoom in the PDF view."""
        self.pdf_viewer.zoomIn()
        # Update slider
        self.zoom_slider.setValue(int(self.pdf_viewer.zoom_factor * 100))
        self.zoom_label.setText(f"{int(self.pdf_viewer.zoom_factor * 100)}%")
    
    def zoomOut(self):
        """Zoom out the PDF view."""
        self.pdf_viewer.zoomOut()
        # Update slider
        self.zoom_slider.setValue(int(self.pdf_viewer.zoom_factor * 100))
        self.zoom_label.setText(f"{int(self.pdf_viewer.zoom_factor * 100)}%")
    
    def previousPage(self):
        """Go to previous page."""
        self.pdf_viewer.goToPrevPage()
    
    def nextPage(self):
        """Go to next page."""
        self.pdf_viewer.goToNextPage()
    
    def addAnnotation(self):
        """Toggle annotation mode."""
        self.pdf_viewer.is_annotating = not self.pdf_viewer.is_annotating
        if self.pdf_viewer.is_annotating:
            self.statusBar().showMessage("Annotation mode: ON (Ctrl+Left click to create annotation)")
        else:
            self.statusBar().showMessage("Annotation mode: OFF")
    
    def onZoomSliderChange(self, value):
        """
        Handle zoom slider value change.
        
        Args:
            value (int): New zoom percentage value
        """
        new_factor = value / 100.0
        if self.pdf_viewer.zoom_factor != new_factor:
            # Update zoom factor
            self.pdf_viewer.zoom_factor = new_factor
            
            # Update zoom label
            self.zoom_label.setText(f"{value}%")
            
            # Apply scaling
            self.pdf_viewer.resetTransform()
            self.pdf_viewer.scale(new_factor, new_factor)
            
            # Update status
            self.statusBar().showMessage(f"Zoom: {value}%")
    
    def onQualityChange(self, index):
        """
        Handle render quality change.
        
        Args:
            index (int): Index of the selected quality option
        """
        quality_map = {0: "standard", 1: "high", 2: "very high"}
        quality = quality_map.get(index, "high")
        
        # Update PDF document quality settings
        if quality != self.pdf_viewer.pdf_doc.render_quality:
            self.pdf_viewer.pdf_doc.render_quality = quality
            
            # Update DPI based on quality
            if quality == "standard":
                self.pdf_viewer.pdf_doc.dpi = 200
            elif quality == "high":
                self.pdf_viewer.pdf_doc.dpi = 350
            else:  # very high
                self.pdf_viewer.pdf_doc.dpi = 600
                
            # Save current zoom
            current_zoom = self.pdf_viewer.zoom_factor
            
            # Reload document if one is loaded
            if self.current_file:
                # Show status
                self.statusBar().showMessage(f"Applying {quality} quality rendering...")
                
                # Reload
                self.loadPDF(self.current_file)
                
                # Restore zoom
                self.pdf_viewer.zoom_factor = current_zoom
                self.pdf_viewer.resetTransform()
                self.pdf_viewer.scale(current_zoom, current_zoom)
                
                # Update zoom slider
                self.zoom_slider.setValue(int(current_zoom * 100))
                
                self.statusBar().showMessage(f"Quality set to {quality}, zoom: {int(current_zoom * 100)}%")
    
    def updateStatus(self, message):
        """
        Update the status bar message.
        
        Args:
            message (str): Status message
        """
        self.statusBar().showMessage(message)
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        # Check for Ctrl+Z
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            self.undoLastAnnotation()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def dragEnterEvent(self, event):
        """Handle drag enter events for drag and drop support."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Handle drop events for drag and drop support."""
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.loadPDF(file_path)
    
    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        # Maintain splitter proportions
        if hasattr(self, 'splitter'):
            self.splitter.setSizes([2 * self.width() // 3, self.width() // 3])
    
    def closeEvent(self, event):
        """Handle window close event."""
        if hasattr(self, 'db'):
            self.db.close()
        event.accept()