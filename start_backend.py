#!/usr/bin/env python3
"""
🚀 BACKEND STARTUP ONLY
Start the FastAPI backend server for manual testing
Usage: python start_backend.py
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
VENV_PATH = PROJECT_ROOT / "venv"

def main():
    """Start backend server"""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    🚀 PHOTOGRAMMETRY BACKEND SERVER 🚀                     ║
║                     Starting FastAPI on port 8000                          ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Check venv
    if sys.platform == "win32":
        python_exe = VENV_PATH / "Scripts" / "python.exe"
    else:
        python_exe = VENV_PATH / "bin" / "python"
    
    if not python_exe.exists():
        print(f"❌ Python executable not found at {python_exe}")
        print("Please ensure venv is configured correctly")
        sys.exit(1)
    
    print("✅ Python executable found")
    print(f"✅ Project root: {PROJECT_ROOT}")
    
    # Verify backend code exists
    if not (PROJECT_ROOT / "backend" / "main.py").exists():
        print("❌ Backend main.py not found")
        sys.exit(1)
    
    print("✅ Backend code found")
    print("")
    print("Starting backend server...")
    print("-" * 70)
    
    # Start server
    os.chdir(str(PROJECT_ROOT))
    os.execvp(
        str(python_exe),
        [str(python_exe), "-m", "uvicorn", "backend.main:app", "--reload"]
    )

if __name__ == "__main__":
    main()
