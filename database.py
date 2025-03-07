import sqlite3
import os
import csv
from dateutil.parser import parse

def standardize_date(date_str):
    """Convert various date formats to YYYY-MM-DD"""
    if not date_str:
        return None
        
    # Clean the date string by removing brackets and extra whitespace
    cleaned_date_str = date_str.replace('[', '').replace(']', '').strip()
    
    # If the string is empty after cleaning, return None
    if not cleaned_date_str:
        return None
    
    try:
        date_obj = parse(cleaned_date_str)
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
                # Use standardized_date if it's already in the annotation
                if 'standardized_date' in annotation and annotation['standardized_date']:
                    standardized_date = annotation['standardized_date']
                else:
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
            # Check if annotation exists before deleting
            self.cursor.execute('SELECT id FROM annotations WHERE id = ?', (annotation_id,))
            if not self.cursor.fetchone():
                print(f"Warning: Annotation ID {annotation_id} not found in database")
                return False
                
            # Perform the deletion
            self.cursor.execute('DELETE FROM annotations WHERE id = ?', (annotation_id,))
            rows_affected = self.cursor.rowcount
            self.conn.commit()
            
            # Verify deletion
            if rows_affected > 0:
                print(f"Successfully deleted annotation ID {annotation_id} from database")
                return True
            else:
                print(f"No rows affected when deleting annotation ID {annotation_id}")
                return False
                
        except sqlite3.Error as e:
            print(f"Error removing annotation: {str(e)}")
            self.conn.rollback()  # Rollback on error
            return False
    
    def export_annotations_to_csv(self, file_path, output_path):
        """Export annotations for a file to CSV"""
        try:
            # Get annotations directly from the database to ensure we have the most current data
            file_name = os.path.basename(file_path)
            
            self.cursor.execute('''
            SELECT id, page_num, rect_x0, rect_y0, rect_x1, rect_y1,
                   annotation_text, annotation_type, field_name, line_item_number,
                   standardized_date, file_name
            FROM annotations
            WHERE file_name = ?
            ORDER BY id
            ''', (file_name,))
            
            rows = self.cursor.fetchall()
            
            if not rows:
                print(f"No annotations found in database for {file_name}")
                return False
            
            with open(output_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'id', 'file_name', 'page', 'type', 'field', 'line_item_number', 
                    'rect_x0', 'rect_y0', 'rect_x1', 'rect_y1',
                    'text', 'standardized_date'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in rows:
                    row_dict = {
                        'id': row[0],
                        'file_name': row[11],
                        'page': row[1] + 1,  # +1 for human-readable page numbers
                        'type': row[7],
                        'field': row[8],
                        'line_item_number': row[9],
                        'rect_x0': row[2],
                        'rect_y0': row[3],
                        'rect_x1': row[4],
                        'rect_y1': row[5],
                        'text': row[6],
                        'standardized_date': row[10] if row[10] else ''
                    }
                    writer.writerow(row_dict)
            
            print(f"Successfully exported {len(rows)} annotations to {output_path}")
            return True
            
        except Exception as e:
            print(f"Error exporting to CSV: {str(e)}")
            return False
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()