"""Password fidelity from Qt input events through QML and real encryption."""
from pathlib import Path
import zipfile

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QUrl, Qt
from PySide6.QtGui import QKeyEvent, QInputMethodEvent
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from blaze_core import archives
from blaze_core.controller import Controller
from test_gui import _app, click, settle, ROOT


@pytest.mark.parametrize('password,mode', [
    ('SimplePassword123', 'typed'),
    ('  Spaces stay exactly  ', 'typed'),
    ('Symbols!@#$%^&*()-_=+', 'typed'),
    ('Accenti-àèìòù-🔐-123', 'commit'),
    ('Nonbreaking\u00a0space-123', 'commit'),
    ('Combining-e\u0301-password', 'commit'),
])
def test_password_reaches_encryption_without_added_or_removed_characters(tmp_path, monkeypatch, password, mode):
    source = tmp_path / 'fixture.zip'
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('proof.txt', 'Password fidelity test')
    controller = Controller(tmp_path / 'state', tmp_path / 'prepared')
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', controller)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'UploadBlazeContent/App.qml')))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    QTest.qWait(30)
    controller.addPaths([str(source)])
    for name in ('passwordInput', 'confirmationInput'):
        field = window.findChild(QQuickItem, name)
        field.forceActiveFocus()
        if mode == 'typed':
            for char in password:
                QCoreApplication.sendEvent(window, QKeyEvent(QEvent.KeyPress, 0, Qt.NoModifier, char))
                QCoreApplication.sendEvent(window, QKeyEvent(QEvent.KeyRelease, 0, Qt.NoModifier, char))
        else:
            event = QInputMethodEvent()
            event.setCommitString(password)
            QCoreApplication.sendEvent(field, event)
        assert field.property('text') == password
    received = []
    original = archives.py7zr.SevenZipFile
    def recording_archive(*args, **kwargs):
        if 'password' in kwargs:
            received.append(kwargs['password'])
        return original(*args, **kwargs)
    monkeypatch.setattr(archives.py7zr, 'SevenZipFile', recording_archive)
    click(window, 'protectButton')
    settle(lambda: not controller.busy)
    assert controller.phase == 'Protection verified', controller.lastError
    assert len(received) >= 2
    assert all(value == password for value in received)
    window.close()
    engine.deleteLater()
    _app.processEvents()
