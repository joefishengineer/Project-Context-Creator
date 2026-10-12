"""
Markdown File Copier
Copies existing .md files to output folder with metadata preservation
"""

import logging
import shutil
from pathlib import Path
from datetime import datetime

def copy_markdown_file(input_path: Path, output_path: Path) -> bool:
    """
    Copy existing markdown file to output location
    
    Args:
        input_path: Path to source .md file
        output_path: Path for output .md file
        
    Returns:
        True if copy successful, False otherwise
    """
    try:
        logging.info(f"Copying markdown file: {input_path.name}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read source file
        content = input_path.read_text(encoding='utf-8')
        
        # Add metadata header
        metadata_header = f"""<!-- 
Source: {input_path.name}
Original Path: {input_path}
Copied: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-->

"""
        
        # Write to output with metadata
        output_path.write_text(metadata_header + content, encoding='utf-8')
        
        logging.info(f"Successfully copied markdown to: {output_path.name}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to copy markdown {input_path.name}: {e}")
        return False


# Made with Bob