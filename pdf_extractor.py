import sys
import os
import fitz  # PyMuPDF
from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, QVBoxLayout, 
                              QHBoxLayout, QWidget, QScrollArea, QToolBar, 
                              QFileDialog, QLabel, QPushButton, QGraphicsView,
                              QGraphicsScene, QGraphicsPixmapItem, QTableWidget,
                              QTableWidgetItem, QSlider, QComboBox, QMessageBox)
from PySide6.QtCore import Qt, QRectF, Signal, QSize, QPoint, QPointF, QSizeF, QEvent
from PySide6.QtGui import (QAction, QIcon, QKeySequence, QPixmap, QImage, 
                          QCursor, QTransform, QColor, QPen, QBrush, QPainter)


class PDFViewer(QGraphicsView):
    """Custom widget for displaying and interacting with PDF pages"""
    # Signals
    textSelected = Signal(str)
    annotationAdded = Signal()
    annotationRemoved = Signal()
    statusUpdated = Signal(str)  # New signal for status updates
    
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
                self.annotations = []
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
        
        # Clear scene
        self.scene.clear()
        
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
                target_width_ratio = 0.9
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
        
        # Update the stored pixmap and the graphics item
        self.pages[page_idx]['pixmap'] = pixmap
        self.page_items[page_idx].setPixmap(pixmap)
    
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
            
            # Store annotation info
            self.annotations.append({
                'page': page_idx,
                'rect': rect,
                'text': text,
                'annot_id': len(self.annotations)  # Use a unique ID instead of a reference
            })
            
            # Re-render the page to show the highlight
            self.renderPage(page_idx)
            
            # Emit signal that an annotation was added
            self.annotationAdded.emit()
            
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
        
        # Store annotation
        self.annotations.append({
            'page': page_idx,
            'rect': pdf_rect,
            'text': text,
            'annot_id': len(self.annotations)  # Use a unique ID instead of a reference
        })
        
        # Re-render the page
        self.renderPage(page_idx)
        
        # Emit signal that an annotation was added
        self.annotationAdded.emit()
        
        return text
    
    def removeAnnotation(self, page_idx, annot_id=None):
        """Remove a specific annotation from a page"""
        if not self.doc or page_idx < 0 or page_idx >= self.page_count:
            return False
            
        page = self.doc[page_idx]
        
        try:
            # Get all annotations on the page and convert to a list (important!)
            annotations = list(page.annots())
            if annotations and len(annotations) > 0:
                # Always remove the last annotation on the page
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
                        self.annotations.append({
                            'page': page_idx,
                            'rect': page_rect,
                            'text': text,
                            'annot_id': len(self.annotations)  # Use a unique ID instead of a reference
                        })
                        
                        # Re-render the page
                        self.renderPage(page_idx)
                
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
        self.initUI()
        
        # Enable key press events for the main window
        self.setFocusPolicy(Qt.StrongFocus)
        
    def initUI(self):
        # Set window properties
        self.setWindowTitle("PDF Viewer")
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
        self.annotations_list.setColumnCount(2)
        self.annotations_list.setHorizontalHeaderLabels(["Page", "Text"])
        self.annotations_list.horizontalHeader().setStretchLastSection(True)
        self.data_layout.addWidget(self.annotations_list)
        
        self.data_panel.setWidget(self.data_content)
        
        # Connect signals
        self.pdf_viewer.textSelected.connect(self.onTextSelected)
        self.pdf_viewer.annotationAdded.connect(self.updateAnnotationsList)
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
        
        # We'll rely on keyPressEvent instead of event filter
    
    def createMenuBar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Open action
        open_action = QAction("&Open", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.openFile)
        file_menu.addAction(open_action)
        
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
        QApplication.processEvents()  # Update UI immediately
        
        if self.pdf_viewer.loadDocument(file_path):
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
        else:
            self.statusBar().showMessage(f"Failed to load PDF: {os.path.basename(file_path)}")
    
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
                
        # Display the text from the current page
        current_page_text = self.pdf_viewer.getCurrentPageText()
        
        # Update the information label
        self.data_label.setText(info_text)
        
        # Reset the annotations list
        self.annotations_list.setRowCount(0)
        
        # Clear the selected text display
        self.selected_text_display.setText("No text selected")
    
    def onTextSelected(self, text):
        """Handle text selection event from the PDF viewer"""
        if text:
            self.selected_text_display.setText(text)
            
            # Update annotations list
            self.updateAnnotationsList()
    
    def updateAnnotationsList(self):
        """Update the annotations list in the data panel"""
        if not self.pdf_viewer.doc:
            return
            
        # Clear the list
        self.annotations_list.setRowCount(0)
        
        # Add each annotation to the list
        for i, annot in enumerate(self.pdf_viewer.annotations):
            row_position = self.annotations_list.rowCount()
            self.annotations_list.insertRow(row_position)
            
            # Add page number
            page_item = QTableWidgetItem(str(annot['page'] + 1))  # +1 for human-readable page numbers
            self.annotations_list.setItem(row_position, 0, page_item)
            
            # Add annotation text (truncated if too long)
            text = annot['text']
            if len(text) > 50:
                text = text[:47] + "..."
            text_item = QTableWidgetItem(text)
            self.annotations_list.setItem(row_position, 1, text_item)
    
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
        print(f"Last annotation on page: {last_annot['page']}")
        
        # Use the PDFViewer's method to remove the last annotation
        if self.pdf_viewer.removeAnnotation(last_annot['page']):
            # Update the annotations list
            self.updateAnnotationsList()
            self.statusBar().showMessage("Last annotation removed")
            return True
        else:
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
        
    # We're not using eventFilter anymore, relying on keyPressEvent instead
    
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


def main():
    app = QApplication(sys.argv)
    window = PDFViewerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()