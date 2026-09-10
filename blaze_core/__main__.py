from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtQml import QQmlApplicationEngine

from .controller import Controller


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('UploadBlaze')
    app.setOrganizationName('UploadBlaze')
    app.setApplicationVersion('1.0.0')
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    app.setWindowIcon(QIcon(str(root / 'UploadBlazeContent/assets/cloud-logo.svg')))
    state = Path(os.environ.get('UPLOADBLAZE_STATE_DIR') or QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    state.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(state / 'instance.lock'))
    if not lock.tryLock(100):
        # A visible, simple error; never terminate another active backup process.
        QMessageBox.information(None, 'UploadBlaze', 'UploadBlaze is already running. Open its existing window.')
        return 1
    output = Path(os.environ.get('UPLOADBLAZE_OUTPUT_DIR') or QStandardPaths.writableLocation(QStandardPaths.DesktopLocation))
    controller = Controller(state, output)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', controller)
    engine.load(QUrl.fromLocalFile(str(root / 'UploadBlazeContent/App.qml')))
    if not engine.rootObjects():
        QMessageBox.critical(None, 'UploadBlaze', 'UploadBlaze could not load its interface. Please reinstall the app.')
        return 2
    app.aboutToQuit.connect(lock.unlock)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
