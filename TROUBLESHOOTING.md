# Troubleshooting Guide

Common issues and solutions for the Document to Markdown Converter.

## Installation Issues

### Python Not Found

**Problem:** `python: command not found` or similar error

**Solution:**
1. Install Python from https://www.python.org/downloads/
2. During installation, check "Add Python to PATH"
3. Restart PowerShell/Terminal
4. Verify: `python --version`

### pip Install Fails

**Problem:** `pip install` commands fail or show errors

**Solutions:**
- Update pip: `python -m pip install --upgrade pip`
- Use `python -m pip install package_name` instead of `pip install`
- Check internet connection
- Try with `--user` flag: `pip install --user package_name`

### Import Errors

**Problem:** `ImportError: No module named 'pdf2image'` or similar

**Solution:**
```powershell
# Reinstall all packages
pip install pdf2image pytesseract pillow python-docx python-pptx
```

## ⚠️ Critical: External Tools Are Not Python Packages

**Tesseract OCR** and **Poppler** are system-level tools — they are **not** installed by `pip install -r requirements.txt` and **do not survive a hard drive migration, OS reinstall, or new machine setup.** The Python packages (`pytesseract`, `pdf2image`) are just wrappers — they will install fine but silently fail at runtime if the underlying system tools are missing.

**Symptom:** The tool appears to run normally — PDFs and DOCX files convert fine — but all `.png`, `.jpg`, and scanned PDF files fail with `TesseractNotFoundError`, and some PDFs fail with `Unable to get page count. Is poppler installed?`. You may only notice when checking the log or seeing ~200 files marked as failed.

**After any of these events, reinstall both tools:**
- New machine or hard drive
- Windows reinstall or upgrade
- Profile migration

**Quick verification before running a large batch:**
```powershell
tesseract --version   # Should show tesseract 5.x.x
pdftoppm -v           # Should show poppler version
```

If either command is not recognised, go to Step 4 in `docs/SETUP.md` for full installation instructions, or use winget:
```powershell
winget install UB-Mannheim.TesseractOCR
# Poppler: download from https://github.com/oschwartz10612/poppler-windows/releases/
```

---

## OCR Issues

### Tesseract Not Found

**Problem:** `TesseractNotFoundError` or `tesseract is not recognized`

**Solutions:**

1. **Install Tesseract:**
   - Download: https://github.com/UB-Mannheim/tesseract/wiki
   - Run installer
   - Check "Add to PATH" during installation

2. **Manual PATH Setup:**
   - Search "Environment Variables" in Windows
   - Edit "Path" in System Variables
   - Add: `C:\Program Files\Tesseract-OCR`
   - Restart PowerShell

3. **Verify Installation:**
   ```powershell
   tesseract --version
   ```

4. **Alternative - Set Path in Code:**
   If Tesseract is installed but not in PATH, you can set it manually:
   - Open `converters/pdf_converter.py`
   - Add after imports:
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

### Poor OCR Quality

**Problem:** Text extraction is inaccurate or garbled

**Solutions:**
- Ensure source document has good resolution
- Check if document is in English (tool uses 'eng' language)
- For other languages, modify converter to use appropriate language code
- Some marketing PDFs with complex layouts may not extract perfectly

## PDF Conversion Issues

### Poppler Not Found

**Problem:** `Unable to get page count. Is poppler installed?`

**Solutions:**

1. **Install Poppler:**
   - Download: https://github.com/oschwartz10612/poppler-windows/releases/
   - Download the latest ZIP file (e.g., `Release-24.08.0-0.zip`)
   - Extract to permanent location: `C:\Program Files\poppler`

2. **Add to PATH (CRITICAL - Must include \Library\bin):**
   - Search "Environment Variables" in Windows Start menu
   - Click "Environment Variables" button
   - Under "System variables", find "Path", click "Edit"
   - Click "New"
   - Add: `C:\Program Files\poppler\Library\bin`
   - **IMPORTANT:** Must be `\Library\bin`, NOT just `\poppler`
   - Click "OK" on all windows to save

3. **Restart Everything:**
   - Close PowerShell completely
   - Close the Project Context Creator app
   - Open new PowerShell window
   - Restart the app

4. **Verify Installation:**
   ```powershell
   pdftoppm -v
   ```
   Should show version info. If not, PATH is incorrect.

**Common Mistake:** Adding `C:\Program Files\poppler` instead of `C:\Program Files\poppler\Library\bin` - this will NOT work!

### PDF Won't Convert

**Problem:** Specific PDF fails to convert

**Possible Causes:**
- PDF is password-protected
- PDF is corrupted
- PDF has unusual encoding

**Solutions:**
- Try opening PDF in a reader to verify it's not corrupted
- Remove password protection if present
- Try converting to images first, then use image converter

## GUI Issues

### GUI Won't Start

**Problem:** `python document_converter_gui.py` shows errors

**Solutions:**

1. **Check tkinter:**
   ```powershell
   python -c "import tkinter"
   ```
   If error, reinstall Python with tkinter support

2. **Check converters:**
   ```powershell
   python -c "from converters import convert_pdf_to_markdown"
   ```
   If error, ensure all converter files are in `converters/` directory

3. **Check logs:**
   - Look in `logs/` directory for error details

### Files Not Converting

**Problem:** Files selected but conversion fails

**Check:**
1. File format is supported (PDF, DOCX, PPTX, JPG, PNG)
2. You have write permissions in the file's directory
3. File is not open in another program
4. Check logs in `logs/` directory for specific errors

## Word/PowerPoint Issues

### DOCX/PPTX Won't Convert

**Problem:** Word or PowerPoint files fail to convert

**Solutions:**

1. **Reinstall packages:**
   ```powershell
   pip uninstall python-docx python-pptx
   pip install python-docx python-pptx
   ```

2. **Check file format:**
   - Ensure file is actually .docx/.pptx (not .doc/.ppt)
   - Old formats not supported - save as newer format

3. **File corruption:**
   - Try opening in Word/PowerPoint
   - Save a copy and try converting the copy

## Performance Issues

### Conversion is Slow

**Normal Behavior:**
- Large PDFs with many pages take time
- OCR processing is CPU-intensive
- First conversion may be slower

**Tips:**
- Convert smaller batches
- Close other applications
- Be patient - quality OCR takes time

### High Memory Usage

**Normal for:**
- Large PDFs
- High-resolution images
- Multiple files at once

**Solutions:**
- Convert files in smaller batches
- Close other applications
- Restart application between large batches

## Output Issues

### Markdown File is Empty

**Possible Causes:**
- Source document has no text (only images without OCR)
- Conversion failed silently

**Solutions:**
- Check logs for errors
- Verify source document has readable text
- For image-only PDFs, ensure Tesseract is installed

### Text is Garbled

**Causes:**
- OCR misreading text
- Unusual fonts or formatting
- Non-English text

**Solutions:**
- Check source document quality
- For non-English, modify language setting in converters
- Some formatting may not translate perfectly - this is expected

### Consolidated File Fails to Upload to ICA (IBM Consulting Advantage)

**Symptom:** A consolidated `PROJ_XX_*.md` file gets stuck on "Processing..." in ICA
even though it uploads individually or other files upload fine.

**Known root causes and fixes:**

**1. Extreme line length (DOCX merged cells)**
- **Symptom:** Max line length > 10,000 chars in the file
- **Cause:** `python-docx` returns merged table cells multiple times (once per spanned column)
- **Fix:** Already resolved in v1.8.0 (`docx_converter.py`). Reconvert the source DOCX by
  deleting its `.md` from the markdown folder and clearing its metadata entry.
- **Check:** `python -c "lines=open('file.md').readlines(); print(max(len(l) for l in lines))"`

**2. Raw data dump from XLSX (large row count)**
- **Symptom:** File is extremely large (>10 MB), contains thousands of table rows of
  employee/transaction data
- **Cause:** XLSX sheet with >500 rows converted as full pipe table
- **Fix:** Already resolved in v1.8.0 (`xlsx_converter.py`). Reconvert source XLSX.
  Sheets >10,000 rows are now skipped; sheets 501–10,000 rows get pandas summary.
- **Check:** Look for `*N data rows × M columns*` lines in the converted .md

**3. Unicode character density (PPTX/DOCX with special characters)**
- **Symptom:** File is structurally clean (no long lines, no null bytes) but still fails.
  19,000+ non-ASCII characters in the file.
- **Cause:** Source files contain curly quotes, bullets, en-dashes, non-breaking spaces,
  checkbox symbols (□ U+25A1), ligatures (ﬁ U+FB01), and mojibake sequences.
  ICA's parser appears to have a threshold for non-ASCII character density.
- **Fix:** Unicode normalization not yet implemented. Workaround: run the file through
  a normalizer script that replaces:
  - U+00A0 (non-breaking space) → regular space
  - U+201C/U+201D (curly double quotes) → `"`
  - U+2019 (curly apostrophe) → `'`
  - U+2022 (bullet) → `-`
  - U+2013 (en-dash) → `-`
  - U+FB01 (ﬁ ligature) → `fi`
  - Mojibake sequences (U+00E2 + U+20AC patterns) → cleaned UTF-8
- **Status:** OPEN — implement Unicode normalizer in `consolidate_by_initiative.py`
  or as a post-processing pass per converter.

**Diagnostic script** — run before ICA upload to catch all three issues:
```python
from pathlib import Path
f = Path('PROJ_XX_file.md')
lines = f.read_text(encoding='utf-8').splitlines()
raw = f.read_bytes()
non_ascii = sum(1 for b in raw if b > 127)
max_len = max(len(l) for l in lines)
table_rows = sum(1 for l in lines if l.startswith('|'))
print(f'Lines: {len(lines)}, Max line len: {max_len}, Table rows: {table_rows}, Non-ASCII bytes: {non_ascii}')
# Red flags: max_len > 5000, table_rows > 20000, non_ascii > 10000
```

### Missing Content

**Expected Behavior:**
- Tool extracts text only, not images
- Complex formatting is simplified
- Some layout information is lost

**This is by design** - the tool creates plain text markdown for AI consumption, not a perfect visual replica.

## AI Platform Context and Navigation Issues

### AI Doesn't Know What Files Are in the Collection

**Symptom:** You ask an AI question and it says "I don't have an index file" or gives
answers that only reference one or two files, unaware that 16 others exist.

**Root cause:** RAG systems (ICA, Copilot, etc.) retrieve by semantic similarity.
Index and mapping files are structural — no query semantically matches them, so they
are never retrieved. The AI genuinely cannot see them.

**Three solutions (use in combination):**

**1. Embedded collection map (automatic — already done)**
Every consolidated file now contains an "About This Collection" table listing all
17 files. Any retrieved chunk carries the full directory. No user action needed.

**2. In-chat injection (ad-hoc sessions)**
Paste `_MASTER_INDEX.md` or `_FILE_MAPPING.md` directly into the chat before asking
your question. Explicitly tell the AI: *"Use this index to understand the collection
structure."* Confirmed effective with ICA (tested 2026-07-09).

**3. Agent config / system prompt (permanent fix for ICA)**
In ICA's agent builder, attach `_MASTER_INDEX.md` and `_FILE_MAPPING.md` as
pinned/always-include documents alongside the document collection. These will then
be present in every conversation context automatically.

**Which to use:**
- For one-off questions: in-chat injection is fastest
- For a team using ICA regularly: build a dedicated ICA agent with pinned index files
- The embedded map is always working in the background regardless

### AI Gives Good Answers on One Topic but Can't Cross-Reference Other Files

**Symptom:** AI answers well about one topic (PROJ_12) but doesn't connect it to process
design context in PROJ_02.

**Cause:** RAG retrieval returns the most relevant chunks from one file. Cross-file
reasoning requires either multi-document retrieval or explicit guidance.

**Solutions:**
- Tell the AI explicitly: *"Also check PROJ_02 for related process context"*
- The embedded collection map helps — the AI now knows to suggest other files
- For deep cross-file analysis, consider using Bob/Claude with the full folder
  rather than a RAG platform. Filesystem-native AI can navigate across all 17 files
  proactively without being told.

---

## Getting Help

### Check Logs

Always check the log files in the `logs/` directory for detailed error messages.

### Common Log Locations

- Conversion logs: `logs/conversion_YYYYMMDD_HHMMSS.log`
- Look for ERROR or WARNING messages

### Still Having Issues?

1. Run setup again: `.\setup.ps1`
2. Check all dependencies are installed
3. Restart PowerShell
4. Try with a simple test file first
5. Review the log files for specific errors

## System Requirements

- **OS:** Windows 10/11
- **Python:** 3.7 or higher
- **RAM:** 4GB minimum (8GB recommended for large files)
- **Disk Space:** 500MB for dependencies + space for output files

## Known Limitations

1. **Image-based PDFs:** Require OCR, may not be 100% accurate
2. **Complex layouts:** Tables and multi-column layouts may not preserve structure perfectly
3. **Non-English text:** Default is English OCR, other languages need configuration
4. **Old file formats:** .doc and .ppt not supported (use .docx and .pptx)
5. **Protected files:** Password-protected or DRM files cannot be converted