"""Build the desktop bundle using this platform's Python environment."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                str(root / 'UploadBlaze.spec')], cwd=root, check=True)
