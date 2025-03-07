import sys
import os
import fitz  # PyMuPDF
from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, QVBoxLayout, 
                              QHBoxLayout, QWidget, QScrollArea, QToolBar, 
                              QFileDialog, QLabel, QPushButton, QGraphicsView,
                              QGraphicsScene, QGraphicsPixmapItem, QTableWidget,
                              QTableWidgetItem, QSlider, QComboBox, QMessageBox,
                              QHeaderView, QDialog, QRadioButton, QButtonGroup,
                              QFormLayout, QLineEdit, QDialogButtonBox, QGroupBox)
from PySide6.QtCore import Qt, QRectF, Signal, QSize, QPoint, QPointF, QSizeF, QEvent
from PySide6.QtGui import (QAction, QIcon, QKeySequence, QPixmap, QImage, 
                          QCursor, QTransform, QColor, QPen, QBrush, QPainter)

# Create a dummy sip module with isdeleted function
class DummySip:
    @staticmethod
    def isdeleted(obj):
        # Try to access a property that should always exist
        try:
            obj.scenePos()
            return False
        except (RuntimeError, AttributeError):
            return True
        
sip = DummySip()

from database import AnnotationDB, standardize_date


class AnnotationFieldDialog(QDialog):
    """Dialog for selecting the field type for annotations"""
    
    def __init__(self, parent=None, last_line_item_number=""):
        super().__init__(parent)
        self.setWindowTitle("Annotation Field Selection")
        self.setMinimumWidth(400)
        
        # Define field lists
        self.meta_fields = [
            "document_name", "customer_name", "buyer_name", 
            "currency", "rfq_date", "due_date"
        ]
        
        self.line_item_fields = [
            "material_number", "part_number", "description",
            "full_description", "quantity", "unit_of_measure",
            "requested_delivery_date", "delivery_point", "manufacturer_name"
        ]
        
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
        """Update field options based on selected type"""
        self.field_combo.clear()
        
        if self.meta_radio.isChecked():
            self.field_combo.addItems(self.meta_fields)
            self.line_item_number_label.setVisible(False)
            self.line_item_number_input.setVisible(False)
        else:
            self.field_combo.addItems(self.line_item_fields)
            self.line_item_number_label.setVisible(True)
            self.line_item_number_input.setVisible(True)
            
    def getFieldInfo(self):
        """Get the selected field information"""
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


class PDFViewer(QGraphicsView):
    """Custom widget for displaying and interacting with PDF pages"""
    # Signals
    textSelected = Signal(str)
    annotationAdded = Signal(dict)  # Updated to include field info
    annotationRemoved = Signal()
    statusUpdated = Signal(str)  # Signal for status updates
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # PDF document properties
        self.doc = None
        self.pages = []  # Store rendered page images
        self.page_items = []  # Store QGraphicsItems for each page
        self.current_page = 0
        self.page_count = 0
        
        # View properties
        self.zoom_factor = 2.0  # Start with a larger default zoom
        self.min_zoom = 0.5
        self.max_zoom = 8.0
        self.dpi = 300  # High DPI for quality rendering
        self.render_quality = "high"  # Quality setting
        self.initial_zoom_set = False  # Flag to track if initial zoom has been set
        
        # Interaction flags
        self.is_panning = False
        self.is_selecting = False
        self.is_annotating = False
        self.selection_start = QPointF()
        self.selection_rect = None
        self.annotations = []
        
        # Store the last line item number used
        self.last_line_item_number = ""
        
        # Configure view
        self.setRenderHint(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Placeholder text
        self.placeholder = self.scene.addText("Drag and drop a PDF file here or use File > Open")
        self.placeholder.setPos(10, 10)
    
    def loadDocument(self, file_path):
        """Load a PDF document and render all pages"""
        try:
            # Close existing document if open
            if self.doc:
                self.doc.close()
                
            self.doc = fitz.open(file_path)
            self.page_count = len(self.doc)
            
            if self.page_count > 0:
                self.scene.clear()
                self.pages = []
                self.page_items = []
                self.annotations = []  # Clear annotations when loading a new document
                self.current_page = 0
                
                # Render all pages
                self.renderAllPages()
                
                return True
            else:
                QMessageBox.warning(self.parent(), "Empty Document", 
                                   "The PDF document contains no pages.")
                return False
        except Exception as e:
            QMessageBox.critical(self.parent(), "Error Loading PDF", 
                               f"Could not load the PDF file:\n{str(e)}")
            print(f"Error loading PDF: {str(e)}")
            return False
    
    def renderAllPages(self):
        """Render all pages of the PDF as a vertical stack"""
        if not self.doc:
            return
        
        # Clear scene and reset page arrays
        self.scene.clear()
        self.pages = []
        self.page_items = []
        
        # Track total height for positioning
        total_height = 0
        page_gap = 20  # Gap between pages
        
        # Display a status message
        self.scene.addText("Rendering pages, please wait...").setPos(10, 10)
        QApplication.processEvents()  # Allow UI to update
        
        # Create a dictionary of rendering parameters based on quality
        render_params = {
            "dpi": self.dpi,
            "alpha": False
        }
        
        # Additional params for high quality
        if self.render_quality == "high":
            render_params["colorspace"] = fitz.csRGB  # RGB colorspace
            # Use a matrix with higher values for better quality
            render_params["matrix"] = fitz.Matrix(2.0, 2.0)  # Scale up for better quality
        elif self.render_quality == "very high":
            render_params["colorspace"] = fitz.csRGB
            render_params["matrix"] = fitz.Matrix(3.0, 3.0)  # Even higher quality
        
        for page_num in range(self.page_count):
            # Get the page
            page = self.doc[page_num]
            
            # Render page with high quality settings
            pix = page.get_pixmap(**render_params)
            
            # Convert pixmap to QImage and then to QPixmap
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            # Create pixmap item and add to scene
            pixmap_item = QGraphicsPixmapItem(pixmap)
            pixmap_item.setPos(0, total_height)
            pixmap_item.setData(0, page_num)  # Store page number in item data
            
            # Enable text selection by making the pixmap item selectable
            pixmap_item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)
            
            # Add item to scene
            self.scene.addItem(pixmap_item)
            
            # Store page info
            self.pages.append({
                'pixmap': pixmap,
                'rect': QRectF(0, total_height, pixmap.width(), pixmap.height()),
                'page_obj': page,
                'words': page.get_text("words")  # Get word positions for text selection
            })
            self.page_items.append(pixmap_item)
            
            # Update total height for next page
            total_height += pixmap.height() + page_gap
            
            # Allow UI to update during rendering of large documents
            if page_num % 5 == 0:
                QApplication.processEvents()
        
        # Clear the "Rendering" message by setting scene rect
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        
        # Reset view to show the whole document
        self.resetView()
    
    def resetView(self):
        """Reset view to show the document with appropriate zoom"""
        # Set a reasonable initial zoom instead of fitting to view
        # which often makes the content too small
        scene_rect = self.scene.itemsBoundingRect()
        
        # Calculate a zoom that makes the document width fill about 80% of the view width
        if not self.initial_zoom_set and self.page_count > 0 and len(self.pages) > 0:
            first_page_width = self.pages[0]['pixmap'].width()
            view_width = self.viewport().width()
            
            # Calculate initial zoom to make the document a readable size
            if first_page_width > 0 and view_width > 0:
                # Target 90% of view width for the document
                target_width_ratio = a = 0.9
                calculated_zoom = (view_width * target_width_ratio) / first_page_width
                
                # Use the calculated zoom, but keep it within reasonable bounds
                self.zoom_factor = max(min(calculated_zoom, 2.0), 1.0)
                self.initial_zoom_set = True
        
        # Apply the zoom
        self.resetTransform()  # Clear any existing transform
        self.scale(self.zoom_factor, self.zoom_factor)
        
        # Center the content
        self.centerOn(scene_rect.center())
        
        # Emit status update
        self.statusUpdated.emit(f"Zoom: {int(self.zoom_factor * 100)}%")
    
    def renderPage(self, page_idx):
        """Re-render a specific page (e.g., after adding annotations)"""
        if not self.doc or page_idx < 0 or page_idx >= self.page_count:
            return
            
        # Get the page
        page = self.doc[page_idx]
        
        # Create rendering parameters based on quality setting
        render_params = {
            "dpi": self.dpi,
            "alpha": False
        }
        
        # Apply matrix based on render quality
        if self.render_quality == "high":
            render_params["colorspace"] = fitz.csRGB
            render_params["matrix"] = fitz.Matrix(2.0, 2.0)
        elif self.render_quality == "very high":
            render_params["colorspace"] = fitz.csRGB
            render_params["matrix"] = fitz.Matrix(3.0, 3.0)
        
        # Render page with high DPI
        pix = page.get_pixmap(**render_params)
        
        # Convert to QImage and QPixmap
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        
        # Safety check: make sure page_items exists and is valid
        if page_idx < len(self.pages) and page_idx < len(self.page_items):
            # Update the stored pixmap
            self.pages[page_idx]['pixmap'] = pixmap
            
            # Check if the page_items[page_idx] is still valid before updating
            try:
                # This will throw an exception if the object has been deleted
                if not sip.isdeleted(self.page_items[page_idx]):
                    self.page_items[page_idx].setPixmap(pixmap)
            except (RuntimeError, NameError):
                # Handle case where the object was deleted
                print(f"Warning: QGraphicsPixmapItem for page {page_idx} is not valid anymore.")
                # We'll need to recreate the page item
                self.scene.removeItem(self.page_items[page_idx])
                
                # Create a new pixmap item
                new_pixmap_item = QGraphicsPixmapItem(pixmap)
                
                # Position it at the same position as the original
                pos_y = 0
                if page_idx > 0:
                    # Calculate position based on previous pages
                    for i in range(page_idx):
                        pos_y += self.pages[i]['pixmap'].height() + 20  # 20 is the page gap
                
                new_pixmap_item.setPos(0, pos_y)
                new_pixmap_item.setData(0, page_idx)  # Store page number
                new_pixmap_item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)
                
                # Add to scene and update our references
                self.scene.addItem(new_pixmap_item)
                self.page_items[page_idx] = new_pixmap_item
        else:
            print(f"Warning: Page index {page_idx} is out of range.")
    
    def zoomIn(self):
        """Zoom in the view"""
        if self.zoom_factor < self.max_zoom:
            # Use a larger zoom factor for more noticeable zoom
            factor = 1.25
            self.zoom_factor *= factor
            self.scale(factor, factor)
            
            # Limit to max zoom
            if self.zoom_factor > self.max_zoom:
                self.zoom_factor = self.max_zoom
                
            # Emit status update
            self.statusUpdated.emit(f"Zoom: {int(self.zoom_factor * 100)}%")
    
    def zoomOut(self):
        """Zoom out the view"""
        if self.zoom_factor > self.min_zoom:
            # Use a larger zoom factor for more noticeable zoom
            factor = 1.25
            self.zoom_factor /= factor
            self.scale(1/factor, 1/factor)
            
            # Limit to min zoom
            if self.zoom_factor < self.min_zoom:
                self.zoom_factor = self.min_zoom
                
            # Emit status update
            self.statusUpdated.emit(f"Zoom: {int(self.zoom_factor * 100)}%")
    
    def goToPage(self, page_num):
        """Scroll view to specific page"""
        if 0 <= page_num < self.page_count:
            self.current_page = page_num
            # Scroll to the page's position
            self.centerOn(self.page_items[page_num])
    
    def goToNextPage(self):
        """Go to next page"""
        if self.current_page < self.page_count - 1:
            self.goToPage(self.current_page + 1)
    
    def goToPrevPage(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.goToPage(self.current_page - 1)
    
    def getCurrentPageText(self):
        """Extract text from current page"""
        if self.doc and 0 <= self.current_page < self.page_count:
            page = self.doc[self.current_page]
            return page.get_text()
        return ""
    
    def findPageAt(self, scene_pos):
        """Find which page is at the given scene position"""
        for i, page in enumerate(self.pages):
            if page['rect'].contains(scene_pos):
                return i, page
        return -1, None
    
    def mapPDFPositionToPage(self, scene_pos):
        """Map a scene position to PDF coordinates on the corresponding page"""
        page_idx, page = self.findPageAt(scene_pos)
        if page_idx >= 0:
            # Calculate position relative to the page
            page_pos = scene_pos - QPointF(page['rect'].left(), page['rect'].top())
            # Scale to PDF coordinates based on zoom and DPI
            pdf_x = page_pos.x() * 72 / self.dpi
            pdf_y = page_pos.y() * 72 / self.dpi
            return page_idx, (pdf_x, pdf_y)
        return -1, None
    
    def cleanTextForDateField(self, text, field_type):
        """Clean text for date fields by removing brackets"""
        date_fields = ['rfq_date', 'due_date', 'requested_delivery_date']
        if field_type in date_fields:
            # Remove brackets from text
            return text.replace('[', '').replace(']', '').strip()
        return text
    
    def selectTextInRegion(self, page_idx, start_pos, end_pos):
        """Select text in the specified region on the given page"""
        if not self.doc or page_idx < 0 or page_idx >= self.page_count:
            return ""
            
        page = self.doc[page_idx]
        
        # Create a rect from the two points
        rect = fitz.Rect(start_pos[0], start_pos[1], end_pos[0], end_pos[1])
        
        # Get text within the rect
        text = page.get_text("text", clip=rect)
        
        # Highlight the text in the document
        if text:
            highlight = page.add_highlight_annot(rect)
            
            # Create annotation without field info - will be added later
            # after the dialog is shown
            new_annotation = {
                'page': page_idx,
                'rect': rect,
                'rect_str': f"({rect.x0:.2f}, {rect.y0:.2f}, {rect.x1:.2f}, {rect.y1:.2f})",
                'text': text,
                'annot_id': len(self.annotations)  # Use a unique ID instead of a reference
            }
            
            # Store annotation temporarily
            self.annotations.append(new_annotation)
            
            # Re-render the page to show the highlight
            self.renderPage(page_idx)
            
            # Show field selection dialog
            dialog = AnnotationFieldDialog(self.parent(), self.last_line_item_number)
            if dialog.exec() == QDialog.Accepted:
                # Get field info from dialog
                field_info = dialog.getFieldInfo()
                
                # Remember the line item number for next time
                if field_info['type'] == 'line_item' and field_info['line_item_number']:
                    self.last_line_item_number = field_info['line_item_number']
                
                # Clean text for date fields
                cleaned_text = self.cleanTextForDateField(text, field_info['field'])
                if cleaned_text != text:
                    self.annotations[-1]['text'] = cleaned_text
                
                # Update the annotation with field info
                self.annotations[-1].update(field_info)
                
                # Emit signal that an annotation was added (with field info)
                self.annotationAdded.emit(self.annotations[-1])
            else:
                # Dialog was cancelled, remove the annotation
                self.undoLastAnnotation()
                return ""
            
        return text
    
    def getSelectedText(self):
        """Get text from the current selection"""
        if not self.selection_rect:
            return ""
            
        rect = self.selection_rect.rect()
        start_page_idx, start_page = self.findPageAt(rect.topLeft())
        end_page_idx, end_page = self.findPageAt(rect.bottomRight())
        
        if start_page_idx < 0 or end_page_idx < 0:
            return ""
            
        # Convert to PDF coordinates
        start_page_idx, start_pdf_pos = self.mapPDFPositionToPage(rect.topLeft())
        end_page_idx, end_pdf_pos = self.mapPDFPositionToPage(rect.bottomRight())
        
        text = ""
        
        # Handle single page or multiple pages
        if start_page_idx == end_page_idx:
            text = self.doc[start_page_idx].get_text(
                "text", 
                clip=fitz.Rect(start_pdf_pos[0], start_pdf_pos[1], end_pdf_pos[0], end_pdf_pos[1])
            )
        else:
            # Multiple pages
            for page_idx in range(start_page_idx, end_page_idx + 1):
                page = self.doc[page_idx]
                
                if page_idx == start_page_idx:
                    # First page - from start to bottom
                    clip_rect = fitz.Rect(start_pdf_pos[0], start_pdf_pos[1], page.rect.width, page.rect.height)
                elif page_idx == end_page_idx:
                    # Last page - from top to end position
                    clip_rect = fitz.Rect(0, 0, end_pdf_pos[0], end_pdf_pos[1])
                else:
                    # Middle pages - full page
                    clip_rect = page.rect
                    
                page_text = page.get_text("text", clip=clip_rect)
                text += page_text + "\n"
                
        return text
    
    def addAnnotation(self, rect=None):
        """Add annotation rectangle to current page"""
        if not self.doc or rect is None:
            # If no rect provided, we're in annotation mode and will create annotations
            # during mouse events
            return
            
        page_idx, page_info = self.findPageAt(rect.topLeft())
        if page_idx < 0:
            return
            
        # Convert to PDF coordinates
        page_idx, start_pos = self.mapPDFPositionToPage(rect.topLeft())
        _, end_pos = self.mapPDFPositionToPage(rect.bottomRight())
        
        pdf_rect = fitz.Rect(start_pos[0], start_pos[1], end_pos[0], end_pos[1])
        
        # Get text in the rectangle
        page = self.doc[page_idx]
        text = page.get_text("text", clip=pdf_rect)
        
        # Create annotation
        annot = page.add_highlight_annot(pdf_rect)
        
        # Create temporary annotation
        new_annotation = {
            'page': page_idx,
            'rect': pdf_rect,
            'rect_str': f"({pdf_rect.x0:.2f}, {pdf_rect.y0:.2f}, {pdf_rect.x1:.2f}, {pdf_rect.y1:.2f})",
            'text': text,
            'annot_id': len(self.annotations)  # Use a unique ID instead of a reference
        }
        
        # Store annotation temporarily
        self.annotations.append(new_annotation)
        
        # Re-render the page
        self.renderPage(page_idx)
        
        # Show field selection dialog
        dialog = AnnotationFieldDialog(self.parent(), self.last_line_item_number)
        if dialog.exec() == QDialog.Accepted:
            # Get field info from dialog
            field_info = dialog.getFieldInfo()
            
            # Remember the line item number for next time
            if field_info['type'] == 'line_item' and field_info['line_item_number']:
                self.last_line_item_number = field_info['line_item_number']
            
            # Clean text for date fields
            cleaned_text = self.cleanTextForDateField(text, field_info['field'])
            if cleaned_text != text:
                self.annotations[-1]['text'] = cleaned_text
            
            # Update the annotation with field info
            self.annotations[-1].update(field_info)
            
            # Emit signal that an annotation was added (with field info)
            self.annotationAdded.emit(self.annotations[-1])
        else:
            # Dialog was cancelled, remove the annotation
            self.undoLastAnnotation()
            return ""
        
        return text
    
    def removeAnnotation(self, page_idx, annot_idx=None):
        """Remove a specific annotation from a page"""
        if not self.doc or page_idx < 0 or page_idx >= self.page_count:
            return False
            
        page = self.doc[page_idx]
        
        try:
            # Get all annotations on the page and convert to a list (important!)
            annotations = list(page.annots())
            if annotations and len(annotations) > 0:
                if annot_idx is not None and 0 <= annot_idx < len(annotations):
                    # Remove the specific annotation if an index is provided
                    page.delete_annot(annotations[annot_idx])
                else:
                    # Default to removing the last annotation on the page
                    page.delete_annot(annotations[-1])
                
                # Re-render the page
                self.renderPage(page_idx)
                # Emit signal that an annotation was removed
                self.annotationRemoved.emit()
                return True
            else:
                print("No annotations found on page")
        except Exception as e:
            print(f"Error removing annotation: {str(e)}")
        return False
    
    def undoLastAnnotation(self):
        """Remove the last annotation added"""
        if not self.annotations:
            self.statusUpdated.emit("No annotations to undo")
            return False
            
        # Get the last annotation
        last_annot = self.annotations.pop()
        
        # Remove from the document
        page_idx = last_annot['page']
        
        result = self.removeAnnotation(page_idx)
        if result:
            self.statusUpdated.emit("Last annotation removed")
        else:
            self.statusUpdated.emit("Failed to remove annotation")
        return result
    
    def removeAnnotationByIndex(self, index):
        """Remove a specific annotation by its index in the annotations list"""
        if not self.annotations or index < 0 or index >= len(self.annotations):
            self.statusUpdated.emit("Invalid annotation index")
            return False
            
        # Get the annotation to remove
        annot_to_remove = self.annotations[index]
        page_idx = annot_to_remove['page']
        
        # Count which annotation on the page this is
        # Find all annotations on this page and their indices
        page_annotations = [(i, a) for i, a in enumerate(self.annotations) if a['page'] == page_idx]
        
        # Find the position of our annotation within that page's annotations
        annot_position = None
        for i, (list_idx, annot) in enumerate(page_annotations):
            if list_idx == index:
                annot_position = i
                break
        
        # Remove from the document using the position on the page
        result = self.removeAnnotation(page_idx, annot_position)
        
        if result:
            # Remove from the annotations list
            self.annotations.pop(index)
            self.statusUpdated.emit(f"Annotation {index} removed")
        else:
            self.statusUpdated.emit(f"Failed to remove annotation {index}")
            
        return result
    
    # Event handlers for mouse interaction
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming with Ctrl and scrolling otherwise"""
        if event.modifiers() & Qt.ControlModifier:
            # Zoom with Ctrl+Wheel
            delta = event.angleDelta().y()
            
            # Get the scene position under the mouse
            pos_before = self.mapToScene(event.position().toPoint())
            
            if delta > 0:
                self.zoomIn()
            else:
                self.zoomOut()
                
            # Update the view to keep the point under the mouse fixed
            pos_after = self.mapToScene(event.position().toPoint())
            delta_scene = pos_after - pos_before
            self.translate(delta_scene.x(), delta_scene.y())
            
            event.accept()
        else:
            # Normal scrolling
            super().wheelEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for panning, selection, and annotation"""
        if not self.doc:
            super().mousePressEvent(event)
            return
            
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            
            if event.modifiers() & Qt.ControlModifier:
                # Start annotation or selection with Ctrl+Left click
                self.is_selecting = True
                self.selection_start = scene_pos
                
                # Create a new selection rectangle if needed
                if self.selection_rect:
                    self.scene.removeItem(self.selection_rect)
                    
                self.selection_rect = self.scene.addRect(
                    QRectF(scene_pos, QSizeF(1, 1)),
                    QPen(QColor(0, 0, 255, 128), 1),
                    QBrush(QColor(0, 0, 255, 30))
                )
                
                event.accept()
            else:
                # Normal panning
                self.setDragMode(QGraphicsView.ScrollHandDrag)
                super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        if self.is_selecting and self.selection_rect:
            # Update selection rectangle
            current_pos = self.mapToScene(event.position().toPoint())
            
            rect = QRectF(
                min(self.selection_start.x(), current_pos.x()),
                min(self.selection_start.y(), current_pos.y()),
                abs(current_pos.x() - self.selection_start.x()),
                abs(current_pos.y() - self.selection_start.y())
            )
            
            self.selection_rect.setRect(rect)
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        if event.button() == Qt.LeftButton and self.is_selecting:
            end_pos = self.mapToScene(event.position().toPoint())
            
            # Find the page(s) where the selection starts and ends
            start_page_idx, start_page = self.findPageAt(self.selection_start)
            end_page_idx, end_page = self.findPageAt(end_pos)
            
            if start_page_idx >= 0 and end_page_idx >= 0:
                # Convert to PDF coordinates
                start_page_idx, start_pdf_pos = self.mapPDFPositionToPage(self.selection_start)
                end_page_idx, end_pdf_pos = self.mapPDFPositionToPage(end_pos)
                
                selected_text = ""
                
                # Handle selection across multiple pages
                if start_page_idx == end_page_idx:
                    # Selection within the same page
                    selected_text = self.selectTextInRegion(start_page_idx, start_pdf_pos, end_pdf_pos)
                else:
                    # Selection across multiple pages - process each page
                    for page_idx in range(start_page_idx, end_page_idx + 1):
                        page = self.doc[page_idx]
                        
                        if page_idx == start_page_idx:
                            # First page: from start to bottom
                            page_rect = fitz.Rect(start_pdf_pos[0], start_pdf_pos[1], page.rect.width, page.rect.height)
                        elif page_idx == end_page_idx:
                            # Last page: from top to end
                            page_rect = fitz.Rect(0, 0, end_pdf_pos[0], end_pdf_pos[1])
                        else:
                            # Middle pages: entire page
                            page_rect = page.rect
                            
                        # Select text on this page
                        text = page.get_text("text", clip=page_rect)
                        selected_text += text + "\n"
                        
                        # Add highlight annotation
                        highlight = page.add_highlight_annot(page_rect)
                        
                        # Add temporary annotation
                        new_annotation = {
                            'page': page_idx,
                            'rect': page_rect,
                            'rect_str': f"({page_rect.x0:.2f}, {page_rect.y0:.2f}, {page_rect.x1:.2f}, {page_rect.y1:.2f})",
                            'text': text,
                            'annot_id': len(self.annotations)  # Use a unique ID instead of a reference
                        }
                        
                        # Store annotation temporarily
                        self.annotations.append(new_annotation)
                        
                        # Re-render the page
                        self.renderPage(page_idx)
                    
                    # Show field selection dialog for multi-page annotation
                    dialog = AnnotationFieldDialog(self.parent(), self.last_line_item_number)
                    if dialog.exec() == QDialog.Accepted:
                        # Get field info from dialog
                        field_info = dialog.getFieldInfo()
                        
                        # Remember the line item number for next time
                        if field_info['type'] == 'line_item' and field_info['line_item_number']:
                            self.last_line_item_number = field_info['line_item_number']
                        
                        # Update all the annotations with the same field info
                        for i in range(start_page_idx, end_page_idx + 1):
                            annot_idx = len(self.annotations) - (end_page_idx - start_page_idx + 1) + (i - start_page_idx)
                            if 0 <= annot_idx < len(self.annotations):
                                # Clean text for date fields if needed
                                if field_info['field'] in ['rfq_date', 'due_date', 'requested_delivery_date']:
                                    cleaned_text = self.cleanTextForDateField(self.annotations[annot_idx]['text'], field_info['field'])
                                    self.annotations[annot_idx]['text'] = cleaned_text
                                
                                self.annotations[annot_idx].update(field_info)
                        
                        # Emit signal that an annotation was added
                        self.annotationAdded.emit(self.annotations[-1])
                    else:
                        # Dialog was cancelled, remove all the added annotations
                        for i in range(end_page_idx - start_page_idx + 1):
                            self.undoLastAnnotation()
                        return ""
                
                # Emit a signal to update UI with the selected text
                self.textSelected.emit(selected_text)
            
            # Clean up
            self.is_selecting = False
            if self.selection_rect:
                self.scene.removeItem(self.selection_rect)
                self.selection_rect = None
                
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            self.setDragMode(QGraphicsView.NoDrag)
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        # We'll handle Ctrl+Z at the main window level instead
        super().keyPressEvent(event)


class PDFViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize the database
        self.db = AnnotationDB()
        
        # Current file path
        self.current_file = None
        
        self.initUI()
        
        # Enable key press events for the main window
        self.setFocusPolicy(Qt.StrongFocus)
        
    def initUI(self):
        # Set window properties
        self.setWindowTitle("PDF Data Viewer")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create toolbar with controls
        self.createToolbar()
        
        # Create splitter for the two panels
        self.splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.splitter)
        
        # Left panel for PDF viewing
        self.pdf_viewer = PDFViewer()
        
        # Right panel for extracted data
        self.data_panel = QScrollArea()
        self.data_panel.setWidgetResizable(True)
        
        # Data content widget
        self.data_content = QWidget()
        self.data_layout = QVBoxLayout(self.data_content)
        self.data_label = QLabel("Data extracted from PDF will appear here")
        self.data_layout.addWidget(self.data_label)
        
        # Create section for selected text
        self.selected_text_label = QLabel("Selected Text:")
        self.data_layout.addWidget(self.selected_text_label)
        
        self.selected_text_display = QLabel("No text selected")
        self.selected_text_display.setWordWrap(True)
        self.selected_text_display.setFrameShape(QLabel.Panel)
        self.selected_text_display.setFrameShadow(QLabel.Sunken)
        self.selected_text_display.setMinimumHeight(100)
        self.data_layout.addWidget(self.selected_text_display)
        
        # Create section for annotations
        self.annotations_label = QLabel("Annotations:")
        self.data_layout.addWidget(self.annotations_label)
        
        self.annotations_list = QTableWidget()
        # Updated columns - removed Rect column
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
        
        # Add Export button to the data panel
        self.export_button = QPushButton("Export Annotations to CSV")
        self.export_button.clicked.connect(self.exportAnnotationsToCSV)
        self.data_layout.addWidget(self.export_button)
        
        self.data_panel.setWidget(self.data_content)
        
        # Connect signals
        self.pdf_viewer.textSelected.connect(self.onTextSelected)
        self.pdf_viewer.annotationAdded.connect(self.onAnnotationAdded)
        self.pdf_viewer.annotationRemoved.connect(self.updateAnnotationsList)
        self.pdf_viewer.statusUpdated.connect(self.updateStatus)  # Connect to new status signal
        
        # Add panels to splitter with 2:1 ratio
        self.splitter.addWidget(self.pdf_viewer)
        self.splitter.addWidget(self.data_panel)
        self.splitter.setSizes([2 * self.width() // 3, self.width() // 3])
        
        # Create menu bar
        self.createMenuBar()
        
        # Set up drag and drop
        self.setAcceptDrops(True)
        
        # Set focus policy to ensure keyboard events are received
        self.pdf_viewer.setFocusPolicy(Qt.StrongFocus)
        
        # Set as the central widget to receive key events
        self.pdf_viewer.setFocus()
    
    def createMenuBar(self):
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
        
        # Undo action - don't set shortcut in the QAction to avoid ambiguity
        self.undo_action = QAction("&Undo Annotation", self)
        # We'll handle the shortcut directly in keyPressEvent
        self.undo_action.triggered.connect(self.undoLastAnnotation)
        edit_menu.addAction(self.undo_action)
    
    def createToolbar(self):
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
        
        # Add zoom percentage label
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
        
        # Undo annotation button - no shortcut here to avoid ambiguity
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
        
        # Add status bar
        self.statusBar().showMessage("Ready. Use Ctrl+Left click to select text/create annotations")
    
    def updateStatus(self, message):
        """Update status bar with the message from PDF viewer"""
        self.statusBar().showMessage(message)
    
    def openFile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF File", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.loadPDF(file_path)
    
    def loadPDF(self, file_path):
        """Load a PDF file and display it"""
        # Show loading indicator
        self.statusBar().showMessage(f"Loading {os.path.basename(file_path)}...")
        QApplication.processEvents()  # Allow UI to update
        
        if self.pdf_viewer.loadDocument(file_path):
            # Store the current file path
            self.current_file = file_path
            
            self.statusBar().showMessage(f"Loaded: {os.path.basename(file_path)}")
            
            # Extract and display info from the PDF
            if self.pdf_viewer.doc:
                self.updateDataPanel()
                
                # Ensure proper initial zoom
                if not self.pdf_viewer.initial_zoom_set:
                    self.pdf_viewer.resetView()
                    
                # Set zoom slider to match current zoom
                self.zoom_slider.setValue(int(self.pdf_viewer.zoom_factor * 100))
                self.zoom_label.setText(f"{int(self.pdf_viewer.zoom_factor * 100)}%")
                
                # Load existing annotations from database AFTER initializing the view
                # This ensures the PDF is fully loaded before annotations are added
                self.loadAnnotationsFromDatabase()
                
                # Make sure to update the annotations list, even if there are no annotations
                self.updateAnnotationsList()
        else:
            self.statusBar().showMessage(f"Failed to load PDF: {os.path.basename(file_path)}")
    
    def loadAnnotationsFromDatabase(self):
        """Load annotations for the current PDF from the database"""
        if not self.current_file or not self.pdf_viewer.doc:
            return
        
        # Make sure the annotations list is cleared first (even if no annotations found)
        self.pdf_viewer.annotations = []
        
        # Get annotations from database (using just filename matching)
        db_annotations = self.db.get_annotations_for_file(self.current_file)
        
        if db_annotations:
            print(f"Found {len(db_annotations)} annotations in database for {os.path.basename(self.current_file)}")
            
            # Add each annotation from the database
            for db_annot in db_annotations:
                # Convert rect tuple to fitz.Rect
                rect_x0, rect_y0, rect_x1, rect_y1 = db_annot['rect']
                rect = fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1)
                
                # Create annotation in same format as viewer expects
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
                
                # Add to the viewer's annotations list
                self.pdf_viewer.annotations.append(annot)
                
                # Add highlights to the PDF
                page = self.pdf_viewer.doc[db_annot['page']]
                page.add_highlight_annot(rect)
                
                # Render the page to show the highlight
                self.pdf_viewer.renderPage(db_annot['page'])
            
            # Force update the annotations list in the UI
            QApplication.processEvents()  # Process any pending events
            self.updateAnnotationsList()
            self.statusBar().showMessage(f"Loaded {len(db_annotations)} annotations from database")
        else:
            print(f"No annotations found in database for {os.path.basename(self.current_file)}")
            # Make sure to update the annotations list even if no annotations were found
            self.updateAnnotationsList()
            self.statusBar().showMessage(f"No annotations found for {os.path.basename(self.current_file)}")
    
    def updateDataPanel(self):
        """Update the data panel with information from the PDF"""
        if not self.pdf_viewer.doc:
            return
            
        # Create a basic information display
        info_text = f"PDF Information:\n"
        info_text += f"Pages: {self.pdf_viewer.page_count}\n"
        
        # Get document metadata if available
        metadata = self.pdf_viewer.doc.metadata
        if metadata:
            if metadata.get('title'):
                info_text += f"Title: {metadata.get('title')}\n"
            if metadata.get('author'):
                info_text += f"Author: {metadata.get('author')}\n"
            if metadata.get('subject'):
                info_text += f"Subject: {metadata.get('subject')}\n"
                
        # Update the information label
        self.data_label.setText(info_text)
        
        # Clear the selected text display
        self.selected_text_display.setText("No text selected")
        
        # Clear the annotations list
        self.annotations_list.setRowCount(0)
    
    def onTextSelected(self, text):
        """Handle text selection event from the PDF viewer"""
        if text:
            self.selected_text_display.setText(text)
    
    def onAnnotationAdded(self, annotation):
        """Handle annotation added event with field information"""
        date_fields = ['rfq_date', 'due_date', 'requested_delivery_date']
        
        # Check if this is a date field and try to standardize it
        if annotation.get('field') in date_fields:
            # Try to standardize the date
            standardized_date = standardize_date(annotation['text'])
            
            # If standardization failed, show an alert to the user
            if not standardized_date:
                QMessageBox.warning(
                    self,
                    "Date Standardization Failed",
                    f"Could not standardize the date: '{annotation['text']}'\n\n"
                    "The text you selected might not be a valid date format.\n"
                    "You may want to undo this annotation and try again with a different selection."
                )
            else:
                # Store the standardized date in the annotation
                annotation['standardized_date'] = standardized_date
        
        # Add to database if we have a file loaded
        if self.current_file:
            annotation_id = self.db.add_annotation(self.current_file, annotation)
            
            # Store the database ID with the annotation
            if annotation_id:
                # Find the annotation in our list (should be the last one)
                if annotation == self.pdf_viewer.annotations[-1]:
                    self.pdf_viewer.annotations[-1]['id'] = annotation_id
        
        # Update the UI
        self.updateAnnotationsList()
    
    def updateAnnotationsList(self):
        """Update the annotations list in the data panel without showing Rect info"""
        if not self.pdf_viewer.doc:
            return
            
        # Clear the list
        self.annotations_list.setRowCount(0)
        
        # Print debug info
        print(f"Updating annotations list with {len(self.pdf_viewer.annotations)} annotations")
        
        # Add each annotation to the list
        for i, annot in enumerate(self.pdf_viewer.annotations):
            # Skip annotations that don't have required fields
            if 'page' not in annot or 'text' not in annot:
                print(f"Skipping invalid annotation: {annot}")
                continue
                
            row_position = self.annotations_list.rowCount()
            self.annotations_list.insertRow(row_position)
            
            # Add page number
            page_item = QTableWidgetItem(str(annot['page'] + 1))  # +1 for human-readable page numbers
            self.annotations_list.setItem(row_position, 0, page_item)
            
            # Add annotation type
            type_item = QTableWidgetItem(annot.get('type', ''))
            self.annotations_list.setItem(row_position, 1, type_item)
            
            # Add line item number
            line_item_num = QTableWidgetItem(annot.get('line_item_number', ''))
            self.annotations_list.setItem(row_position, 2, line_item_num)
            
            # Add field name
            field_item = QTableWidgetItem(annot.get('field', ''))
            self.annotations_list.setItem(row_position, 3, field_item)
            
            # Determine text to display - use standardized date if available for date fields
            display_text = annot['text']
            date_fields = ['rfq_date', 'due_date', 'requested_delivery_date']
            
            if annot.get('field') in date_fields:
                # For date fields, try to get standardized date
                if 'standardized_date' in annot and annot['standardized_date']:
                    display_text = f"{annot['text']} → {annot['standardized_date']}"
                else:
                    # Try to standardize it now if it wasn't already
                    std_date = standardize_date(annot['text'])
                    if std_date:
                        display_text = f"{annot['text']} → {std_date}"
                        # Store the standardized date in the annotation
                        annot['standardized_date'] = std_date
            
            # Add annotation text (truncated if too long)
            if len(display_text) > 50:
                display_text = display_text[:47] + "..."
            text_item = QTableWidgetItem(display_text)
            self.annotations_list.setItem(row_position, 4, text_item)
            
            # Create a stable reference to the current index 
            current_index = i  # Capture current value of i
            
            # Add delete button
            delete_button = QPushButton("[x]")
            delete_button.setFixedWidth(30)
            # Create a function that captures the current index
            delete_func = lambda checked, idx=current_index: self.onDeleteAnnotation(idx)
            delete_button.clicked.connect(delete_func)
            self.annotations_list.setCellWidget(row_position, 5, delete_button)
        
        # Make sure all columns are properly sized
        self.annotations_list.resizeColumnsToContents()
        
        # Force UI update
        QApplication.processEvents()
    
    def onDeleteAnnotation(self, index):
        """Handle delete button click for a specific annotation"""
        if not self.pdf_viewer.annotations or index >= len(self.pdf_viewer.annotations):
            self.statusBar().showMessage(f"Invalid annotation index: {index}")
            return
        
        # Get the annotation to delete
        annotation = self.pdf_viewer.annotations[index]
        
        # Print information for debugging
        print(f"Deleting annotation: index={index}, id={annotation.get('id', 'unknown')}, page={annotation.get('page', 'unknown')}")
        
        # First remove from the PDF
        if self.pdf_viewer.removeAnnotationByIndex(index):
            # Then remove from database if we have an ID
            if 'id' in annotation:
                success = self.db.remove_annotation(annotation['id'])
                if success:
                    self.statusBar().showMessage(f"Annotation {index} deleted")
                else:
                    self.statusBar().showMessage(f"Warning: Annotation removed from PDF but failed to delete from database")
            else:
                self.statusBar().showMessage(f"Annotation {index} deleted (no database ID)")
                
            # Update the UI
            self.updateAnnotationsList()
        else:
            self.statusBar().showMessage(f"Failed to remove annotation {index} from PDF")
    
    def exportAnnotationsToCSV(self):
        """Export annotations for the current PDF to CSV"""
        if not self.current_file:
            QMessageBox.warning(self, "Export Error", "No PDF file is currently loaded.")
            return
        
        # Get filename for export
        file_name = os.path.basename(self.current_file).replace(".pdf", "_annotations.csv")
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Export Annotations to CSV", file_name, "CSV Files (*.csv)"
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
    
    # PDF control methods
    def zoomIn(self):
        self.pdf_viewer.zoomIn()
        # Update slider to match
        self.zoom_slider.setValue(int(self.pdf_viewer.zoom_factor * 100))
        self.zoom_label.setText(f"{int(self.pdf_viewer.zoom_factor * 100)}%")
    
    def zoomOut(self):
        self.pdf_viewer.zoomOut()
        # Update slider to match
        self.zoom_slider.setValue(int(self.pdf_viewer.zoom_factor * 100))
        self.zoom_label.setText(f"{int(self.pdf_viewer.zoom_factor * 100)}%")
    
    def previousPage(self):
        self.pdf_viewer.goToPrevPage()
    
    def nextPage(self):
        self.pdf_viewer.goToNextPage()
    
    def addAnnotation(self):
        # Toggle annotation mode
        self.pdf_viewer.is_annotating = not self.pdf_viewer.is_annotating
        if self.pdf_viewer.is_annotating:
            self.statusBar().showMessage("Annotation mode: ON (Ctrl+Left click to create annotation)")
        else:
            self.statusBar().showMessage("Annotation mode: OFF")
    
    def undoLastAnnotation(self):
        """Remove the last annotation"""
        print("Attempting to undo annotation")
        if not self.pdf_viewer.doc or not self.pdf_viewer.annotations:
            print("No annotations to undo")
            self.statusBar().showMessage("No annotations to undo")
            return False
            
        # Get the last annotation
        last_annot = self.pdf_viewer.annotations.pop()
        
        # Use the PDFViewer's method to remove the last annotation
        if self.pdf_viewer.removeAnnotation(last_annot['page']):
            # Remove from database if it has an ID
            if 'id' in last_annot:
                success = self.db.remove_annotation(last_annot['id'])
                if not success:
                    print(f"Warning: Failed to remove annotation ID {last_annot.get('id')} from database")
            
            # Update the annotations list
            self.updateAnnotationsList()
            self.statusBar().showMessage("Last annotation removed")
            return True
        else:
            # If we failed to remove from PDF, put the annotation back in the list
            self.pdf_viewer.annotations.append(last_annot)
            self.statusBar().showMessage("Failed to remove annotation")
            return False
    
    def onZoomSliderChange(self, value):
        """Handle zoom slider change"""
        new_factor = value / 100.0
        if self.pdf_viewer.zoom_factor != new_factor:
            # Calculate the ratio for scaling
            ratio = new_factor / self.pdf_viewer.zoom_factor
            
            # Update zoom factor
            self.pdf_viewer.zoom_factor = new_factor
            
            # Update zoom label
            self.zoom_label.setText(f"{value}%")
            
            # Apply scaling - reset transform first to avoid cumulative errors
            self.pdf_viewer.resetTransform()
            self.pdf_viewer.scale(new_factor, new_factor)
            
            # Update status
            self.statusBar().showMessage(f"Zoom: {value}%")
    
    def onQualityChange(self, index):
        """Handle render quality change"""
        quality_map = {0: "standard", 1: "high", 2: "very high"}
        quality = quality_map.get(index, "high")
        
        if quality != self.pdf_viewer.render_quality:
            self.pdf_viewer.render_quality = quality
            
            # Update DPI based on quality
            if quality == "standard":
                self.pdf_viewer.dpi = 200  # Increased from 150
            elif quality == "high":
                self.pdf_viewer.dpi = 350  # Increased from 300
            else:  # very high
                self.pdf_viewer.dpi = 600
                
            # Save current zoom factor
            current_zoom = self.pdf_viewer.zoom_factor
            
            # Remember the center point to restore the view position
            center_point = self.pdf_viewer.mapToScene(
                self.pdf_viewer.viewport().rect().center())
            
            # Reload current document if one is loaded
            if self.pdf_viewer.doc:
                current_file = self.pdf_viewer.doc.name
                # Show status message
                self.statusBar().showMessage(f"Applying {quality} quality rendering...")
                
                # Reload the document
                self.loadPDF(current_file)
                
                # Restore zoom and center position
                self.pdf_viewer.zoom_factor = current_zoom
                self.pdf_viewer.resetTransform()
                self.pdf_viewer.scale(current_zoom, current_zoom)
                
                # Update zoom slider
                self.zoom_slider.setValue(int(current_zoom * 100))
                
                self.statusBar().showMessage(f"Quality set to {quality}, zoom: {int(current_zoom * 100)}%")
    
    # Event handlers
    def keyPressEvent(self, event):
        """Handle key press events at the main window level"""
        # Check for Ctrl+Z
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            # Handle Ctrl+Z directly here
            print("Ctrl+Z detected in main window")
            result = self.undoLastAnnotation()
            print(f"Undo result: {result}")
            event.accept()
        else:
            # For all other key events, pass to parent implementation
            super().keyPressEvent(event)
    
    # Drag and drop event handlers
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.loadPDF(file_path)
                
    def resizeEvent(self, event):
        """Handle resize events to maintain splitter proportions"""
        super().resizeEvent(event)
        # Re-apply the 2:1 ratio when resizing
        if hasattr(self, 'splitter'):
            self.splitter.setSizes([2 * self.width() // 3, self.width() // 3])
            
        # Refresh the PDF view if loaded to maintain proper zoom
        if hasattr(self, 'pdf_viewer') and self.pdf_viewer.doc and not self.pdf_viewer.initial_zoom_set:
            # This will help ensure good initial sizing on first load
            self.pdf_viewer.resetView()
    
    def closeEvent(self, event):
        """Handle window close event to properly close the database"""
        if hasattr(self, 'db'):
            self.db.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = PDFViewerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()