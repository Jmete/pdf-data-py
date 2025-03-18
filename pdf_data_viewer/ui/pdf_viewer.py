"""PDF viewer widget for displaying and interacting with PDF documents."""

from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, 
                              QApplication)
from PySide6.QtCore import Qt, QPointF, QRectF, QSizeF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QTransform

import fitz  # PyMuPDF
import time
from ..core.pdf_handler import PDFDocument
from ..config import DEFAULT_ZOOM_FACTOR, MIN_ZOOM, MAX_ZOOM, PAGE_GAP

class PDFViewer(QGraphicsView):
    """Custom widget for displaying and interacting with PDF pages."""
    
    # Signals
    textSelected = Signal(str)
    annotationAdded = Signal(dict)  # Signal when annotation is added
    annotationRemoved = Signal()    # Signal when annotation is removed
    statusUpdated = Signal(str)     # Signal for status updates
    
    def __init__(self, parent=None):
        """
        Initialize the PDF viewer.
        
        Args:
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Initialize PDF document handler
        self.pdf_doc = PDFDocument()
        
        # Page rendering properties
        self.pages = []  # Store rendered page info
        self.page_items = []  # Store QGraphicsItems for each page
        self.current_page = 0
        
        # View properties
        self.zoom_factor = DEFAULT_ZOOM_FACTOR
        self.min_zoom = MIN_ZOOM
        self.max_zoom = MAX_ZOOM
        self.initial_zoom_set = False
        
        # Interaction flags
        self.is_panning = False
        self.is_selecting = False
        self.is_annotating = False
        self.selection_start = QPointF()
        self.selection_rect = None
        
        # Configure view
        self.setRenderHint(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Add placeholder text
        self.placeholder = self.scene.addText("Drag and drop a PDF file here or use File > Open")
        self.placeholder.setPos(10, 10)
    
    def loadDocument(self, file_path):
        """
        Load a PDF document and render its pages.
        
        Args:
            file_path (str): Path to the PDF file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.pdf_doc.load(file_path):
            if self.pdf_doc.page_count > 0:
                self.scene.clear()
                self.pages = []
                self.page_items = []
                self.current_page = 0
                
                # Render all pages
                self.renderAllPages()
                
                return True
        return False
    
    def renderAllPages(self):
        """Render all pages of the PDF as a vertical stack."""
        if not self.pdf_doc.doc:
            return
        
        # Clear scene and reset page arrays
        self.scene.clear()
        self.pages = []
        self.page_items = []
        
        # Track total height for positioning
        total_height = 0
        
        # Display a status message
        self.scene.addText("Rendering pages, please wait...").setPos(10, 10)
        QApplication.processEvents()  # Allow UI to update
        
        for page_num in range(self.pdf_doc.page_count):
            # Render page with current settings
            pixmap, page_info = self.pdf_doc.render_page(page_num)
            
            if pixmap:
                # Create pixmap item and add to scene
                pixmap_item = QGraphicsPixmapItem(pixmap)
                pixmap_item.setPos(0, total_height)
                pixmap_item.setData(0, page_num)  # Store page number
                
                # Make pixmap selectable
                pixmap_item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)
                
                # Add to scene
                self.scene.addItem(pixmap_item)
                
                # Store page info
                page_info['rect'] = QRectF(0, total_height, pixmap.width(), pixmap.height())
                self.pages.append(page_info)
                self.page_items.append(pixmap_item)
                
                # Update height for next page
                total_height += pixmap.height() + PAGE_GAP
                
                # Allow UI to update periodically
                if page_num % 5 == 0:
                    QApplication.processEvents()
        
        # Set scene rect to contain all items
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        
        # Reset view to show the whole document
        self.resetView()
    
    def renderPage(self, page_num):
        """
        Re-render a specific page (e.g., after adding annotations).
        
        Args:
            page_num (int): Page number to render
        """
        if not self.pdf_doc.doc or page_num < 0 or page_num >= self.pdf_doc.page_count:
            return
            
        # Render the page
        pixmap, page_info = self.pdf_doc.render_page(page_num)
        
        if pixmap and page_num < len(self.pages) and page_num < len(self.page_items):
            # Update the stored pixmap
            self.pages[page_num]['pixmap'] = pixmap
            
            # Update the graphics item
            try:
                self.page_items[page_num].setPixmap(pixmap)
            except (RuntimeError, NameError):
                # Handle case where item was deleted
                pos_y = 0
                if page_num > 0:
                    # Calculate position based on previous pages
                    for i in range(page_num):
                        pos_y += self.pages[i]['pixmap'].height() + PAGE_GAP
                
                # Create and add new pixmap item
                new_pixmap_item = QGraphicsPixmapItem(pixmap)
                new_pixmap_item.setPos(0, pos_y)
                new_pixmap_item.setData(0, page_num)
                new_pixmap_item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)
                
                self.scene.addItem(new_pixmap_item)
                self.page_items[page_num] = new_pixmap_item
    
    def resetView(self):
        """Reset view to show the document with appropriate zoom."""
        scene_rect = self.scene.itemsBoundingRect()
        
        # Calculate initial zoom if needed
        if not self.initial_zoom_set and self.pdf_doc.page_count > 0 and len(self.pages) > 0:
            first_page_width = self.pages[0]['pixmap'].width()
            view_width = self.viewport().width()
            
            if first_page_width > 0 and view_width > 0:
                # Target 90% of view width for the document
                target_width_ratio = 0.9
                calculated_zoom = (view_width * target_width_ratio) / first_page_width
                
                # Keep zoom within reasonable bounds
                self.zoom_factor = max(min(calculated_zoom, 2.0), 1.0)
                self.initial_zoom_set = True
        
        # Apply the zoom
        self.resetTransform()
        self.scale(self.zoom_factor, self.zoom_factor)
        
        # Center the content
        self.centerOn(scene_rect.center())
        
        # Emit status update
        self.statusUpdated.emit(f"Zoom: {int(self.zoom_factor * 100)}%")
    
    def zoomIn(self):
        """Zoom in the view."""
        if self.zoom_factor < self.max_zoom:
            factor = 1.25
            self.zoom_factor = min(self.zoom_factor * factor, self.max_zoom)
            
            # Apply scaling
            self.resetTransform()
            self.scale(self.zoom_factor, self.zoom_factor)
                
            # Emit status update
            self.statusUpdated.emit(f"Zoom: {int(self.zoom_factor * 100)}%")
    
    def zoomOut(self):
        """Zoom out the view."""
        if self.zoom_factor > self.min_zoom:
            factor = 1.25
            self.zoom_factor = max(self.zoom_factor / factor, self.min_zoom)
            
            # Apply scaling
            self.resetTransform()
            self.scale(self.zoom_factor, self.zoom_factor)
                
            # Emit status update
            self.statusUpdated.emit(f"Zoom: {int(self.zoom_factor * 100)}%")
    
    def findPageAt(self, scene_pos):
        """
        Find which page is at the given scene position.
        
        Args:
            scene_pos (QPointF): Position in scene coordinates
            
        Returns:
            tuple: (page_index, page_info) or (-1, None) if no page found
        """
        for i, page in enumerate(self.pages):
            if page['rect'].contains(scene_pos):
                return i, page
        return -1, None
    
    def mapPDFPositionToPage(self, scene_pos):
        """
        Map a scene position to PDF coordinates on the corresponding page.
        
        Args:
            scene_pos (QPointF): Position in scene coordinates
            
        Returns:
            tuple: (page_index, (pdf_x, pdf_y)) or (-1, None) if not on a page
        """
        page_idx, page = self.findPageAt(scene_pos)
        if page_idx >= 0:
            # Calculate position relative to the page
            page_pos = scene_pos - QPointF(page['rect'].left(), page['rect'].top())
            # Scale to PDF coordinates based on zoom and DPI
            pdf_x = page_pos.x() * 72 / self.pdf_doc.dpi
            pdf_y = page_pos.y() * 72 / self.pdf_doc.dpi
            return page_idx, (pdf_x, pdf_y)
        return -1, None
    
    def getSelectedText(self):
        """
        Get text from the current selection.
        
        Returns:
            str: Selected text
        """
        if not self.selection_rect:
            return ""
            
        rect = self.selection_rect.rect()
        
        # Find pages covered by selection
        start_page_idx, _ = self.findPageAt(rect.topLeft())
        end_page_idx, _ = self.findPageAt(rect.bottomRight())
        
        if start_page_idx < 0 or end_page_idx < 0:
            print("Selection doesn't cover any pages")
            return ""
            
        # Convert to PDF coordinates
        start_page_idx, start_pdf_pos = self.mapPDFPositionToPage(rect.topLeft())
        end_page_idx, end_pdf_pos = self.mapPDFPositionToPage(rect.bottomRight())
        
        print(f"Selection spans pages {start_page_idx} to {end_page_idx}")
        
        text = ""
        
        # Handle selection across pages
        if start_page_idx == end_page_idx:
            # Single page selection
            pdf_rect = fitz.Rect(start_pdf_pos[0], start_pdf_pos[1], end_pdf_pos[0], end_pdf_pos[1])
            text = self.pdf_doc.get_text_in_rect(start_page_idx, pdf_rect)
            print(f"Single page text: '{text}'")
        else:
            # Multi-page selection
            for page_idx in range(start_page_idx, end_page_idx + 1):
                page = self.pdf_doc.doc[page_idx]
                
                if page_idx == start_page_idx:
                    # First page - from start to bottom
                    clip_rect = fitz.Rect(start_pdf_pos[0], start_pdf_pos[1], page.rect.width, page.rect.height)
                elif page_idx == end_page_idx:
                    # Last page - from top to end position
                    clip_rect = fitz.Rect(0, 0, end_pdf_pos[0], end_pdf_pos[1])
                else:
                    # Middle pages - full page
                    clip_rect = page.rect
                    
                page_text = self.pdf_doc.get_text_in_rect(page_idx, clip_rect)
                print(f"Page {page_idx} text: '{page_text}'")
                text += page_text + "\n"
        
        return text
    
    # Navigation methods
    def goToPage(self, page_num):
        """
        Scroll view to specific page.
        
        Args:
            page_num (int): Page number to scroll to
        """
        if 0 <= page_num < self.pdf_doc.page_count and page_num < len(self.page_items):
            self.current_page = page_num
            # Scroll to the page's position
            self.centerOn(self.page_items[page_num])
    
    def goToNextPage(self):
        """Go to next page."""
        if self.current_page < self.pdf_doc.page_count - 1:
            self.goToPage(self.current_page + 1)
    
    def goToPrevPage(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.goToPage(self.current_page - 1)
    
    # Event handlers
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming and scrolling."""
        if event.modifiers() & Qt.ControlModifier:
            # Zoom with Ctrl+Wheel
            delta = event.angleDelta().y()
            
            # Get position under mouse before zoom
            pos_before = self.mapToScene(event.position().toPoint())
            
            if delta > 0:
                self.zoomIn()
            else:
                self.zoomOut()
                
            # Keep point under mouse fixed
            pos_after = self.mapToScene(event.position().toPoint())
            delta_scene = pos_after - pos_before
            self.translate(delta_scene.x(), delta_scene.y())
            
            event.accept()
        else:
            # Normal scrolling
            super().wheelEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for panning, selection, and annotation."""
        if not self.pdf_doc.doc:
            super().mousePressEvent(event)
            return
            
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            
            if event.modifiers() & Qt.ControlModifier:
                # Start text selection with Ctrl+Left click
                self.is_selecting = True
                self.selection_start = scene_pos
                
                # Create selection rectangle
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
        """Handle mouse move events."""
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
        """Handle mouse release events."""
        if event.button() == Qt.LeftButton and self.is_selecting:
            end_pos = self.mapToScene(event.position().toPoint())
            
            # Get selected text
            selected_text = self.getSelectedText()
            
            # Emit selection signal
            if selected_text:
                self.textSelected.emit(selected_text)
                
                # Create annotation from selection
                rect = self.selection_rect.rect()
                start_page_idx, start_pdf_pos = self.mapPDFPositionToPage(rect.topLeft())
                end_page_idx, end_pdf_pos = self.mapPDFPositionToPage(rect.bottomRight())
                
                if start_page_idx >= 0 and end_page_idx >= 0:
                    # Check if this is a multi-page selection
                    if start_page_idx == end_page_idx:
                        # Single page selection - handle as before
                        pdf_rect = fitz.Rect(start_pdf_pos[0], start_pdf_pos[1], end_pdf_pos[0], end_pdf_pos[1])
                        
                        # Emit signal with annotation info
                        annotation_info = {
                            'page': start_page_idx,
                            'rect': pdf_rect,
                            'text': selected_text,
                            'type': 'selection',
                            'is_multipage': False
                        }
                        self.annotationAdded.emit(annotation_info)
                    else:
                        # Multi-page selection - create a separate annotation for each page
                        self.handleMultiPageSelection(start_page_idx, start_pdf_pos, end_page_idx, end_pdf_pos, selected_text)
                
                # Clean up
                self.is_selecting = False
                if self.selection_rect:
                    self.scene.removeItem(self.selection_rect)
                    self.selection_rect = None
                    
                event.accept()
            else:
                super().mouseReleaseEvent(event)
                self.setDragMode(QGraphicsView.NoDrag)

    def scrollToAnnotation(self, page_num, rect):
        """
        Scroll to make a specific annotation visible.
        
        Args:
            page_num (int): Page number of the annotation
            rect (fitz.Rect): Rectangle coordinates of the annotation
        """
        if not self.pdf_doc.doc or page_num < 0 or page_num >= self.pdf_doc.page_count:
            return
        
        # First, make sure the page is in view by going to that page
        self.goToPage(page_num)
        
        # Then, calculate the scene coordinates for the annotation
        if page_num < len(self.pages):
            page = self.pages[page_num]
            
            # Convert PDF coordinates to scene coordinates
            pdf_to_scene = self.pdf_doc.dpi / 72.0
            scene_x = page['rect'].x() + (rect.x0 * pdf_to_scene)
            scene_y = page['rect'].y() + (rect.y0 * pdf_to_scene)
            
            # Center on the annotation
            self.centerOn(scene_x, scene_y)

    def handleMultiPageSelection(self, start_page_idx, start_pdf_pos, end_page_idx, end_pdf_pos, complete_text):
        """Handle selections that span multiple pages by creating separate annotations for each page.
        
        Args:
            start_page_idx (int): Index of the first page in the selection
            start_pdf_pos (tuple): PDF coordinates on the first page
            end_page_idx (int): Index of the last page in the selection
            end_pdf_pos (tuple): PDF coordinates on the last page
            complete_text (str): Complete text from the selection across all pages
        """
        # Get group ID to associate annotations across pages
        group_id = str(int(time.time() * 1000))  # Simple timestamp-based ID
        
        # Calculate total number of pages in this multi-page selection
        total_pages = end_page_idx - start_page_idx + 1
        
        # Handle first page
        first_page = self.pdf_doc.doc[start_page_idx]
        first_page_rect = fitz.Rect(start_pdf_pos[0], start_pdf_pos[1], first_page.rect.width, first_page.rect.height)
        first_page_text = self.pdf_doc.get_text_in_rect(start_page_idx, first_page_rect)
        
        # Emit signal for first page annotation
        self.annotationAdded.emit({
            'page': start_page_idx,
            'rect': first_page_rect,
            'text': first_page_text,
            'type': 'selection',
            'is_multipage': True,
            'multipage_position': 1,  # Now using 1-based position numbering
            'multipage_type': 'start',  # Type remains as start/middle/end
            'group_id': group_id,
            'complete_text': complete_text  # Store the complete text with the first annotation
        })
        
        # Handle middle pages (if any)
        position = 2  # Start with position 2
        for page_idx in range(start_page_idx + 1, end_page_idx):
            page = self.pdf_doc.doc[page_idx]
            page_rect = page.rect
            page_text = self.pdf_doc.get_text_in_rect(page_idx, page_rect)
            
            self.annotationAdded.emit({
                'page': page_idx,
                'rect': page_rect,
                'text': page_text,
                'type': 'selection',
                'is_multipage': True,
                'multipage_position': position,
                'multipage_type': 'middle',
                'group_id': group_id
            })
            position += 1
        
        # Handle last page
        last_page_rect = fitz.Rect(0, 0, end_pdf_pos[0], end_pdf_pos[1])
        last_page_text = self.pdf_doc.get_text_in_rect(end_page_idx, last_page_rect)
        
        self.annotationAdded.emit({
            'page': end_page_idx,
            'rect': last_page_rect,
            'text': last_page_text,
            'type': 'selection',
            'is_multipage': True,
            'multipage_position': total_pages,
            'multipage_type': 'end',
            'group_id': group_id
        })
