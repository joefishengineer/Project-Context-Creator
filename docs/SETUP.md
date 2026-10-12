# Setup Guide - Project Context Creator

Complete installation instructions for Windows, macOS, and Linux.

## Prerequisites

Before you begin, ensure you have:
- **Python 3.7 or higher** installed
- **Git** (optional, for cloning repository)
- **Administrator/sudo access** (for installing system dependencies)
- **Internet connection** (for downloading dependencies)

---

## Step 1: Get the Project

### Option A: Clone with Git (Recommended)

```bash
git clone https://github.com/joefishengineer/Project-Context-Creator.git
cd Project-Context-Creator
```

### Option B: Download ZIP

1. Download ZIP from GitHub
2. Extract to your desired location
3. Open terminal/command prompt in that folder

---

## Step 2: Install Python (if needed)

### Check if Python is Installed

```bash
python --version
# or
python3 --version
```

If you see `Python 3.7` or higher, you're good! Skip to Step 3.

### Windows

1. Download from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **IMPORTANT:** ✓ Check "Add Python to PATH"
4. Click "Install Now"
5. Restart your terminal

### macOS

**Option 1: Homebrew (Recommended)**
```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python3
```

**Option 2: Official Installer**
1. Download from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. Follow the prompts

### Linux

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install python3 python3-pip
```

**CentOS/RHEL:**
```bash
sudo yum install python3 python3-pip
```

**Fedora:**
```bash
sudo dnf install python3 python3-pip
```

---

## Step 3: Run Setup Script

This script will:
- Check your Python version
- Install required Python packages
- Check for Tesseract and Poppler
- Guide you through any missing dependencies

```bash
python setup.py
```

**Expected Output:**
```
==================================================
  Project Context Creator - Setup
==================================================

Platform: Windows 10
Python: 3.9.7

[Checking Python Version]
✓ Python 3.9.7

[Installing Python Packages]
Installing packages from requirements.txt...
✓ Python packages installed successfully

[Checking Tesseract OCR]
✓ Tesseract found: tesseract 5.0.0

[Checking Poppler Utilities]
✓ Poppler utilities found

[Creating Directories]
✓ Created: logs
✓ Created: data/output
✓ Created: data/archive

==================================================
✓ Setup Complete!
==================================================

🚀 You're ready to use Project Context Creator!

To start the GUI:
  python context_creator_gui.py
```

If you see ❌ marks, continue to Step 4.

---

## Step 4: Install External Dependencies

### Tesseract OCR

Tesseract is required for extracting text from images and scanned PDFs.

#### Windows

1. **Download Installer:**
   - Go to [Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki)
   - Download the latest `tesseract-ocr-w64-setup-*.exe`

2. **Run Installer:**
   - Double-click the downloaded file
   - **IMPORTANT:** ✓ Check "Add to PATH" during installation
   - Complete the installation

3. **Verify Installation:**
   ```powershell
   # Close and reopen PowerShell, then run:
   tesseract --version
   ```
   
   Should show: `tesseract 5.x.x`

**Troubleshooting:**
- If "tesseract not found", manually add to PATH:
  1. Search "Environment Variables" in Windows
  2. Edit "Path" in System Variables
  3. Add: `C:\Program Files\Tesseract-OCR`
  4. Restart terminal

#### macOS

```bash
# Using Homebrew (easiest)
brew install tesseract

# Verify
tesseract --version
```

**If you don't have Homebrew:**
```bash
# Install Homebrew first
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Then install Tesseract
brew install tesseract
```

#### Linux

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr

# Verify
tesseract --version
```

**CentOS/RHEL:**
```bash
sudo yum install tesseract

# Verify
tesseract --version
```

**Fedora:**
```bash
sudo dnf install tesseract

# Verify
tesseract --version
```

---

### Poppler Utilities

Poppler is required for converting PDF pages to images.

#### Windows

1. **Download Poppler:**
   - Go to [Poppler Windows Releases](https://github.com/oschwartz10612/poppler-windows/releases/)
   - Download the latest `Release-*` ZIP file (e.g., `Release-24.02.0-0.zip`)

2. **Extract Files:**
   - Extract the ZIP file
   - Move the extracted folder to: `C:\Program Files\poppler`
   - Your structure should be: `C:\Program Files\poppler\Library\bin\`

3. **Add to PATH:**
   - Search "Environment Variables" in Windows Start menu
   - Click "Environment Variables" button
   - Under "System variables", find and select "Path"
   - Click "Edit"
   - Click "New"
   - Add: `C:\Program Files\poppler\Library\bin`
   - **CRITICAL:** Must be `\Library\bin`, not just `\poppler`
   - Click OK on all windows

4. **Verify Installation:**
   ```powershell
   # Close and reopen PowerShell, then run:
   pdftoppm -v
   ```
   
   Should show version information

**Troubleshooting:**
- If "pdftoppm not found", verify PATH includes `\Library\bin`
- Restart terminal after adding to PATH
- Check that `pdftoppm.exe` exists in the bin folder

#### macOS

```bash
# Using Homebrew (easiest)
brew install poppler

# Verify
pdftoppm -v
```

#### Linux

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install poppler-utils

# Verify
pdftoppm -v
```

**CentOS/RHEL:**
```bash
sudo yum install poppler-utils

# Verify
pdftoppm -v
```

**Fedora:**
```bash
sudo dnf install poppler-utils

# Verify
pdftoppm -v
```

---

## Step 5: Verify Complete Setup

Run the setup script again to verify everything is installed:

```bash
python setup.py
```

You should see all ✓ checks:
```
✓ Python 3.9.7
✓ Python packages installed successfully
✓ Tesseract found
✓ Poppler utilities found
```

---

## Step 6: Launch the Application

```bash
python context_creator_gui.py
```

The GUI should open. If you see the interface, congratulations! 🎉

---

## Common Issues

### "Python not found"

**Windows:**
- Reinstall Python and check "Add to PATH"
- Or manually add Python to PATH

**macOS/Linux:**
- Use `python3` instead of `python`
- Install Python using package manager

### "pip not found"

```bash
# Windows
python -m ensurepip --upgrade

# macOS/Linux
python3 -m ensurepip --upgrade
```

### "Permission denied" errors

**macOS/Linux:**
```bash
# Use sudo for system-wide installation
sudo apt-get install tesseract-ocr

# Or use --user flag for pip
pip install --user -r requirements.txt
```

### "Module not found" after installation

```bash
# Reinstall packages
pip install -r requirements.txt --force-reinstall

# Or install individually
pip install pdf2image pytesseract pillow python-docx python-pptx
```

### Tesseract or Poppler not in PATH

**Windows:**
1. Find where the program is installed
2. Add that directory to System PATH
3. Restart terminal

**macOS/Linux:**
```bash
# Check if installed
which tesseract
which pdftoppm

# If not found, reinstall
brew install tesseract poppler  # macOS
sudo apt-get install tesseract-ocr poppler-utils  # Linux
```

---

## Optional: Video Transcription

For MP4 video transcription support, install OpenAI Whisper:

```bash
pip install openai-whisper
```

**Note:** Whisper requires significant disk space (~1-5 GB) and works best with a GPU.

---

## Next Steps

1. ✅ Setup complete? Great!
2. 📖 Read [USAGE.md](USAGE.md) to learn how to use the tool
3. 🚀 Start converting your project folders!

---

## Getting Help

- **Troubleshooting:** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Issues:** [GitHub Issues](https://github.com/joefishengineer/Project-Context-Creator/issues)
- **Questions:** [GitHub Issues](https://github.com/joefishengineer/Project-Context-Creator/issues)

---

*Last Updated: 2026-06-24*