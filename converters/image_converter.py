"""
Image to Markdown Converter
Extracts text from images using OCR
"""

from pathlib import Path
import logging

def convert_image_to_markdown(image_path, output_path=None):
    """
    Convert image to markdown using OCR.
    
    Args:
        image_path: Path to image file (JPG, PNG, etc.)
        output_path: Optional output path (defaults to same name with .md extension)
    
    Returns:
        Path to created markdown file
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError(
            "Required libraries not installed. Run setup.ps1 or install manually:\n"
            "pip install pytesseract pillow"
        )
    
    image_path = Path(image_path)
    if output_path is None:
        output_path = image_path.with_suffix('.md')
    else:
        output_path = Path(output_path)
    
    logging.info(f"Converting image: {image_path}")
    
    try:
        # Open and process image
        image = Image.open(str(image_path))
        
        # Extract text using OCR
        text = pytesseract.image_to_string(image, lang='eng')
        text = text.strip()
        
    except Exception as e:
        logging.error(f"Failed to process image: {e}")
        raise
    
    # Create markdown
    markdown_lines = []
    markdown_lines.append(f"# {image_path.stem}\n")
    markdown_lines.append(f"*Converted from: {image_path.name}*\n\n")
    
    if text:
        markdown_lines.append(text)
    else:
        markdown_lines.append("*[No text detected in image]*")
    
    # Write markdown file
    content = '\n'.join(markdown_lines)
    output_path.write_text(content, encoding='utf-8')
    
    logging.info(f"Created markdown: {output_path}")
    return output_path

# Made with Bob
