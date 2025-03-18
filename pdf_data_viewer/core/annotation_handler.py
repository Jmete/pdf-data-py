"""Handler for PDF annotations."""

import fitz
from ..config import DATE_FIELDS
from ..utils.date_utils import standardize_date

class AnnotationHandler:
    """Handler for PDF annotation operations."""
    
    def __init__(self, pdf_document):
        """
        Initialize the annotation handler.
        
        Args:
            pdf_document (PDFDocument): PDF document handler instance
        """
        self.pdf_document = pdf_document
        self.annotations = []
        self.last_line_item_number = ""
    
    def clear_annotations(self):
        """Clear all annotations from memory."""
        self.annotations = []
    
    def add_annotation(self, page_num, rect, text, field_info=None, is_multipage=False, multipage_position=None, multipage_type='', group_id=''):
        """
        Add an annotation to the PDF.
        
        Args:
            page_num (int): Page number
            rect (fitz.Rect): Rectangle coordinates
            text (str): Text content of the annotation
            field_info (dict, optional): Field information for the annotation
            is_multipage (bool): Whether this is part of a multi-page annotation
            multipage_position (int): Position number in multi-page annotation (1,2,3...)
            multipage_type (str): Type in multi-page annotation ('start', 'middle', 'end')
            group_id (str): Group ID for associating multi-page annotations
            
        Returns:
            dict: The created annotation data
        """
        # Add highlight to the PDF document
        self.pdf_document.add_highlight_annotation(page_num, rect)
        
        # Create annotation object
        annotation = {
            'page': page_num,
            'rect': rect,
            'rect_str': f"({rect.x0:.2f}, {rect.y0:.2f}, {rect.x1:.2f}, {rect.y1:.2f})",
            'text': text,
            'annot_id': len(self.annotations)  # Use a unique ID
        }
        
        # Add multi-page annotation data if applicable
        if is_multipage:
            annotation['is_multipage'] = True
            annotation['multipage_position'] = multipage_position
            annotation['multipage_type'] = multipage_type
            annotation['group_id'] = group_id
        
        # Add field info if provided
        if field_info:
            annotation.update(field_info)
            
            # Process date fields (only if standardized_date is not already provided)
            if field_info.get('field') in DATE_FIELDS and 'standardized_date' not in annotation and text:
                cleaned_text = self.clean_text_for_date_field(text, field_info.get('field'))
                if cleaned_text != text:
                    annotation['text'] = cleaned_text
                
                # Try to standardize the date (only log at debug level to avoid duplication)
                std_date = standardize_date(cleaned_text, log_level='debug')
                if std_date:
                    annotation['standardized_date'] = std_date
            
            # Remember the last line item number
            if field_info.get('type') == 'line_item' and field_info.get('line_item_number'):
                self.last_line_item_number = field_info.get('line_item_number')
        
        # Store the annotation
        self.annotations.append(annotation)
        
        return annotation
    
    def remove_annotation_by_index(self, index):
        """
        Remove an annotation by its index.
        
        Args:
            index (int): Index of the annotation in the annotations list
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.annotations or index < 0 or index >= len(self.annotations):
            return False
            
        # Get the annotation to remove
        annotation = self.annotations[index]
        page_num = annotation['page']
        
        # Find position of this annotation among annotations on the same page
        page_annotations = [(i, a) for i, a in enumerate(self.annotations) if a['page'] == page_num]
        
        # Find the position of our annotation within that page's annotations
        annot_position = None
        for i, (list_idx, annot) in enumerate(page_annotations):
            if list_idx == index:
                annot_position = i
                break
        
        # Remove from the document
        if self.pdf_document.remove_annotation(page_num, annot_position):
            # Remove from our annotations list
            self.annotations.pop(index)
            return True
            
        return False
    
    def remove_last_annotation(self):
        """
        Remove the last annotation added.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.annotations:
            return False
            
        # Get the last annotation
        last_annot = self.annotations[-1]
        page_num = last_annot['page']
        
        # Remove from the document
        if self.pdf_document.remove_annotation(page_num):
            # Remove from our list
            self.annotations.pop()
            return True
            
        return False
    
    @staticmethod
    def clean_text_for_date_field(text, field_type):
        """
        Clean text for date fields by removing brackets.
        
        Args:
            text (str): Text to clean
            field_type (str): Field type
            
        Returns:
            str: Cleaned text
        """
        if field_type in DATE_FIELDS:
            return text.replace('[', '').replace(']', '').strip()
        return text