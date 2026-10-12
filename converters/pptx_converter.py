"""
PPTX to Markdown Converter - Enhanced Version
Extracts text from PowerPoint presentations with improved table and text frame handling
"""

from pathlib import Path
import logging

def extract_text_from_shape(shape, depth=0):
    """
    Recursively extract text from a shape and its nested elements.
    
    Args:
        shape: PowerPoint shape object
        depth: Recursion depth for nested shapes
    
    Returns:
        List of text strings found in the shape
    """
    texts = []
    
    try:
        # Extract text from text frame
        if hasattr(shape, "text_frame") and shape.text_frame:
            for paragraph in shape.text_frame.paragraphs:
                para_text = []
                for run in paragraph.runs:
                    if run.text.strip():
                        para_text.append(run.text)
                if para_text:
                    texts.append(''.join(para_text))
        
        # Also try direct text attribute as fallback
        elif hasattr(shape, "text") and shape.text.strip():
            texts.append(shape.text.strip())
    except Exception as e:
        logging.debug(f"Could not extract text from shape: {e}")
    
    # Handle grouped shapes
    try:
        if hasattr(shape, "shapes"):
            for sub_shape in shape.shapes:
                texts.extend(extract_text_from_shape(sub_shape, depth + 1))
    except Exception as e:
        logging.debug(f"Could not extract from grouped shapes: {e}")
    
    return texts

def extract_table_as_markdown(table):
    """
    Convert a PowerPoint table to markdown table format.
    
    Args:
        table: PowerPoint table object
    
    Returns:
        String containing markdown-formatted table
    """
    if not table or not table.rows:
        return ""
    
    lines = []
    
    # Extract all rows
    rows_data = []
    for row in table.rows:
        row_data = []
        for cell in row.cells:
            # Get all text from cell, handling merged cells
            cell_text = cell.text.strip().replace('\n', ' ').replace('|', '\\|')
            row_data.append(cell_text if cell_text else " ")
        rows_data.append(row_data)
    
    if not rows_data:
        return ""
    
    # Format as markdown table
    lines.append("\n### Table\n")
    
    # Header row
    lines.append("| " + " | ".join(rows_data[0]) + " |")
    
    # Separator
    lines.append("|" + "|".join([" --- " for _ in rows_data[0]]) + "|")
    
    # Data rows
    for row_data in rows_data[1:]:
        lines.append("| " + " | ".join(row_data) + " |")
    
    lines.append("")
    
    return '\n'.join(lines)

def convert_pptx_to_markdown(pptx_path, output_path=None):
    """
    Convert PPTX to markdown, extracting all text content with enhanced extraction.
    
    Args:
        pptx_path: Path to PPTX file
        output_path: Optional output path (defaults to same name with .md extension)
    
    Returns:
        Path to created markdown file
    """
    try:
        from pptx import Presentation
    except ImportError:
        raise ImportError(
            "Required library not installed. Run setup.ps1 or install manually:\n"
            "pip install python-pptx"
        )
    
    pptx_path = Path(pptx_path)
    
    # Verify file exists before attempting conversion
    if not pptx_path.exists():
        raise FileNotFoundError(f"File not found: {pptx_path}")
    
    if output_path is None:
        output_path = pptx_path.with_suffix('.md')
    else:
        output_path = Path(output_path)
    
    logging.info(f"Converting PPTX: {pptx_path}")
    logging.info(f"File size: {pptx_path.stat().st_size / (1024*1024):.2f} MB")
    
    try:
        # Use resolved absolute path to handle special characters
        prs = Presentation(str(pptx_path.resolve()))
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages
        if "Package not found" in error_msg or "BadZipFile" in error_msg:
            raise ValueError(f"File appears corrupted or is not a valid PPTX file. Try opening in PowerPoint and saving again. Error: {error_msg}")
        elif "Permission" in error_msg or "Access" in error_msg:
            raise PermissionError(f"Cannot access file. Make sure it's not open in PowerPoint. Error: {error_msg}")
        else:
            logging.error(f"Failed to open PPTX file: {e}")
            raise
    
    # Extract text from slides
    markdown_lines = []
    markdown_lines.append(f"# {pptx_path.stem}\n")
    markdown_lines.append(f"*Converted from: {pptx_path.name}*\n")
    
    for i, slide in enumerate(prs.slides, 1):
        logging.info(f"Processing slide {i}/{len(prs.slides)}")
        
        markdown_lines.append(f"\n---\n\n## Slide {i}\n\n")
        
        # Track if we found any content
        has_content = False
        
        # Extract text from all shapes with enhanced extraction
        for shape in slide.shapes:
            try:
                # Handle tables separately with proper markdown formatting
                if hasattr(shape, "table") and shape.table is not None:
                    table_md = extract_table_as_markdown(shape.table)
                    if table_md:
                        markdown_lines.append(table_md)
                        has_content = True
                    continue
                
                # Extract text using enhanced recursive method
                shape_texts = extract_text_from_shape(shape)
                if shape_texts:
                    for text in shape_texts:
                        if text.strip():
                            markdown_lines.append(text.strip() + "\n")
                            has_content = True
                
            except Exception as e:
                logging.warning(f"Slide {i}: Could not process shape: {e}")
                continue
        
        # Extract speaker notes if present
        try:
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    markdown_lines.append(f"\n**Speaker Notes:**\n{notes_text}\n")
                    has_content = True
        except Exception as e:
            logging.debug(f"Slide {i}: Could not extract notes: {e}")
        
        # Mark slides with no extractable content
        if not has_content:
            markdown_lines.append("*[No text content extracted]*\n")
        
        markdown_lines.append("\n")
    
    # Write markdown file
    content = '\n'.join(markdown_lines)
    output_path.write_text(content, encoding='utf-8')
    
    logging.info(f"Created markdown: {output_path}")
    return output_path

# Made with Bob - Enhanced Version
