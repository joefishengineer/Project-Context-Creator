"""
Box Note Converter
Converts Box Note (.boxnote) files to Markdown
Box Notes are stored as JSON with a ProseMirror document structure
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

def convert_boxnote_to_markdown(input_path: Path, output_path: Path) -> bool:
    """
    Convert Box Note JSON to Markdown
    
    Args:
        input_path: Path to .boxnote file
        output_path: Path for output .md file
        
    Returns:
        True if conversion successful, False otherwise
    """
    try:
        logging.info(f"Converting Box Note: {input_path.name}")
        
        # Read Box Note JSON
        with open(input_path, 'r', encoding='utf-8') as f:
            boxnote_data = json.load(f)
        
        # Extract document structure
        doc = boxnote_data.get('doc', {})
        content = doc.get('content', [])
        
        # Convert to markdown
        markdown_lines = []
        markdown_lines.append(f"# {input_path.stem}\n\n")
        markdown_lines.append(f"*Converted from Box Note*\n\n")
        markdown_lines.append("---\n\n")
        
        # Process content nodes
        for node in content:
            markdown_lines.extend(_process_node(node))
        
        # Write output
        markdown_content = ''.join(markdown_lines)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_content, encoding='utf-8')
        
        logging.info(f"Successfully converted Box Note to: {output_path.name}")
        return True
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in Box Note {input_path.name}: {e}")
        return False
    except Exception as e:
        logging.error(f"Failed to convert Box Note {input_path.name}: {e}")
        return False


def _process_node(node: Dict[str, Any], level: int = 0) -> List[str]:
    """
    Process a ProseMirror node and convert to markdown
    
    Args:
        node: ProseMirror node dictionary
        level: Current nesting level
        
    Returns:
        List of markdown lines
    """
    lines = []
    node_type = node.get('type', '')
    content = node.get('content', [])
    attrs = node.get('attrs', {})
    marks = node.get('marks', [])
    text = node.get('text', '')
    
    # Handle different node types
    if node_type == 'paragraph':
        # Process paragraph content
        para_text = _process_content(content, marks)
        if para_text.strip():
            lines.append(f"{para_text}\n\n")
    
    elif node_type == 'heading':
        # Heading with level
        heading_level = attrs.get('level', 1)
        heading_text = _process_content(content, marks)
        lines.append(f"{'#' * heading_level} {heading_text}\n\n")
    
    elif node_type == 'bulletList':
        # Bullet list
        for item in content:
            if item.get('type') == 'listItem':
                item_content = item.get('content', [])
                for para in item_content:
                    if para.get('type') == 'paragraph':
                        item_text = _process_content(para.get('content', []), marks)
                        lines.append(f"- {item_text}\n")
        lines.append("\n")
    
    elif node_type == 'orderedList':
        # Numbered list
        start = attrs.get('start', 1)
        for idx, item in enumerate(content, start=start):
            if item.get('type') == 'listItem':
                item_content = item.get('content', [])
                for para in item_content:
                    if para.get('type') == 'paragraph':
                        item_text = _process_content(para.get('content', []), marks)
                        lines.append(f"{idx}. {item_text}\n")
        lines.append("\n")
    
    elif node_type == 'codeBlock':
        # Code block
        code_text = _process_content(content, marks)
        language = attrs.get('language', '')
        lines.append(f"```{language}\n{code_text}\n```\n\n")
    
    elif node_type == 'blockquote':
        # Blockquote
        for item in content:
            quote_lines = _process_node(item, level + 1)
            for line in quote_lines:
                if line.strip():
                    lines.append(f"> {line}")
        lines.append("\n")
    
    elif node_type == 'table':
        # Table
        lines.extend(_process_table(node))
    
    elif node_type == 'horizontalRule':
        # Horizontal rule
        lines.append("---\n\n")
    
    elif node_type == 'text':
        # Plain text node
        formatted_text = _apply_marks(text, marks)
        lines.append(formatted_text)
    
    else:
        # Unknown node type - try to process content
        if content:
            for child in content:
                lines.extend(_process_node(child, level))
    
    return lines


def _process_content(content: List[Dict], parent_marks: Optional[List] = None) -> str:
    """Process content array and return formatted text"""
    if not content:
        return ""
    
    text_parts = []
    for node in content:
        if node.get('type') == 'text':
            text = node.get('text', '')
            marks = node.get('marks', parent_marks or [])
            formatted = _apply_marks(text, marks)
            text_parts.append(formatted)
        elif node.get('type') == 'hardBreak':
            text_parts.append('\n')
        else:
            # Recursively process nested content
            nested = _process_node(node)
            text_parts.extend(nested)
    
    return ''.join(text_parts)


def _apply_marks(text: str, marks: List[Dict]) -> str:
    """Apply formatting marks to text"""
    if not marks:
        return text
    
    formatted = text
    
    for mark in marks:
        mark_type = mark.get('type', '')
        
        if mark_type == 'strong' or mark_type == 'bold':
            formatted = f"**{formatted}**"
        elif mark_type == 'em' or mark_type == 'italic':
            formatted = f"*{formatted}*"
        elif mark_type == 'code':
            formatted = f"`{formatted}`"
        elif mark_type == 'link':
            href = mark.get('attrs', {}).get('href', '')
            formatted = f"[{formatted}]({href})"
        elif mark_type == 'strike':
            formatted = f"~~{formatted}~~"
        elif mark_type == 'underline':
            # Markdown doesn't have native underline, use HTML
            formatted = f"<u>{formatted}</u>"
    
    return formatted


def _process_table(table_node: Dict) -> List[str]:
    """Process table node and convert to markdown table"""
    lines = []
    content = table_node.get('content', [])
    
    if not content:
        return lines
    
    # Extract rows
    rows = []
    for item in content:
        if item.get('type') in ['tableRow', 'table_row']:
            row_content = item.get('content', [])
            cells = []
            for cell in row_content:
                if cell.get('type') in ['tableCell', 'table_cell', 'tableHeader', 'table_header']:
                    cell_content = cell.get('content', [])
                    cell_text = []
                    for para in cell_content:
                        if para.get('type') == 'paragraph':
                            cell_text.append(_process_content(para.get('content', []), []))
                    cells.append(' '.join(cell_text).strip())
            if cells:
                rows.append(cells)
    
    if not rows:
        return lines
    
    # Build markdown table
    # Header row
    if rows:
        lines.append("| " + " | ".join(rows[0]) + " |\n")
        lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |\n")
        
        # Data rows
        for row in rows[1:]:
            # Pad row if needed
            while len(row) < len(rows[0]):
                row.append("")
            lines.append("| " + " | ".join(row) + " |\n")
        
        lines.append("\n")
    
    return lines


# Test function
def test_boxnote_converter():
    """Test the Box Note converter with sample data"""
    sample_boxnote = {
        "version": 1,
        "schema_version": 1,
        "doc": {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 1},
                    "content": [{"type": "text", "text": "Test Document"}]
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "This is "},
                        {"type": "text", "marks": [{"type": "strong"}], "text": "bold"},
                        {"type": "text", "text": " and "},
                        {"type": "text", "marks": [{"type": "em"}], "text": "italic"},
                        {"type": "text", "text": " text."}
                    ]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item 1"}]
                                }
                            ]
                        },
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item 2"}]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }
    
    # Write test file
    test_path = Path("test_boxnote.boxnote")
    test_path.write_text(json.dumps(sample_boxnote), encoding='utf-8')
    
    # Convert
    output_path = Path("test_boxnote.md")
    success = convert_boxnote_to_markdown(test_path, output_path)
    
    if success:
        print("✓ Conversion successful!")
        print("\nOutput:")
        print(output_path.read_text(encoding='utf-8'))
    else:
        print("✗ Conversion failed")
    
    # Cleanup
    test_path.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    # Run test
    logging.basicConfig(level=logging.INFO)
    test_boxnote_converter()

# Made with Bob