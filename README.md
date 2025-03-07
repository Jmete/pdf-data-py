# PDF Data Py

## Summary
We are building a PDF viewer app in python that should be able to run on multiple platforms, including Windows.

## Goals & Requirements
The requirements include:
- GUI app that has a menu bar at top, and 2 panels below.
- Left panel will be a PDF viewer, Right panel will show the data extracted from the PDF
- Left panel should take up 2/3 of the space by default, and the right panel should be 1/3 of the space by default.
- The user should be able to drag the middle divider splitter and be able to drag it to adjust the size of the panels.
- The PDF viewer should allow the user to drag-and-drop a PDF file onto the panel to open it, or simply click file -> open.
- The PDF viewer should ideally be able to show all the pages at once as a vertical scrollable view
- It should display the PDF with high-quality and not be blurry when zoomed out. It should look similar to when you view a PDF in Google Chrome.
- The overall app should be aesthetically pleasing and look like a modern desktop app.
- PDF viewing controls should be the following:
-- The user should be able to zoom (with ctrl+mousewheel)
-- The user should be able to drag to move around (with holding left click)
-- The user should be able to scroll down the PDF file (if multiple pages) with the mousewheel.
-- The user should be able to draw annotation boxes that are compatible with pymupdf (with ctrl+leftclick to draw the annotation boxes)
-- Ideally the user should be able to draw the annotation boxes by actually highlighting the text, like you can do in Google Chrome or Adobe Acrobat.
-- I want to display the PDF with selectable text. 
-- There should also be button controls for zooming in [+] and out [-].
-- The annotation data should be saved to a SQLite database as a backend
-- The user should be able to export the annotation data for the current PDF being read to a CSV file
-- Dates extracted from the PDFs should be converted to YYYY-MM-DD format
-- SQLite should have a primary unique auto-incrementing index following best practices
-- Each row in the database will be 1 specific annotation. It should include the file_name as well as the regular annotation data stored in it, including the extracted Rect() data for that annotation.
-- All other fields except for dates and not should be stored as strings, including line_item_number

## Preferred libraries
I prefer to use the following libraries:
- pymupdf
- PySide6

If the above libraries do not support a feature that I want to add, then please let me know and suggest a proper alternative. 

## Data to Extract
<data to extract>
<meta data>
- document_name
- customer_name
- buyer_name
- currency
- rfq_date
- due_date
</meta data>

<line item data>
- line_item_number
- material_number
- part_number
- description
- full_description
- quantity
- unit_of_measure
- requested_delivery_date
- delivery_point
- manufacturer_name
</line item data>
</data to extract>

