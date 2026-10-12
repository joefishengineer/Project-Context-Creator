#!/usr/bin/env python3
"""
File Consolidator - JSON Config Driven
Consolidates a flat folder of markdown files into grouped mega-documents
guided by a JSON config file that defines groups and filename prefix rules.

Usage:
    python consolidate_by_initiative.py <source_folder> [output_folder] [--config config.json]

A groups config is required. Without one, consolidation is skipped.
"""

import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ---------------------------------------------------------------------------
# JSON-config driven consolidator
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Unicode normalizer
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """
    Normalize Unicode characters to clean ASCII-safe equivalents.

    ICA (IBM Consulting Advantage) and many markdown parsers have thresholds
    for non-ASCII character density. Source PPTX/DOCX files frequently contain
    typographic characters (curly quotes, bullets, en-dashes), checkbox symbols,
    ligatures, and mojibake sequences that cause upload failures.

    This function is applied to every source file's content before it is written
    into a consolidated output file.
    """
    # --- Straight replacements: typographic → ASCII ---
    replacements = [
        ('\u00a0', ' '),   # non-breaking space → regular space
        ('\u201c', '"'),   # left double quotation mark
        ('\u201d', '"'),   # right double quotation mark
        ('\u2018', "'"),   # left single quotation mark
        ('\u2019', "'"),   # right single quotation mark
        ('\u2013', '-'),   # en dash
        ('\u2014', '--'),  # em dash
        ('\u2022', '-'),   # bullet •
        ('\u25a1', '[]'),  # white square □ (checkbox)
        ('\u25a0', '[x]'), # black square ■ (checked checkbox)
        ('\u2026', '...'), # horizontal ellipsis …
        ('\ufb01', 'fi'),  # fi ligature ﬁ
        ('\ufb02', 'fl'),  # fl ligature ﬂ
        ('\u00e9', 'e'),   # é
        ('\u00e0', 'a'),   # à
        ('\u00e8', 'e'),   # è
        ('\u00ea', 'e'),   # ê
        ('\u00f4', 'o'),   # ô
        ('\u00fb', 'u'),   # û
        ('\u00e7', 'c'),   # ç
        ('\u00fc', 'u'),   # ü
        ('\u00e4', 'a'),   # ä
        ('\u00f6', 'o'),   # ö
        ('\u00df', 'ss'),  # ß
        ('\u00ae', '(R)'), # ® registered
        ('\u00a9', '(C)'), # © copyright
        ('\u2122', '(TM)'),# ™ trademark
        ('\u00b0', ' deg'),# ° degree
        ('\u00b7', '-'),   # middle dot ·
        ('\u2010', '-'),   # hyphen ‐
        ('\u2011', '-'),   # non-breaking hyphen ‑
        ('\u2012', '-'),   # figure dash ‒
        ('\u2015', '--'),  # horizontal bar ―
        ('\u00d7', 'x'),   # multiplication sign ×
        ('\u00f7', '/'),   # division sign ÷
        ('\u2192', '->'),  # rightwards arrow →
        ('\u2190', '<-'),  # leftwards arrow ←
        ('\u2194', '<->'), # left right arrow ↔
        ('\u25b6', '>'),   # black right-pointing triangle ▶
        ('\u25ba', '>'),   # black right-pointing pointer ►
    ]
    for src, dst in replacements:
        text = text.replace(src, dst)

    # --- Mojibake cleanup: UTF-8 bytes misread as latin-1 ---
    # Pattern: â€" → – (en-dash mojibake), â€™ → ' etc.
    # These arise when a UTF-8 file was read as cp1252 at some point.
    # Re-encode as latin-1 bytes then decode as UTF-8 where possible.
    import re
    def fix_mojibake(text: str) -> str:
        try:
            # Attempt to fix latin1-encoded UTF-8 sequences
            return text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
        except Exception:
            return text

    # Only attempt mojibake fix if suspicious sequences are present
    if '\u00e2' in text and ('\u20ac' in text or '\u0080' in text):
        text = fix_mojibake(text)
        # Run replacements again after mojibake fix (may have uncovered more)
        for src, dst in replacements:
            text = text.replace(src, dst)

    return text


class JsonConsolidator:
    """
    Consolidates markdown files using a JSON config that defines groups and
    the filename-prefix rules that assign files to each group.

    Config schema:
    {
      "project_name": "Example Project",
      "description": "...",
      "groups": [
        {
          "code": "PROJ_01",
          "name": "Knowledge Transfer",
          "filename": "PROJ_01_KNOWLEDGE_TRANSFER.md",
          "prefixes": ["Knowledge Transfer_", ...]
        },
        ...
      ]
    }

    Matching rules
    --------------
    Each file is tested against every group's prefix list in order.  The
    FIRST matching group wins.  Longer (more specific) prefixes beat shorter
    ones because the JSON author controls the order.

    A prefix of "BPO Transition_" (trailing underscore) acts as a catch-all
    for any file whose name starts with that string and has not been claimed
    by a more specific group above it.
    """

    def __init__(self, source_folder: Path, output_folder: Path, config: dict):
        self.source_folder = Path(source_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

        self.project_name = config.get("project_name", "Project")
        self.description = config.get("description", "")
        self.groups = config["groups"]  # ordered list
        self.exclude_prefixes = config.get("exclude_prefixes", [])

        self.stats = {
            "total_files": 0,
            "by_group": defaultdict(int),
            "uncategorized": 0,
        }

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, filename: str) -> Optional[str]:
        """Return the group code for filename, None if uncategorized, or 'EXCLUDE' if excluded."""
        for ep in self.exclude_prefixes:
            if filename.startswith(ep):
                return "EXCLUDE"
        for group in self.groups:
            for prefix in group["prefixes"]:
                if filename.startswith(prefix):
                    return group["code"]
        return None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def consolidate(self):
        logging.info(f"Starting consolidation from: {self.source_folder}")
        logging.info(f"Output folder: {self.output_folder}")
        logging.info(f"Project: {self.project_name}")

        md_files = sorted(
            [f for f in self.source_folder.glob("*.md") if not f.name.startswith("_")],
            key=lambda x: x.name,
        )
        self.stats["total_files"] = len(md_files)
        logging.info(f"Found {len(md_files)} markdown files to consolidate")

        # Bucket files
        buckets: Dict[str, List[Path]] = defaultdict(list)
        uncategorized: List[Path] = []

        for f in md_files:
            code = self._classify(f.name)
            if code == "EXCLUDE":
                logging.debug(f"Excluded from consolidation: {f.name}")
            elif code:
                buckets[code].append(f)
                self.stats["by_group"][code] += 1
            else:
                uncategorized.append(f)
                self.stats["uncategorized"] += 1

        # Write group files (preserve JSON order)
        logging.info("\n=== Creating Group Files ===")
        group_lookup = {g["code"]: g for g in self.groups}
        for group in self.groups:
            code = group["code"]
            if code in buckets:
                self._write_group_file(group, buckets[code])
            else:
                logging.info(f"  (skipped {group['filename']} – no files matched)")

        # Write uncategorized
        if uncategorized:
            logging.info("\n=== Creating Uncategorized File ===")
            self._write_uncategorized(uncategorized)

        # Write master index and mapping
        logging.info("\n=== Creating Master Index ===")
        self._write_master_index(buckets, uncategorized, group_lookup)
        self._write_file_mapping(buckets, uncategorized, group_lookup)

        self._print_stats(group_lookup)

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    def _build_collection_map(self, current_code: str) -> str:
        """
        Build a compact collection map block listing all groups in this project.
        Embedded at the top of every consolidated file so that any AI reading
        even a single retrieved chunk knows the full structure of the collection
        and can direct users to the right file — regardless of whether an index
        file was retrieved by the RAG system.
        """
        lines = []
        lines.append("## About This Collection\n\n")
        lines.append(
            f"This file is part of the **{self.project_name}** knowledge base. "
            f"The collection is split into {len(self.groups)} topic files. "
            f"If a topic you need is not in this file, refer to the table below "
            f"to identify the correct file and ask specifically about it.\n\n"
        )
        lines.append("| Code | File | Topics Covered |\n")
        lines.append("|------|------|----------------|\n")
        for g in self.groups:
            marker = " **(this file)**" if g["code"] == current_code else ""
            lines.append(
                f"| {g['code']} | {g['filename']} | {g['name']}{marker} |\n"
            )
        lines.append("\n---\n\n")
        return "".join(lines)

    def _write_group_file(self, group: dict, files: List[Path]):
        out = self.output_folder / group["filename"]
        logging.info(f"Creating {group['filename']} ({len(files)} files)")

        lines = []
        lines.append(f"# {group['code']}: {group['name']}\n\n")
        lines.append(f"**Consolidated from {len(files)} source files**  \n")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        lines.append(f"**Project**: {self.project_name}\n\n")

        # Collection map — helps RAG systems that only retrieve this file
        # understand the full collection structure
        lines.append(self._build_collection_map(group["code"]))

        # Table of contents
        lines.append("## Table of Contents\n\n")
        for idx, fp in enumerate(files, 1):
            lines.append(f"{idx}. [{fp.stem}](#{idx}-{self._slugify(fp.stem)})\n")
        lines.append("\n---\n\n")

        # Content sections
        for idx, fp in enumerate(files, 1):
            lines.append(f"## {idx}. {fp.stem}\n\n")
            lines.append(f"**Source File**: `{fp.name}`\n\n")
            try:
                content = fp.read_text(encoding="utf-8")
                lines.append(_normalize_text(content))
            except Exception as e:
                logging.warning(f"  Error reading {fp.name}: {e}")
                lines.append(f"*Error reading file: {e}*\n")
            lines.append("\n\n---\n\n")

        out.write_text("".join(lines), encoding="utf-8")
        logging.info(f"  ✓ {out.name}  ({out.stat().st_size:,} bytes)")

    def _write_uncategorized(self, files: List[Path]):
        out = self.output_folder / "MISC_UNCATEGORIZED.md"
        logging.info(f"Creating MISC_UNCATEGORIZED.md ({len(files)} files)")

        lines = []
        lines.append("# Miscellaneous & Uncategorized Documents\n\n")
        lines.append(f"**Consolidated from {len(files)} source files**  \n")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for idx, fp in enumerate(files, 1):
            lines.append(f"## {idx}. {fp.stem}\n\n")
            lines.append(f"**Source File**: `{fp.name}`\n\n")
            try:
                content = fp.read_text(encoding="utf-8")
                lines.append(_normalize_text(content))
            except Exception as e:
                lines.append(f"*Error reading file: {e}*\n")
            lines.append("\n\n---\n\n")

        out.write_text("".join(lines), encoding="utf-8")
        logging.info(f"  ✓ {out.name}")

    def _write_master_index(self, buckets, uncategorized, group_lookup):
        out = self.output_folder / "_MASTER_INDEX.md"
        total_groups = sum(1 for g in self.groups if g["code"] in buckets)
        total_outputs = total_groups + (1 if uncategorized else 0)

        lines = []
        lines.append(f"# {self.project_name} – Master Index\n\n")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        lines.append(f"**Total Source Files**: {self.stats['total_files']}  \n")
        lines.append(f"**Consolidated Output Files**: {total_outputs}\n\n")
        if self.description:
            lines.append(f"> {self.description}\n\n")

        lines.append("## Groups\n\n")
        lines.append("| Code | Name | File | Source Files |\n")
        lines.append("|------|------|------|--------------|\n")
        for group in self.groups:
            code = group["code"]
            if code in buckets:
                count = len(buckets[code])
                lines.append(f"| {code} | {group['name']} | `{group['filename']}` | {count} |\n")
        if uncategorized:
            lines.append(f"| — | Miscellaneous | `MISC_UNCATEGORIZED.md` | {len(uncategorized)} |\n")
        lines.append("\n")

        lines.append("## Quick Start\n\n")
        for group in self.groups:
            if group["code"] in buckets:
                lines.append(f"- **{group['name']}** → `{group['filename']}`\n")
        lines.append("\n")

        lines.append("## Statistics\n\n")
        lines.append(f"- **Total source files processed**: {self.stats['total_files']}\n")
        for group in self.groups:
            code = group["code"]
            if code in buckets:
                lines.append(f"- **{group['name']}**: {len(buckets[code])} files\n")
        if uncategorized:
            lines.append(f"- **Uncategorized**: {len(uncategorized)} files\n")
        lines.append(f"- **Total output files**: {total_outputs}\n")

        out.write_text("".join(lines), encoding="utf-8")
        logging.info(f"  ✓ {out.name}")

    def _write_file_mapping(self, buckets, uncategorized, group_lookup):
        out = self.output_folder / "_FILE_MAPPING.md"
        lines = []
        lines.append(f"# File Mapping: Source → Consolidated\n\n")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for group in self.groups:
            code = group["code"]
            if code not in buckets:
                continue
            lines.append(f"## {group['filename']}\n\n")
            for fp in buckets[code]:
                lines.append(f"- `{fp.name}`\n")
            lines.append("\n")

        if uncategorized:
            lines.append("## MISC_UNCATEGORIZED.md\n\n")
            for fp in uncategorized:
                lines.append(f"- `{fp.name}`\n")

        out.write_text("".join(lines), encoding="utf-8")
        logging.info(f"  ✓ {out.name}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        text = re.sub(r"^-+|-+$", "", text)
        return text

    def _print_stats(self, group_lookup):
        logging.info("\n" + "=" * 60)
        logging.info("CONSOLIDATION COMPLETE")
        logging.info("=" * 60)
        logging.info(f"Total source files processed: {self.stats['total_files']}")
        logging.info("\nFiles by group:")
        for group in self.groups:
            code = group["code"]
            if code in self.stats["by_group"]:
                logging.info(f"  {code} {group['name']}: {self.stats['by_group'][code]} files")
        if self.stats["uncategorized"]:
            logging.info(f"\nUncategorized files: {self.stats['uncategorized']}")
        logging.info(f"\nOutput folder: {self.output_folder}")
        logging.info("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Consolidate markdown files into grouped mega-documents."
    )
    parser.add_argument("source_folder", help="Folder containing flat .md files")
    parser.add_argument(
        "output_folder",
        nargs="?",
        default=None,
        help="Destination folder (default: <source_folder>/_CONSOLIDATED)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a JSON grouping config file (e.g. my_groups.json). "
             "Required; without it consolidation is skipped.",
    )
    args = parser.parse_args()

    source_folder = Path(args.source_folder)
    if not source_folder.exists():
        print(f"Error: Source folder not found: {source_folder}")
        raise SystemExit(1)

    output_folder = Path(args.output_folder) if args.output_folder else source_folder / "_CONSOLIDATED"

    print(f"\n{'='*60}")
    print("FILE CONSOLIDATOR")
    print(f"{'='*60}\n")

    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {config_path}")
            raise SystemExit(1)
        with open(config_path, encoding="utf-8-sig") as fh:
            config = json.load(fh)
        print(f"Mode: JSON config  ({config_path.name})")
        consolidator = JsonConsolidator(source_folder, output_folder, config)
    else:
        print("No groups config supplied (--config) - skipping consolidation.")
        print("See CONSOLIDATION_GUIDE.md for how to create one.")
        return

    consolidator.consolidate()

    print(f"\nConsolidation complete!")
    print(f"Output files: {output_folder}\n")


if __name__ == "__main__":
    main()

# Made with Bob
