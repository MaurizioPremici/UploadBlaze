from pathlib import Path
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])
from blaze_core.controller import Controller


def test_queue_rejects_directories_deduplicates_and_never_deletes(tmp_path):
    app = _app
    c = Controller(tmp_path / 'state', tmp_path / 'prepared')
    source = tmp_path / 'notes.txt'
    source.write_text('keep me')
    c.addPaths([str(source), str(source), str(tmp_path)])
    assert len(c.files) == 1
    assert c.files[0]['status'] == 'Ready to zip'
    c.removeFile(str(source))
    assert c.files == []
    assert source.read_text() == 'keep me'


def test_unverified_archives_cannot_upload_and_passwords_are_checked(tmp_path):
    app = _app
    c = Controller(tmp_path / 'state', tmp_path / 'prepared')
    fake = tmp_path / 'secret_PROTETTO.7z'
    fake.write_bytes(b'not a protected archive')
    c.addPaths([str(fake)])
    c.uploadBackup()
    assert not c.busy
    assert 'Protect Files' in c.lastError
    c.protectFiles('short', 'different')
    assert not c.busy
    assert c.files[0]['verified'] is False
