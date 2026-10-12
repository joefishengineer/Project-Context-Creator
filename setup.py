#!/usr/bin/env python3
"""
Project Context Creator - Cross-Platform Setup Script
Checks dependencies and guides installation for Windows, macOS, and Linux
"""

import sys
import subprocess
import platform
import shutil
from pathlib import Path

# Fix Unicode output for Windows console
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_section(text):
    """Print a section header"""
    print(f"\n[{text}]")


def check_python_version():
    """Ensure Python 3.7+"""
    print_section("Checking Python Version")
    version = sys.version_info
    if version < (3, 7):
        print(f"❌ Python 3.7+ required (you have {version.major}.{version.minor})")
        print("\nPlease install Python 3.7 or higher:")
        print_python_install_instructions()
        sys.exit(1)
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")


def install_python_packages():
    """Install required Python packages from requirements.txt"""
    print_section("Installing Python Packages")
    
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ requirements.txt not found!")
        print("Creating requirements.txt...")
        create_requirements_file()
    
    print("Installing packages from requirements.txt...")
    print("(This may take a few minutes)")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ Python packages installed successfully")
            return True
        else:
            print("⚠ Some packages may have failed to install")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error installing packages: {e}")
        return False


def create_requirements_file():
    """Create requirements.txt if it doesn't exist"""
    requirements_content = """# Core dependencies
pdf2image>=1.16.0
pytesseract>=0.3.10
Pillow>=9.0.0
python-docx>=0.8.11
python-pptx>=0.6.21
openpyxl>=3.0.10

# Hybrid PDF converters (v1.4.0+)
PyMuPDF>=1.23.0
pdfplumber>=0.10.0
PyPDF2>=3.0.0

# Optional: Video transcription
# openai-whisper>=20230314
"""
    requirements_file = Path(__file__).parent / "requirements.txt"
    requirements_file.write_text(requirements_content)
    print("✓ Created requirements.txt")


def check_tesseract():
    """Check if Tesseract OCR is installed"""
    print_section("Checking Tesseract OCR")
    
    if shutil.which("tesseract"):
        try:
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True,
                text=True
            )
            version_line = result.stdout.split('\n')[0]
            print(f"✓ Tesseract found: {version_line}")
            return True
        except Exception:
            print("✓ Tesseract found (version check failed)")
            return True
    else:
        print("❌ Tesseract OCR not found!")
        print_tesseract_instructions()
        return False


def check_poppler():
    """Check if Poppler utilities are installed"""
    print_section("Checking Poppler Utilities")
    
    if shutil.which("pdftoppm"):
        print("✓ Poppler utilities found")
        return True
    else:
        print("❌ Poppler utilities not found!")
        print_poppler_instructions()
        return False


def print_python_install_instructions():
    """Print Python installation instructions for current platform"""
    os_type = platform.system()
    
    print("\nPython Installation:")
    if os_type == "Windows":
        print("  1. Download from: https://www.python.org/downloads/")
        print("  2. Run installer")
        print("  3. ✓ Check 'Add Python to PATH' during installation")
        print("  4. Restart terminal after installation")
    elif os_type == "Darwin":  # macOS
        print("  Option 1 (Homebrew - Recommended):")
        print("    brew install python3")
        print("\n  Option 2 (Official Installer):")
        print("    Download from: https://www.python.org/downloads/")
    else:  # Linux
        print("  Ubuntu/Debian:")
        print("    sudo apt-get update")
        print("    sudo apt-get install python3 python3-pip")
        print("\n  CentOS/RHEL:")
        print("    sudo yum install python3 python3-pip")
        print("\n  Fedora:")
        print("    sudo dnf install python3 python3-pip")


def print_tesseract_instructions():
    """Print Tesseract installation instructions for current platform"""
    os_type = platform.system()
    
    print("\n📋 Tesseract OCR Installation:")
    print("-" * 60)
    
    if os_type == "Windows":
        print("Windows:")
        print("  1. Download installer from:")
        print("     https://github.com/UB-Mannheim/tesseract/wiki")
        print("  2. Run the installer (tesseract-ocr-w64-setup-*.exe)")
        print("  3. During installation:")
        print("     ✓ Check 'Add to PATH'")
        print("  4. Restart your terminal/PowerShell")
        print("  5. Verify: tesseract --version")
        
    elif os_type == "Darwin":  # macOS
        print("macOS:")
        print("  Using Homebrew (recommended):")
        print("    brew install tesseract")
        print("\n  Verify installation:")
        print("    tesseract --version")
        print("\n  If you don't have Homebrew:")
        print("    Install from: https://brew.sh")
        
    else:  # Linux
        print("Linux:")
        print("  Ubuntu/Debian:")
        print("    sudo apt-get update")
        print("    sudo apt-get install tesseract-ocr")
        print("\n  CentOS/RHEL:")
        print("    sudo yum install tesseract")
        print("\n  Fedora:")
        print("    sudo dnf install tesseract")
        print("\n  Verify installation:")
        print("    tesseract --version")


def print_poppler_instructions():
    """Print Poppler installation instructions for current platform"""
    os_type = platform.system()
    
    print("\n📋 Poppler Utilities Installation:")
    print("-" * 60)
    
    if os_type == "Windows":
        print("Windows:")
        print("  1. Download from:")
        print("     https://github.com/oschwartz10612/poppler-windows/releases/")
        print("  2. Download the latest 'Release-*' ZIP file")
        print("  3. Extract to: C:\\Program Files\\poppler")
        print("  4. Add to Windows PATH:")
        print("     a. Search 'Environment Variables' in Windows")
        print("     b. Click 'Environment Variables' button")
        print("     c. Under 'System variables', find and edit 'Path'")
        print("     d. Click 'New' and add:")
        print("        C:\\Program Files\\poppler\\Library\\bin")
        print("     e. Click OK on all windows")
        print("  5. Restart your terminal/PowerShell")
        print("  6. Verify: pdftoppm -v")
        
    elif os_type == "Darwin":  # macOS
        print("macOS:")
        print("  Using Homebrew (recommended):")
        print("    brew install poppler")
        print("\n  Verify installation:")
        print("    pdftoppm -v")
        print("\n  If you don't have Homebrew:")
        print("    Install from: https://brew.sh")
        
    else:  # Linux
        print("Linux:")
        print("  Ubuntu/Debian:")
        print("    sudo apt-get update")
        print("    sudo apt-get install poppler-utils")
        print("\n  CentOS/RHEL:")
        print("    sudo yum install poppler-utils")
        print("\n  Fedora:")
        print("    sudo dnf install poppler-utils")
        print("\n  Verify installation:")
        print("    pdftoppm -v")


def create_directories():
    """Create necessary directories"""
    print_section("Creating Directories")
    
    project_dir = Path(__file__).parent
    directories = [
        project_dir / "logs",
        project_dir / "data" / "output",
        project_dir / "data" / "archive"
    ]
    
    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✓ Created: {directory.relative_to(project_dir)}")
        else:
            print(f"✓ Exists: {directory.relative_to(project_dir)}")


def print_summary(python_ok, tesseract_ok, poppler_ok):
    """Print setup summary"""
    print_header("Setup Summary")
    
    print("\nComponent Status:")
    print(f"  Python 3.7+:        {'✓ INSTALLED' if python_ok else '❌ NOT INSTALLED'}")
    print(f"  Python packages:    {'✓ INSTALLED' if python_ok else '❌ NOT INSTALLED'}")
    print(f"  Tesseract OCR:      {'✓ INSTALLED' if tesseract_ok else '❌ NOT INSTALLED'}")
    print(f"  Poppler utilities:  {'✓ INSTALLED' if poppler_ok else '❌ NOT INSTALLED'}")
    
    all_ok = python_ok and tesseract_ok and poppler_ok
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ Setup Complete!")
        print("=" * 60)
        print("\n🚀 You're ready to use Project Context Creator!")
        print("\nTo start the GUI:")
        print("  python context_creator_gui.py")
        print("\nFor help:")
        print("  See README.md for usage instructions")
    else:
        print("⚠ Setup Incomplete")
        print("=" * 60)
        print("\n⚠ Some dependencies are missing.")
        print("\nNext steps:")
        print("  1. Install missing dependencies (see instructions above)")
        print("  2. Restart your terminal")
        print("  3. Run this setup script again: python setup.py")
        print("\nFor detailed help:")
        print("  See docs/SETUP.md")
    print("=" * 60)


def main():
    """Main setup process"""
    print_header("Project Context Creator - Setup")
    print(f"\nPlatform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")
    
    # Check Python version
    check_python_version()
    
    # Install Python packages
    python_ok = install_python_packages()
    
    # Check external dependencies
    tesseract_ok = check_tesseract()
    poppler_ok = check_poppler()
    
    # Create directories
    create_directories()
    
    # Print summary
    print_summary(python_ok, tesseract_ok, poppler_ok)
    
    # Exit code
    sys.exit(0 if (python_ok and tesseract_ok and poppler_ok) else 1)


if __name__ == "__main__":
    main()

# Made with Bob
