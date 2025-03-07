"""Core functionality for handling PDF documents."""

import fitz  # PyMuPDF
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import QRectF

class PDFDocument:
    """Handler for PDF document operations."""
    
    def __init__(self, dpi=300, render_quality="high"):
        """
        Initialize the PDF document handler.
        
        Args:
            dpi (int): DPI for rendering
            render_quality (str): Quality setting for rendering (standard, high, very high)
        """
        self.doc = None
        self.file_path = None
        self.page_count = 0
        self.dpi = dpi
        self.render_quality = render_quality
    
    def load(self, file_path):
        """
        Load a PDF document.
        
        Args:
            file_path (str): Path to the PDF file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Close existing document if open
            if self.doc:
                self.doc.close()
                
            self.doc = fitz.open(file_path)
            self.file_path = file_path
            self.page_count = len(self.doc)
            
            return self.page_count > 0
            
        except Exception as e:
            print(f"Error loading PDF: {str(e)}")
            return False
    
    def close(self):
        """Close the current document."""
        if self.doc:
            self.doc.close()
            self.doc = None
            self.file_path = None
            self.page_count = 0
    
    def render_page(self, page_num):
        """
        Render a specific page to a QPixmap.
        
        Args:
            page_num (int): Page number to render
            
        Returns:
            tuple: (QPixmap, dict) - Rendered page as pixmap and page info
        """
        if not self.doc or page_num < 0 or page_num >= self.page_count:
            return None, None
        
        # Get the page
        page = self.doc[page_num]
        
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
        
        # Render page with settings
        pix = page.get_pixmap(**render_params)
        
        # Convert to QImage and QPixmap
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        
        # Create page info dict
        page_info = {
            'pixmap': pixmap,
            'width': pixmap.width(),
            'height': pixmap.height(),
            'page_obj': page,
            'words': page.get_text("words")  # Get word positions for text selection
        }
        
        return pixmap, page_info
    
    def get_text_in_rect(self, page_num, rect):
        """
        Get text within a rectangle on a specific page.
        
        Args:
            page_num (int): Page number
            rect (fitz.Rect): Rectangle coordinates
            
        Returns:
            str: Text content within the rectangle
        """
        if not self.doc or page_num < 0 or page_num >= self.page_count:
            return ""
        
        page = self.doc[page_num]
        return page.get_text("text", clip=rect)
    
    def add_highlight_annotation(self, page_num, rect):
        """
        Add a highlight annotation to a page.
        
        Args:
            page_num (int): Page number
            rect (fitz.Rect): Rectangle coordinates
            
        Returns:
            fitz.Annot: The created annotation object or None if failed
        """
        if not self.doc or page_num < 0 or page_num >= self.page_count:
            return None
        
        page = self.doc[page_num]
        try:
            return page.add_highlight_annot(rect)
        except Exception as e:
            print(f"Error adding highlight: {str(e)}")
            return None
    
    def remove_annotation(self, page_num, annot_idx=None):
        """
        Remove an annotation from a page.
        
        Args:
            page_num (int): Page number
            annot_idx (int, optional): Index of the annotation to remove, 
                                      defaults to the last annotation
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.doc or page_num < 0 or page_num >= self.page_count:
            return False
            
        page = self.doc[page_num]
        
        try:
            # Get all annotations on the page and convert to a list
            annotations = list(page.annots())
            if annotations and len(annotations) > 0:
                if annot_idx is not None and 0 <= annot_idx < len(annotations):
                    # Remove the specific annotation if an index is provided
                    page.delete_annot(annotations[annot_idx])
                else:
                    # Default to removing the last annotation on the page
                    page.delete_annot(annotations[-1])
                
                return True
            else:
                print("No annotations found on page")
        except Exception as e:
            print(f"Error removing annotation: {str(e)}")
        return False
    
    def get_metadata(self):
        """
        Get document metadata.
        
        Returns:
            dict: Document metadata
        """
        if not self.doc:
            return {}
        
        return self.doc.metadata
