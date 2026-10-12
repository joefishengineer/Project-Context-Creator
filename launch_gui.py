"""
launch_gui.py — Project Context Creator launcher
Run with ANY Python: python launch_gui.py

Finds a Python that has tkinter, then launches the GUI.
Works on Windows and macOS regardless of virtualenvs or LibreOffice
having hijacked the system 'python' command.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

HERE = Path(__file__).parent
GUI  = str(HERE / "context_creator_gui_v2.py")


def _clean_env():
    """
    Return a copy of os.environ with LibreOffice / venv Python overrides removed.
    LibreOffice sets PYTHONHOME and PYTHONPATH pointing at its own stdlib,
    which poisons any Python subprocess we spawn.
    """
    env = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH"):
        env.pop(key, None)
    return env


def _has_tkinter(python_exe):
    """Return True if the given interpreter can import tkinter."""
    try:
        result = subprocess.run(
            [python_exe, "-c", "import tkinter"],
            capture_output=True, timeout=8,
            env=_clean_env(),
        )
        return result.returncode == 0
    except Exception:
        return False


def _find_python():
    """
    Return the path to a Python ≥ 3.8 that has tkinter.
    Searches in order — newest Windows user-install first, then PATH fallbacks.
    The current sys.executable is tried last so LibreOffice / venv Pythons
    that lack tkinter don't shadow a proper system install.
    """
    candidates = []

    # ── Windows: scan LOCALAPPDATA user installs (newest first) ──────────────
    local_programs = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"
    for d in sorted(local_programs.glob("Python/Python3*"), reverse=True):
        exe = d / "python.exe"
        if exe.exists() and exe.stat().st_size > 0:
            candidates.append(str(exe))

    # ── Windows: scan ProgramFiles system-wide installs ───────────────────────
    for prog in ["PROGRAMFILES", "PROGRAMFILES(X86)"]:
        root = Path(os.environ.get(prog, ""))
        for d in sorted(root.glob("Python3*"), reverse=True):
            exe = d / "python.exe"
            if exe.exists() and exe.stat().st_size > 0:
                candidates.append(str(exe))

    # ── Windows: py launcher ──────────────────────────────────────────────────
    py = shutil.which("py")
    if py:
        candidates.append(py)

    # ── macOS / Linux: common names on PATH ───────────────────────────────────
    for name in ("python3.13", "python3.12", "python3.11", "python3.10",
                 "python3.9", "python3.8", "python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    # ── Last resort: current interpreter ─────────────────────────────────────
    candidates.append(sys.executable)

    seen = set()
    for exe in candidates:
        try:
            key = str(Path(exe).resolve())
        except Exception:
            key = exe
        if key in seen:
            continue
        seen.add(key)
        if _has_tkinter(exe):
            return exe

    return None


def main():
    python = _find_python()
    if python is None:
        print("ERROR: No Python with tkinter found.")
        print("Install Python from https://python.org and ensure 'tcl/tk' is included.")
        sys.exit(1)

    print(f"Using Python: {python}")

    # Strip LibreOffice env-var poison before handing off
    env = _clean_env()

    # subprocess.run handles paths with spaces correctly on Windows
    sys.exit(subprocess.run([python, GUI] + sys.argv[1:], env=env).returncode)


if __name__ == "__main__":
    main()
