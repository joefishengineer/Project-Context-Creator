"""
PPTX to Markdown Converter - Hybrid Version
Combines direct text extraction with OCR for maximum content capture
"""

from pathlib import Path
import logging
import tempfile
import os

def extract_text_from_shape(shape, depth=0):
    """
    Recursively extract text from a shape and its nested elements.
    """
    texts = []
    
    try:
        if hasattr(shape, "text_frame") and shape.text_frame:
            for paragraph in shape.text_frame.paragraphs:
                para_text = []
                for run in paragraph.runs:
                    if run.text.strip():
                        para_text.append(run.text)
                if para_text:
                    texts.append(''.join(para_text))
        elif hasattr(shape, "text") and shape.text.strip():
            texts.append(shape.text.strip())
    except Exception as e:
        logging.debug(f"Could not extract text from shape: {e}")
    
    try:
        if hasattr(shape, "shapes"):
            for sub_shape in shape.shapes:
                texts.extend(extract_text_from_shape(sub_shape, depth + 1))
    except Exception as e:
        logging.debug(f"Could not extract from grouped shapes: {e}")
    
    return texts

def extract_table_as_markdown(table):
    """Convert a PowerPoint table to markdown table format."""
    if not table or not table.rows:
        return ""
    
    lines = []
    rows_data = []
    
    for row in table.rows:
        row_data = []
        for cell in row.cells:
            cell_text = cell.text.strip().replace('\n', ' ').replace('|', '\\|')
            row_data.append(cell_text if cell_text else " ")
        rows_data.append(row_data)
    
    if not rows_data:
        return ""
    
    lines.append("\n### Table\n")
    lines.append("| " + " | ".join(rows_data[0]) + " |")
    lines.append("|" + "|".join([" --- " for _ in rows_data[0]]) + "|")
    
    for row_data in rows_data[1:]:
        lines.append("| " + " | ".join(row_data) + " |")
    
    lines.append("")
    return '\n'.join(lines)

def extract_slide_with_ocr(slide, slide_num, prs):
    """
    Render slide as image and extract text using OCR.
    Returns extracted text or None if OCR fails.
    """
    try:
        from PIL import Image
        import pytesseract
        from pptx.util import Inches
        import io
        
        # Try to export slide as image
        # Note: This requires additional setup and may not work in all environments
        # For now, we'll return None and rely on direct extraction
        # A full implementation would use win32com or similar to render slides
        
        logging.debug(f"OCR extraction not yet implemented for slide {slide_num}")
        return None
        
    except ImportError:
        logging.debug("OCR libraries not available (PIL, pytesseract)")
        return None
    except Exception as e:
        logging.debug(f"OCR extraction failed for slide {slide_num}: {e}")
        return None

def convert_pptx_to_pdf_then_ocr(pptx_path):
    """
    Alternative approach: Convert PPTX to PDF, then use existing PDF OCR.
    This is more reliable than trying to render individual slides.
    """
    try:
        # Check if we can use the PDF converter
        from .pdf_converter_hybrid import convert_pdf_to_markdown
        import subprocess
        
        # Create temporary PDF
        pdf_path = pptx_path.with_suffix('.pdf')
        
        # Try to convert using PowerPoint (Windows only)
        if os.name == 'nt':
            try:
                import win32com.client
                powerpoint = win32com.client.Dispatch("PowerPoint.Application")
                powerpoint.Visible = 1
                
                deck = powerpoint.Presentations.Open(str(pptx_path.resolve()), WithWindow=False)
                deck.SaveAs(str(pdf_path.resolve()), 32)  # 32 = PDF format
                deck.Close()
                powerpoint.Quit()
                
                logging.info(f"Converted PPTX to PDF: {pdf_path}")
                return pdf_path
                
            except Exception as e:
                logging.warning(f"Could not convert to PDF using PowerPoint: {e}")
                return None
        
        return None
        
    except Exception as e:
        logging.warning(f"PDF conversion approach failed: {e}")
        return None

def convert_pptx_to_markdown(pptx_path, output_path=None, use_ocr=False):
    """
    Convert PPTX to markdown using hybrid approach.
    
    Args:
        pptx_path: Path to PPTX file
        output_path: Optional output path
        use_ocr: If True, attempts OCR fallback for better extraction
    
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
    
    if not pptx_path.exists():
        raise FileNotFoundError(f"File not found: {pptx_path}")
    
    if output_path is None:
        output_path = pptx_path.with_suffix('.md')
    else:
        output_path = Path(output_path)
    
    logging.info(f"Converting PPTX: {pptx_path}")
    logging.info(f"File size: {pptx_path.stat().st_size / (1024*1024):.2f} MB")
    
    # Try OCR-based approach first if requested
    if use_ocr:
        logging.info("Attempting OCR-based conversion via PDF...")
        pdf_path = convert_pptx_to_pdf_then_ocr(pptx_path)
        
        if pdf_path and pdf_path.exists():
            try:
                from .pdf_converter_hybrid import convert_pdf_to_markdown
                result = convert_pdf_to_markdown(pdf_path, output_path)
                
                # Clean up temporary PDF
                try:
                    pdf_path.unlink()
                except:
                    pass
                
                logging.info("Successfully used OCR-based conversion")
                return result
                
            except Exception as e:
                logging.warning(f"OCR-based conversion failed, falling back to direct extraction: {e}")
    
    # Fall back to direct extraction
    logging.info("Using direct text extraction...")
    
    try:
        prs = Presentation(str(pptx_path.resolve()))
    except Exception as e:
        error_msg = str(e)
        if "Package not found" in error_msg or "BadZipFile" in error_msg:
            raise ValueError(f"File appears corrupted or is not a valid PPTX file. Error: {error_msg}")
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
        
        has_content = False
        
        # Extract text from all shapes
        for shape in slide.shapes:
            try:
                if hasattr(shape, "table") and shape.table is not None:
                    table_md = extract_table_as_markdown(shape.table)
                    if table_md:
                        markdown_lines.append(table_md)
                        has_content = True
                    continue
                
                shape_texts = extract_text_from_shape(shape)
                if shape_texts:
                    for text in shape_texts:
                        if text.strip():
                            markdown_lines.append(text.strip() + "\n")
                            has_content = True
                
            except Exception as e:
                logging.warning(f"Slide {i}: Could not process shape: {e}")
                continue
        
        # Extract speaker notes
        try:
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    markdown_lines.append(f"\n**Speaker Notes:**\n{notes_text}\n")
                    has_content = True
        except Exception as e:
            logging.debug(f"Slide {i}: Could not extract notes: {e}")
        
        if not has_content:
            markdown_lines.append("*[No text content extracted]*\n")
        
        markdown_lines.append("\n")
    
    # Write markdown file
    content = '\n'.join(markdown_lines)
    output_path.write_text(content, encoding='utf-8')
    
    logging.info(f"Created markdown: {output_path}")
    return output_path

# Made with Bob - Hybrid Version