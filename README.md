# Project Context Creator

> Convert project folders into AI-optimized markdown with 95%+ size reduction

**▶ Watch the overview video:** https://www.youtube.com/watch?v=l-0d0rp929o

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What This Does

Converts your project folders (PDFs, Word docs, PowerPoints, images, videos, Box Notes, meeting transcripts) into AI-optimized markdown that's ready to upload to Claude Projects, ChatGPT, IBM Consulting Assistant, or any AI system.

**Key Benefits:**
- 📉 **95%+ size reduction** while preserving all content (tested and verified!)
- 📁 **Flat structure** with path prefixes for easy AI navigation
- 🔄 **Incremental updates** - only converts what changed
- 📋 **Paste Teams transcripts** directly without saving files first
- 🎯 **Automatic filename sanitization** for upload compatibility
- 🎥 **MP4 video transcription** using OpenAI Whisper
- ⏭️ **Skip Options** — skip MP4s, files over a size threshold, or entire folder patterns (Archive, OLD, etc.)
- 🧹 **Orphan cleanup** — automatically removes stale .md files when source documents are deleted
- 💾 **Persistent config** — skip settings saved to config.json between sessions
- 📝 **Box Notes & Markdown** file support
- 🗂️ **AI-powered consolidation** — AI generates a `groups.json` once; tool auto-consolidates on every subsequent run
- 🌍 **Cross-platform** - works on Windows, macOS, and Linux

## Quick Start

### Option A — Download zip (recommended for most users)

1. On this page, click the green **Code** button → **Download ZIP**
2. Unzip anywhere
3. Run once to install Python packages:
   ```bash
   python install.py
   ```
4. Launch the GUI:
   ```bash
   python launch_gui.py
   ```

> **No large installer needed.** Requires [Python 3.8+](https://python.org/downloads/) with tcl/tk (the default installer option).

### Option B — Clone with git

```bash
git clone https://github.com/joefishengineer/Project-Context-Creator.git
cd Project-Context-Creator
python install.py
python launch_gui.py
```

> **Note for Windows users with LibreOffice installed:** LibreOffice can hijack the `python` command.
> `launch_gui.py` detects this automatically and always uses the correct Python installation.

### Install external dependencies (for PDF/image conversion)

### Platform-Specific Setup

#### Windows

**Tesseract OCR:**
1. Download from [Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run installer and ✓ check "Add to PATH"
3. Restart terminal

**Poppler:**
1. Download from [Poppler Windows](https://github.com/oschwartz10612/poppler-windows/releases/)
2. Extract to `C:\Program Files\poppler`
3. Add `C:\Program Files\poppler\Library\bin` to PATH
4. Restart terminal

#### macOS

```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install tesseract poppler python3
```

#### Linux

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils python3 python3-pip

# CentOS/RHEL
sudo yum install tesseract poppler-utils python3 python3-pip

# Fedora
sudo dnf install tesseract poppler-utils python3 python3-pip
```

### Verify Installation

```bash
# Run setup again to verify everything is installed
python setup.py

# Should show all ✓ checks
```

## Features

### Supported Formats

- **Documents:** PDF (hybrid 4-tier extraction), DOCX, PPTX (hybrid 2-tier extraction)
- **Images:** JPG, PNG, JPEG (with OCR)
- **Transcripts:** Teams meeting transcripts (paste or file)
- **Videos:** MP4 (with faster-whisper — timestamped output, model selectable)
- **Video URLs:** YouTube and 1,000+ sites via yt-dlp + faster-whisper (🎬 Video URL mode)
- **Box Notes:** .boxnote files
- **Markdown:** .md files (with metadata)
- **Spreadsheets:** XLSX (enhanced — smart summary engine for large sheets, v1.12.0 ✅ stable)

### PDF Conversion Quality

- **Hybrid 4-Tier Approach:** Intelligent extraction with multiple fallbacks
  - **Tier 1:** PyMuPDF (fast text extraction) - handles 80% of PDFs
  - **Tier 2:** pdfplumber (complex layouts & tables) - handles 15% more
  - **Tier 3:** PyPDF2 (lightweight fallback) - handles edge cases
  - **Tier 4:** OCR (Tesseract) - last resort for scanned PDFs only
- **Performance:** 10-100x faster than OCR-only approach
- **Success Rate:** 85-95% (up from 36% with old OCR-only method)

## Usage

### For Project Folders

1. Launch GUI: `python launch_gui.py`
2. Select "Project Folder" mode
3. (Optional) Set **Skip Options** — check "Skip MP4 video files" and/or "Skip files over X MB" if you want to exclude large files for this run
4. (Optional) Choose custom output location
5. Select your project directory
6. Review scan results (shows file counts and any skipped categories)
7. Click "Convert to Markdown"
8. **First run:** Share `_INDEX.md` with your AI assistant and ask it to create a `groups.json`. Drop it in the `_markdown` folder.
9. **Subsequent runs:** Check **Auto-consolidate** — the tool detects `groups.json` automatically and consolidates after conversion.
10. Upload `_markdown/_CONSOLIDATED/` folder to your AI platform

### For Individual Files

1. Select "Individual Files" mode
2. Choose documents to convert
3. Click "Convert to Markdown"
4. Markdown files saved next to originals

### For Meeting Transcripts

1. Select "Paste Input" mode
2. Paste your Teams transcript
3. Click "Convert to Markdown"
4. Ready for AI analysis

## Output Structure

```
YourProject/
└── _markdown/
    ├── _INDEX.md                    # Master navigation file
    ├── docs_overview.md             # Flat structure with prefixes
    ├── docs_reports_Q4.md
    ├── presentations_deck.md
    └── .conversion_metadata.json    # For incremental updates
```

### The Index File

`_INDEX.md` contains:
- Project statistics (file count, total size)
- File tree visualization
- Table of contents with links
- File metadata (size, type, conversion date)

## Incremental Updates

Run the tool again on the same folder - it automatically:
- ✅ Skips unchanged files (based on file hash)
- ✅ Only converts new or modified files
- ✅ Updates the index
- ✅ Saves time and resources

## Documentation

- **[Setup Guide](docs/SETUP.md)** - Detailed installation
- **[Consolidation Guide](CONSOLIDATION_GUIDE.md)** - Grouping output into a few AI-ready files
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

## Requirements

- **Python 3.7+**
- **Tesseract OCR** - For image and scanned PDF text extraction
- **Poppler utilities** - For PDF to image conversion
- **Python packages** - Auto-installed by `setup.py` (see `requirements.txt`)

## Success Metrics

You'll know it's working when:
- ✅ Project folder converts with 50%+ size reduction
- ✅ Only changed files convert on subsequent runs
- ✅ Master index provides clear navigation
- ✅ Output uploads successfully to your AI assistant
- ✅ You can use the tool confidently in <10 minutes

## Troubleshooting

### Common Issues

**"Tesseract not found"**
- Ensure Tesseract is installed and in PATH
- Restart terminal after installation
- Run `tesseract --version` to verify

**"Poppler not found"**
- Ensure Poppler is installed and in PATH
- On Windows, verify `\Library\bin` is in PATH (not just `\poppler`)
- Run `pdftoppm -v` to verify

**"Module not found" errors**
- Run `python setup.py` to install packages
- Or manually: `pip install -r requirements.txt`

For more help, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Contributing

Contributions welcome — open an issue or pull request.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Project Evolution

- **v1.0.0** - Initial release with document conversion
- **v1.1.0** - Added batch processing for large folders
- **v1.3.0** - MP4 video transcription via Whisper
- **v1.4.0** - Hybrid PDF/PPTX converters (10-100x faster)
- **v1.5.0** - Enhanced XLSX converter rewrite
- **v1.6.0** - Skip Options for large files (MP4 + size threshold)
- **v1.7.0** - Persistent config, orphan cleanup, folder exclusion patterns
- **v1.9.0** - Auto-consolidate panel integrated into GUI
- **v1.10.0** - Collection map embedded in every consolidated file
- **v1.11.0** - AI-authored groups config workflow formalised
- **v1.12.0** - Smart summary engine for large XLSX sheets (✅ stable)
- **v1.13.0** - Video URL mode (YouTube + 1000+ sites), faster-whisper upgrade, MP4 file picker fix

## Support

See **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** for solutions to common issues.

---

**Made with ❤️ for AI-powered workflows**

*Last Updated: 2026-07-22 (v1.13.0)*
