"""
install.py — One-time dependency installer for Project Context Creator
Run once: python install.py
Then run:  python launch_gui.py
"""
import sys
import subprocess
from pathlib import Path

REQUIRED_PYTHON = (3, 8)

def check_python():
    v = sys.version_info
    if v < REQUIRED_PYTHON:
        print(f"ERROR: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required. You have {v.major}.{v.minor}")
        sys.exit(1)

def check_tkinter():
    try:
        import tkinter
        print(f"  ✓ tkinter present")
        return True
    except ImportError:
        print("  ✗ tkinter not found")
        print("    On Windows: re-install Python and check 'tcl/tk and IDLE' in the installer")
        print("    On macOS:   brew install python-tk@3.x")
        print("    On Ubuntu:  sudo apt install python3-tk")
        return False

def install_packages():
    reqs = Path(__file__).parent / "requirements.txt"
    if not reqs.exists():
        print("WARNING: requirements.txt not found — skipping package install")
        return
    print(f"\nInstalling packages from requirements.txt …")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(reqs)],
        capture_output=False,
    )
    if result.returncode != 0:
        print("\nERROR: pip install failed. Check the output above.")
        sys.exit(1)
    print("\n✓ All packages installed.")

def main():
    print("=" * 55)
    print("  Project Context Creator — Setup")
    print("=" * 55)
    print(f"\nPython: {sys.executable}")
    print(f"Version: {sys.version.split()[0]}")

    check_python()

    if not check_tkinter():
        sys.exit(1)

    install_packages()

    print("\n" + "=" * 55)
    print("  Setup complete!")
    print("  Run the GUI with:  python launch_gui.py")
    print("=" * 55)

if __name__ == "__main__":
    main()
