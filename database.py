import sqlite3
import os
import csv
from dateutil.parser import parse

def standardize_date(date_str):
    """Convert various date formats to YYYY-MM-DD"""
    if not date_str:
        return None
    try:
        date_obj = parse(date_str)
        return date_obj.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error parsing date: {e}")
        return None

class AnnotationDB:
    """SQLite database handler for PDF annotations"""
    
    def __init__(self, db_path="annotations.db"):
        """Initialize the database connection"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Connect to the SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # Enable foreign key support
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            print(f"Database connection error: {str(e)}")
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            # Create annotations table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                page_num INTEGER NOT NULL,
                rect_x0 REAL NOT NULL,
                rect_y0 REAL NOT NULL,
                rect_x1 REAL NOT NULL,
                rect_y1 REAL NOT NULL,
                annotation_text TEXT,
                annotation_type TEXT NOT NULL,
                field_name TEXT NOT NULL,
                line_item_number TEXT,
                standardized_date TEXT,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating tables: {str(e)}")
    
    def add_annotation(self, file_path, annotation):
        """Add a new annotation to the database"""
        try:
            # Extract just the filename (not the full path)
            file_name = os.path.basename(file_path)
            
            # Extract rect coordinates
            rect = annotation['rect']
            rect_x0, rect_y0, rect_x1, rect_y1 = rect.x0, rect.y0, rect.x1, rect.y1
            
            # Check if the field is a date field and should be converted
            date_fields = ['rfq_date', 'due_date', 'requested_delivery_date']
            field_name = annotation.get('field', '')
            standardized_date = None
            
            if field_name in date_fields and annotation['text']:
                # Try to convert the date
                standardized_date = standardize_date(annotation['text'])
            
            # Insert into annotations table
            self.cursor.execute('''
            INSERT INTO annotations (
                file_name, page_num, rect_x0, rect_y0, rect_x1, rect_y1,
                annotation_text, annotation_type, field_name, line_item_number, standardized_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_name,
                annotation['page'],
                rect_x0, rect_y0, rect_x1, rect_y1,
                annotation['text'],
                annotation.get('type', ''),
                field_name,
                annotation.get('line_item_number', ''),
                standardized_date
            ))
            
            annotation_id = self.cursor.lastrowid
            self.conn.commit()
            return annotation_id
            
        except sqlite3.Error as e:
            print(f"Error adding annotation: {str(e)}")
            return None
    
    def get_annotations_for_file(self, file_path):
        """Get all annotations for a specific PDF file using just the filename"""
        try:
            # Extract just the filename (not the full path)
            file_name = os.path.basename(file_path)
            
            self.cursor.execute('''
            SELECT id, page_num, rect_x0, rect_y0, rect_x1, rect_y1,
                   annotation_text, annotation_type, field_name, line_item_number,
                   standardized_date, file_name
            FROM annotations
            WHERE file_name = ?
            ORDER BY id
            ''', (file_name,))
            
            annotations = []
            for row in self.cursor.fetchall():
                annotation = {
                    'id': row[0],
                    'page': row[1],
                    'rect': (row[2], row[3], row[4], row[5]),
                    'rect_str': f"({row[2]:.2f}, {row[3]:.2f}, {row[4]:.2f}, {row[5]:.2f})",
                    'text': row[6],
                    'type': row[7],
                    'field': row[8],
                    'line_item_number': row[9],
                    'file_name': row[11]
                }
                
                # If this is a date field and we have a standardized date
                if row[10] is not None:
                    annotation['standardized_date'] = row[10]
                
                annotations.append(annotation)
            
            return annotations
            
        except sqlite3.Error as e:
            print(f"Error retrieving annotations: {str(e)}")
            return []
    
    def remove_annotation(self, annotation_id):
        """Remove an annotation from the database"""
        try:
            self.cursor.execute('DELETE FROM annotations WHERE id = ?', (annotation_id,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error removing annotation: {str(e)}")
            return False
    
    def export_annotations_to_csv(self, file_path, output_path):
        """Export annotations for a file to CSV"""
        try:
            annotations = self.get_annotations_for_file(file_path)
            
            if not annotations:
                return False
            
            with open(output_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'id', 'file_name', 'page', 'type', 'field', 'line_item_number', 
                    'rect_x0', 'rect_y0', 'rect_x1', 'rect_y1',
                    'text', 'standardized_date'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for annot in annotations:
                    # Parse the rect tuple
                    rect_x0, rect_y0, rect_x1, rect_y1 = annot['rect']
                    
                    row = {
                        'id': annot['id'],
                        'file_name': annot['file_name'],
                        'page': annot['page'] + 1,  # +1 for human-readable page numbers
                        'type': annot['type'],
                        'field': annot['field'],
                        'line_item_number': annot['line_item_number'],
                        'rect_x0': rect_x0,
                        'rect_y0': rect_y0,
                        'rect_x1': rect_x1,
                        'rect_y1': rect_y1,
                        'text': annot['text'],
                        'standardized_date': annot.get('standardized_date', '')
                    }
                    writer.writerow(row)
            
            return True
            
        except Exception as e:
            print(f"Error exporting to CSV: {str(e)}")
            return False
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()