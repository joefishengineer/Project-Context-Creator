"""
Folder Processor for Batch Document Conversion
Handles recursive folder scanning and batch conversion with incremental updates
"""

from pathlib import Path
import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class FolderProcessor:
    """Process entire folders of documents for conversion"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.xlsx', '.jpg', '.jpeg', '.png', '.boxnote', '.md', '.mp4'}
    METADATA_FILE = '.conversion_metadata.json'
    METADATA_FILE_LEGACY = '.conversion_metadata'
    
    def __init__(self, source_folder: Path, output_folder: Path,
                 exclude_folder_patterns: Optional[List[str]] = None):
        """
        Initialize folder processor

        Args:
            source_folder: Source folder to scan
            output_folder: Output folder for markdown files
            exclude_folder_patterns: Folder name substrings to exclude at any path depth (case-insensitive)
        """
        self.source_folder = Path(source_folder)
        self.output_folder = Path(output_folder)
        # Support both .conversion_metadata.json (current) and .conversion_metadata (legacy)
        legacy = self.output_folder / self.METADATA_FILE_LEGACY
        current = self.output_folder / self.METADATA_FILE
        if legacy.exists() and not current.exists():
            self.metadata_path = legacy
        else:
            self.metadata_path = current
        self.exclude_folder_patterns = [p.lower() for p in (exclude_folder_patterns or [])]
        self.metadata = self._load_metadata()
        self._checkpoint_counter = 0
        
    def _load_metadata(self) -> Dict:
        """Load conversion metadata for incremental updates"""
        if self.metadata_path.exists():
            try:
                # utf-8-sig strips a BOM if present, otherwise reads plain utf-8
                with open(self.metadata_path, 'r', encoding='utf-8-sig') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load metadata: {e}")
        return {'files': {}, 'last_scan': None}
    
    def _save_metadata(self):
        """Save conversion metadata, always backing up before overwriting."""
        try:
            self.output_folder.mkdir(parents=True, exist_ok=True)

            # Safety: if the current metadata on disk has MORE entries than what
            # we're about to write, preserve it as a timestamped backup rather
            # than silently losing conversion history.
            if self.metadata_path.exists():
                try:
                    existing = json.loads(self.metadata_path.read_text(encoding='utf-8'))
                    existing_count = len(existing.get('files', {}))
                    new_count = len(self.metadata.get('files', {}))
                    if existing_count > new_count:
                        backup_name = self.metadata_path.with_name(
                            self.metadata_path.stem
                            + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            + self.metadata_path.suffix
                        )
                        import shutil
                        shutil.copy2(self.metadata_path, backup_name)
                        logging.warning(
                            f"Metadata regression detected ({existing_count} → {new_count} entries). "
                            f"Backed up existing metadata to {backup_name.name}"
                        )
                except Exception:
                    pass  # best-effort; don't block the save

            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save metadata: {e}")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate file hash for change detection"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logging.error(f"Failed to hash {file_path}: {e}")
            return ""
    
    def _needs_conversion(self, file_path: Path) -> bool:
        """Check if file needs conversion (new or modified)"""
        rel_path = str(file_path.relative_to(self.source_folder))
        
        # New file
        if rel_path not in self.metadata['files']:
            return True
        
        # Check if previous conversion was successful
        if not self.metadata['files'][rel_path].get('success', False):
            # Previous conversion failed, try again
            return True
        
        # Check if file was modified
        current_hash = self._get_file_hash(file_path)
        if not current_hash:
            # Can't hash file (likely locked), skip it
            logging.warning(f"Skipping {file_path.name} - cannot access file (may be open)")
            return False
        
        stored_hash = self.metadata['files'][rel_path].get('hash', '')
        
        return current_hash != stored_hash

    def _is_excluded_path(self, file_path: Path) -> bool:
        """Return True if any component of the path matches an exclude pattern."""
        if not self.exclude_folder_patterns:
            return False
        parts = [p.lower() for p in file_path.relative_to(self.source_folder).parts[:-1]]
        return any(pattern in part for part in parts for pattern in self.exclude_folder_patterns)

    def clean_orphans(self) -> int:
        """
        Remove orphaned output .md files whose source files no longer exist.
        Also purges their metadata entries.

        Returns:
            Number of orphaned files cleaned up.
        """
        orphan_count = 0
        orphaned_keys = []

        for rel_path, file_info in self.metadata['files'].items():
            if not file_info.get('success', False):
                continue
            source_file = self.source_folder / rel_path
            if source_file.exists():
                continue  # still present — not an orphan

            # Source is gone — delete the .md output if it exists
            output_rel = file_info.get('output', '')
            if output_rel:
                output_file = self.output_folder / output_rel
                if output_file.exists():
                    try:
                        output_file.unlink()
                        logging.info(f"Orphan cleanup: removed {output_file.name} (source deleted)")
                    except Exception as e:
                        logging.warning(f"Orphan cleanup: could not remove {output_file.name}: {e}")

            orphaned_keys.append(rel_path)
            orphan_count += 1

        for key in orphaned_keys:
            del self.metadata['files'][key]

        if orphan_count:
            logging.info(f"Orphan cleanup: removed {orphan_count} stale file(s)")
            self._save_metadata()

        return orphan_count

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize filename by removing/replacing problematic characters
        
        Args:
            name: Original filename or path component
            
        Returns:
            Sanitized filename safe for all systems
        """
        # Character replacements for upload compatibility
        replacements = {
            '?': '',        # Remove question marks (glob wildcard)
            '*': '',        # Remove asterisks (glob wildcard)
            ':': '-',       # Replace colons with hyphens
            '<': '',        # Remove less than
            '>': '',        # Remove greater than
            '|': '-',       # Replace pipes with hyphens
            '"': "'",       # Replace double quotes with single quotes
            '+': 'and',     # Replace plus with 'and'
            '&': 'and',     # Replace ampersand with 'and'
            '/': '-',       # Replace forward slash
            '\\': '-',      # Replace backslash
        }
        
        sanitized = name
        for char, replacement in replacements.items():
            sanitized = sanitized.replace(char, replacement)
        
        # Clean up multiple spaces and hyphens
        sanitized = ' '.join(sanitized.split())  # Multiple spaces to single
        sanitized = '-'.join(filter(None, sanitized.split('-')))  # Remove empty parts between hyphens
        
        return sanitized.strip()
    
    def _create_flat_filename(self, file_path: Path) -> str:
        """
        Create flat filename with path prefixes and sanitization.
        Handles long paths by truncating components while preserving uniqueness.
        Example: docs/reports/file?.pdf -> docs_reports_file.md
        """
        PATH_LENGTH_THRESHOLD = 240  # Leave buffer for output folder path
        
        rel_path = file_path.relative_to(self.source_folder)
        parts = list(rel_path.parts[:-1])  # All except filename
        filename = rel_path.stem  # Filename without extension
        
        # Sanitize all path components
        sanitized_parts = [self._sanitize_filename(part) for part in parts]
        sanitized_filename = self._sanitize_filename(filename)
        
        # Build initial filename
        if sanitized_parts:
            prefix = '_'.join(sanitized_parts)
            flat_filename = f"{prefix}_{sanitized_filename}.md"
        else:
            flat_filename = f"{sanitized_filename}.md"
        
        # Check if output path will be too long
        output_path = self.output_folder / flat_filename
        if len(str(output_path)) > PATH_LENGTH_THRESHOLD:
            # Truncate components to fit within limit
            flat_filename = self._truncate_filename(sanitized_parts, sanitized_filename, PATH_LENGTH_THRESHOLD)
        
        return flat_filename
    
    def _truncate_filename(self, parts: List[str], filename: str, max_length: int) -> str:
        """
        Truncate filename components to fit within path length limit.
        Preserves uniqueness by keeping start and end of each component.
        
        Args:
            parts: List of sanitized path components (folders)
            filename: Sanitized filename without extension
            max_length: Maximum allowed path length
            
        Returns:
            Truncated flat filename that fits within limit
        """
        import hashlib
        
        # Calculate available space for filename (accounting for output folder path + .md extension)
        output_folder_len = len(str(self.output_folder))
        available_space = max_length - output_folder_len - 4  # -4 for ".md" and path separator
        
        # Strategy: Truncate each component proportionally
        # Keep first 20 chars + last 10 chars of each component, with hash in middle if needed
        truncated_parts = []
        for part in parts:
            if len(part) > 35:
                # Keep start and end, add hash in middle for uniqueness
                part_hash = hashlib.md5(part.encode()).hexdigest()[:6]
                truncated = f"{part[:20]}_{part_hash}_{part[-10:]}"
                truncated_parts.append(truncated)
            else:
                truncated_parts.append(part)
        
        # Truncate filename similarly
        if len(filename) > 50:
            file_hash = hashlib.md5(filename.encode()).hexdigest()[:6]
            truncated_filename = f"{filename[:30]}_{file_hash}_{filename[-14:]}"
        else:
            truncated_filename = filename
        
        # Build truncated flat filename
        if truncated_parts:
            prefix = '_'.join(truncated_parts)
            result = f"{prefix}_{truncated_filename}.md"
        else:
            result = f"{truncated_filename}.md"
        
        # If still too long, aggressively truncate
        if len(str(self.output_folder / result)) > max_length:
            # Last resort: use hash-based name with minimal context
            full_path = '_'.join(parts + [filename])
            path_hash = hashlib.md5(full_path.encode()).hexdigest()[:12]
            
            # Keep first part of path and filename for context
            context = f"{parts[0][:15] if parts else ''}__{truncated_filename[:30]}"
            result = f"{context}_{path_hash}.md"
        
        return result
    
    def scan_folder(self) -> Tuple[List[Path], int, int]:
        """
        Scan folder for convertible files
        
        Returns:
            Tuple of (files_to_convert, total_files, total_size_bytes)
        """
        files_to_convert = []
        total_files = 0
        total_size = 0
        locked_files = []
        
        logging.info(f"Scanning folder: {self.source_folder}")
        
        # Scan ALL files - no size limit on scanning
        # Files are processed one at a time, so memory usage is minimal
        for file_path in self.source_folder.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:

                # Skip files inside excluded folders (any depth, case-insensitive)
                if self._is_excluded_path(file_path):
                    logging.debug(f"Excluded by folder pattern: {file_path}")
                    continue

                total_files += 1

                # Check if file is accessible before adding to size
                try:
                    total_size += file_path.stat().st_size
                except (PermissionError, OSError) as e:
                    logging.warning(f"Cannot access {file_path.name}: {e}")
                    locked_files.append(file_path.name)
                    continue

                if self._needs_conversion(file_path):
                    files_to_convert.append(file_path)
        
        if locked_files:
            logging.warning(f"Found {len(locked_files)} locked/inaccessible files: {', '.join(locked_files)}")
            logging.warning("These files may be open in another program. Close them and try again.")
        
        logging.info(f"Found {total_files} supported files, {len(files_to_convert)} need conversion")
        return files_to_convert, total_files, total_size
    
    def update_file_metadata(self, source_file: Path, output_file: Path, success: bool, error: Optional[str] = None):
        """Update metadata for a converted file"""
        rel_path = str(source_file.relative_to(self.source_folder))
        
        self.metadata['files'][rel_path] = {
            'hash': self._get_file_hash(source_file) if success else '',
            'output': str(output_file.relative_to(self.output_folder)) if success else '',
            'converted': datetime.now().isoformat(),
            'success': success,
            'error': error,
            'size': source_file.stat().st_size
        }
        
        self.metadata['last_scan'] = datetime.now().isoformat()
    
    def get_output_path(self, source_file: Path) -> Path:
        """Get output path for a source file (flat structure with prefixes)"""
        flat_name = self._create_flat_filename(source_file)
        return self.output_folder / flat_name
    
    def create_index(self, converted_files: List[Tuple[Path, Path, bool]]) -> Path:
        """
        Create master index file with TOC and metadata
        
        Args:
            converted_files: List of (source_file, output_file, success) tuples from current run
        
        Returns:
            Path to index file
        """
        index_path = self.output_folder / '_INDEX.md'
        
        # Build complete file list from metadata (includes all successful conversions, not just current run)
        all_files = []
        for rel_path, file_info in self.metadata['files'].items():
            if file_info.get('success', False):
                source_file = self.source_folder / rel_path
                output_file = self.output_folder / file_info['output']
                if source_file.exists() and output_file.exists():
                    all_files.append((source_file, output_file, True))
        
        # Build file tree from all successfully converted files
        file_tree = {}
        for source_file, output_file, success in all_files:
            rel_path = source_file.relative_to(self.source_folder)
            parts = rel_path.parts
            
            current = file_tree
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = {
                'output': output_file.name,
                'size': source_file.stat().st_size,
                'type': source_file.suffix
            }
        
        # Generate index content
        lines = []
        lines.append(f"# Project Index: {self.source_folder.name}\n")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        lines.append(f"*Source: {self.source_folder}*\n")
        lines.append(f"*Output: {self.output_folder}*\n\n")
        
        # Statistics
        total_files = len(all_files)
        total_size = sum(f[0].stat().st_size for f in all_files)
        lines.append("## Statistics\n\n")
        lines.append(f"- **Total Files Converted:** {total_files}\n")
        lines.append(f"- **Total Size:** {self._format_size(total_size)}\n")
        lines.append(f"- **Output Format:** Flat structure with path prefixes\n\n")
        
        # Table of Contents
        lines.append("## Table of Contents\n\n")
        self._build_toc(file_tree, lines, 0)
        
        # File List with status
        lines.append("\n## File List\n\n")
        lines.append("| Source File | Output File | Size | Type | Status |\n")
        lines.append("|-------------|-------------|------|------|--------|\n")
        
        for source_file, output_file, success in sorted(all_files, key=lambda x: str(x[0])):
            rel_source = source_file.relative_to(self.source_folder)
            size = self._format_size(source_file.stat().st_size)
            file_type = source_file.suffix.upper()[1:]
            status = "✓" if success else "✗"
            if success:
                lines.append(f"| {rel_source} | [{output_file.name}]({output_file.name}) | {size} | {file_type} | {status} |\n")
            else:
                lines.append(f"| {rel_source} | *Failed* | {size} | {file_type} | {status} |\n")
        
        # Add failed files section if any
        failed_files = [(src, self.metadata['files'][str(src.relative_to(self.source_folder))].get('error', 'Unknown error'))
                       for src, out, success in all_files if not success]
        
        if failed_files:
            lines.append("\n## ⚠️ Failed Conversions\n\n")
            for source_file, error in failed_files:
                rel_source = source_file.relative_to(self.source_folder)
                lines.append(f"- **{rel_source}**: {error}\n")
        
        # Write index
        content = ''.join(lines)
        index_path.write_text(content, encoding='utf-8')
        
        logging.info(f"Created index: {index_path}")
        return index_path
    
    def _build_toc(self, tree: Dict, lines: List[str], level: int):
        """Recursively build table of contents"""
        indent = "  " * level
        
        for name, content in sorted(tree.items()):
            if isinstance(content, dict):
                if 'output' in content:
                    # File entry
                    lines.append(f"{indent}- [{name}]({content['output']}) "
                               f"*({self._format_size(content['size'])}, {content['type'].upper()[1:]})*\n")
                else:
                    # Directory entry
                    lines.append(f"{indent}- **{name}/**\n")
                    self._build_toc(content, lines, level + 1)
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def save_checkpoint(self, every: int = 10):
        """Save metadata periodically during a run so progress survives interruptions."""
        self._checkpoint_counter += 1
        if self._checkpoint_counter % every == 0:
            self._save_metadata()

    def finalize(self):
        """Save metadata after processing"""
        self._save_metadata()

# Made with Bob
