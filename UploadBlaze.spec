# Run on each target OS; PyInstaller does not cross-compile.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

root = Path(SPECPATH)
data = [(str(root / 'UploadBlazeContent'), 'UploadBlazeContent')]
for package in ('keyring', 'b2sdk', 'py7zr'):
    data += copy_metadata(package)
icon = str(root / 'packaging' / 'UploadBlaze.icns') if sys.platform == 'darwin' else None
analysis = Analysis(
    ['app.py'], pathex=[str(root)], binaries=[], datas=data,
    hiddenimports=collect_submodules('keyring.backends') + ['PySide6.QtQuick', 'PySide6.QtSvg'],
    hookspath=[], runtime_hooks=[],
    excludes=['pytest', 'tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtWebEngineQuick', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets'],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='UploadBlaze',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=icon)
collection = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name='UploadBlaze')
if sys.platform == 'darwin':
    app = BUNDLE(collection, name='UploadBlaze.app', icon=icon,
                 bundle_identifier='app.uploadblaze.desktop',
                 info_plist={'CFBundleShortVersionString':'1.0.0', 'CFBundleVersion':'1',
                             'NSHighResolutionCapable':True,
                             'NSDocumentsFolderUsageDescription':'Select files to prepare your backup.',
                             'NSDesktopFolderUsageDescription':'Read selected files and save prepared backup archives.'})
