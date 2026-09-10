"""Real QML events and real archive services; no network or real credentials."""
import json
import time
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Qt, QPointF
from PySide6.QtQuick import QQuickWindow, QQuickItem
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from blaze_core.controller import Controller

_app = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[1]


def settle(predicate, timeout=15):
    until = time.monotonic() + timeout
    while not predicate() and time.monotonic() < until:
        _app.processEvents()
        QTest.qWait(10)
    assert predicate()


def click(window, name):
    item = window.findChild(QQuickItem, name)
    assert item and item.isEnabled(), name
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
    _app.processEvents()


def test_real_gui_archive_flow_and_separate_settings(tmp_path, monkeypatch):
    controller = Controller(tmp_path / 'state', tmp_path / 'prepared')
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(x.toString() for x in items))
    engine.rootContext().setContextProperty('backend', controller)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'UploadBlazeContent/App.qml')))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    QTest.qWait(100)
    assert (window.width(), window.height()) == (569, 710)
    original = tmp_path / 'notes.txt'
    original.write_text('Original content stays unchanged.\n')
    controller.addPaths([str(original)])
    click(window, 'zipButton')
    settle(lambda: not controller.busy)
    assert controller.phase == 'ZIP ready', controller.lastError
    assert len(controller.files) == 2
    form = window.findChild(QObject, 'mainForm')
    form.setProperty('password', 'test-encryption-password')
    form.setProperty('confirmation', 'test-encryption-password')
    click(window, 'protectButton')
    settle(lambda: not controller.busy)
    assert controller.phase == 'Protection verified', controller.lastError
    protected = [f for f in controller.files if f['verified']]
    assert len(protected) == 1
    assert original.read_text() == 'Original content stays unchanged.\n'
    window.grabWindow().save('/tmp/uploadblaze-main.png')
    click(window, 'settingsButton')
    settings = window.findChild(QQuickWindow, 'settingsWindow')
    assert settings.isVisible()
    assert (settings.width(), settings.height()) == (569, 710)
    panel = settings.findChild(QObject, 'settingsForm')
    panel.setProperty('keyId', 'test-key-id')
    panel.setProperty('applicationKey', 'test-key-not-a-real-secret')
    panel.setProperty('bucket', 'test-private-bucket')
    panel.setProperty('prefix', '')
    from blaze_core import cloud
    monkeypatch.setattr(cloud, 'check_connection', lambda config, key, cancel: {'bucket': config['bucket']})
    click(settings, 'testConnectionButton')
    settle(lambda: not controller.busy)
    assert panel.property('connectionStatus') == 'Connection verified'
    panel.setProperty('bucket', 'test-another-private-bucket')
    assert panel.property('connectionStatus') == 'Not tested'
    QTest.qWait(100)
    settings.grabWindow().save('/tmp/uploadblaze-settings.png')
    click(settings, 'saveSettingsButton')
    settle(lambda: not controller.busy)
    assert not settings.isVisible()
    saved = (tmp_path / 'state' / 'settings.json').read_text()
    assert 'test-key-not-a-real-secret' not in saved
    assert json.loads(saved)['prefix'] == ''
    click(window, 'settingsButton')
    assert panel.property('prefix') == ''
    assert panel.property('applicationKey') == ''
    settings.close()
    def cancellable_work(cancel, progress):
        from blaze_core.archives import check_cancel
        cancel.wait(5)
        check_cancel(cancel)
    controller._start('zip', cancellable_work)
    click(window, 'stopButton')
    settle(lambda: not controller.busy)
    assert controller.phase == 'Stopped'
    controller.removeFile(protected[0]['path'])
    assert Path(protected[0]['path']).exists()
    assert not warnings, warnings
    window.close()
    engine.deleteLater()
    _app.processEvents()
