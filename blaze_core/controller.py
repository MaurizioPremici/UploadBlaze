"""Qt-facing state; filesystem/network work is performed off the GUI thread."""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl


class Controller(QObject):
    changed = Signal()
    event = Signal(object)
    settingsSaved = Signal()
    errorRaised = Signal(str)

    def __init__(self, state_dir, output_dir, parent=None):
        super().__init__(parent)
        from .settings import SettingsStore
        self.state_dir, self.output_dir = Path(state_dir), Path(output_dir)
        self.store = SettingsStore(str(self.state_dir))
        self._config = {'key_id': '', 'bucket': '', 'prefix': 'encrypted-backups/', 'remember': False}
        self._files, self._logs = [], []
        self._busy = False
        self._percent = 0.0
        self._phase = 'Ready'
        self._last_error = ''
        self._connection = 'Not checked'
        self._test_status = 'Not tested'
        self._session_key = ''
        self._cancel = threading.Event()
        self._thread = None
        self.event.connect(self._receive)
        try:
            loaded = self.store.load()
            if loaded and loaded.get("key_id"):
                self._config.update(loaded)
        except Exception:
            self._last_error = 'Saved settings could not be read. Open Settings and save them again.'
            self._log(self._last_error)

    @Property('QVariantList', notify=changed)
    def files(self):
        return [dict(item) for item in self._files]

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(float, notify=changed)
    def percent(self):
        return self._percent

    @Property(str, notify=changed)
    def phase(self):
        return self._phase

    @Property(str, notify=changed)
    def logText(self):
        return '\n'.join(self._logs)

    @Property(str, notify=changed)
    def lastError(self):
        return self._last_error

    @Property(str, notify=changed)
    def bucketName(self):
        return self._config.get('bucket') or 'No bucket selected'

    @Property(str, notify=changed)
    def connectionText(self):
        return self._connection

    @Property(str, notify=changed)
    def testStatus(self):
        return self._test_status

    @Property('QVariantMap', notify=changed)
    def settings(self):
        return dict(self._config)

    def _log(self, text):
        self._logs.append(f'{datetime.now():%H:%M:%S}  {text}')
        self._logs = self._logs[-200:]

    def _fail(self, text):
        self._last_error = text
        self._log(text)
        self.changed.emit()
        self.errorRaised.emit(text)

    @Slot('QVariantList')
    def addPaths(self, paths):
        if self._busy:
            return
        errors = []
        for value in paths:
            try:
                text = value.toLocalFile() if isinstance(value, QUrl) else str(value)
                if text.startswith('file:'):
                    text = QUrl(text).toLocalFile()
                p = Path(text).expanduser()
                if not p.is_absolute() or p.is_symlink() or not p.is_file():
                    raise ValueError('Choose regular files; folders and symbolic links are not supported.')
                p = p.resolve(strict=True)
                if any(item['path'] == str(p) for item in self._files):
                    continue
                kind = 'zip' if p.suffix.lower() == '.zip' else 'protected' if p.suffix.lower() == '.7z' else 'raw'
                status = {'zip': 'Ready to protect', 'protected': 'Needs verification', 'raw': 'Ready to zip'}[kind]
                self._files.append({'path': str(p), 'name': p.name, 'size': p.stat().st_size,
                                    'sizeText': self._size(p.stat().st_size), 'kind': kind, 'status': status, 'verified': False})
                self._log(f'Added {p.name}')
            except (OSError, ValueError) as error:
                errors.append(str(error))
        self.changed.emit()
        if errors:
            self._fail(errors[0])

    @staticmethod
    def _size(size):
        return f'{size / 1024 / 1024:.1f} MB' if size >= 1024 * 1024 else f'{size / 1024:.1f} KB'

    @Slot(str)
    def removeFile(self, path):
        if not self._busy:
            self._files = [item for item in self._files if item['path'] != path]
            self.changed.emit()

    @Slot()
    def clearLog(self):
        self._logs.clear()
        self.changed.emit()

    @Slot()
    def stop(self):
        if self._busy:
            self._cancel.set()
            self._phase = 'Stopping safely…'
            self._log('Stop requested. Waiting for the current operation to stop safely.')
            self.changed.emit()

    def _start(self, kind, function, secrets=()):
        if self._busy:
            return
        self._busy, self._percent, self._last_error = True, 0.0, ''
        self._cancel = threading.Event()
        self._phase = {'zip': 'Creating ZIP…', 'protect': 'Protecting files…', 'upload': 'Checking backup…',
                       'test': 'Testing connection…', 'save': 'Saving settings…'}[kind]
        if kind == 'test':
            self._test_status = 'Testing…'
        self._log(self._phase)
        self.changed.emit()
        token = self._cancel

        def run():
            from .archives import Cancelled
            last_emit = [0.0, '']

            def progress(done, total, message):
                now = time.monotonic()
                if now - last_emit[0] >= 0.1 or message != last_emit[1] or done == total:
                    value = max(0.0, min(100.0, 100.0 * done / total)) if total else -1.0
                    self.event.emit({'type': 'progress', 'value': value, 'message': str(message)})
                    last_emit[:] = [now, message]
            try:
                result = function(token, progress)
                self.event.emit({'type': 'finished', 'kind': kind, 'result': result})
            except Exception as error:
                text = str(error) or type(error).__name__
                for secret in secrets:
                    if secret:
                        text = text.replace(secret, '[redacted]')
                text = re.sub(r'(?i)(authorization|applicationKey|authToken)\s*[:=]\s*\S+', r'\1=[redacted]', text)
                self.event.emit({'type': 'failed', 'kind': kind, 'error': text[:4000],
                                 'cancelled': isinstance(error, Cancelled)})
        self._thread = threading.Thread(target=run, name=f'UploadBlaze-{kind}', daemon=True)
        self._thread.start()

    @Slot(object)
    def _receive(self, event):
        kind = event['type']
        if kind == 'progress':
            if not self._cancel.is_set():
                if self._phase != event['message']:
                    self._log(event['message'])
                self._phase, self._percent = event['message'], event['value']
        elif kind == 'protected':
            data = event['item']
            existing = next((i for i in self._files if i['path'] == data['path']), None)
            row = {**data, 'name': Path(data['path']).name, 'sizeText': self._size(data['size']),
                   'kind': 'protected', 'status': 'Protected', 'verified': True}
            if existing is None:
                self._files.append(row)
            else:
                existing.update(row)
            for item in self._files:
                if item['path'] == event['source'] and item['path'] != data['path']:
                    item['status'] = 'Protection created'
            self._log(f"Verified protected archive: {row['name']}")
        elif kind == 'finished':
            self._busy = False
            self._percent = 100.0
            job, result = event['kind'], event['result']
            if job == 'zip':
                for item in self._files:
                    if item['path'] in result['sources']:
                        item['status'] = 'Archived'
                self.addPaths([result['path']])
                self._log(f"ZIP saved: {result['path']}")
                self._phase = 'ZIP ready'
            elif job == 'protect':
                self._phase = 'Protection verified'
                self._log('Protected archives verified. Originals kept unchanged.')
            elif job == 'upload':
                self._phase = 'Backup verified'
                self._connection = 'Verified'
                completed_paths = result.pop('_paths', [])
                for item in self._files:
                    if item['path'] in completed_paths:
                        item['status'] = 'Uploaded'
                self._log(f"Backup verified: {result['uploaded']} uploaded, {result['skipped']} already completed. {result['prefix']}")
            elif job == 'test':
                self._test_status = 'Connection verified'
                self._phase = 'Connection test completed'
                self._log(f"Private bucket verified: {result['bucket']}")
            elif job == 'save':
                self._config = result['config']
                self._session_key = result['key']
                self._connection = 'Not checked'
                self._phase = 'Settings saved'
                self._log('Settings saved.')
                self.settingsSaved.emit()
        elif kind == 'failed':
            self._busy = False
            self._percent = 0.0
            self._phase = 'Stopped' if event['cancelled'] else 'Operation failed'
            if event['kind'] == 'test':
                self._test_status = 'Stopped' if event['cancelled'] else 'Connection failed'
            if event['kind'] == 'upload':
                self._connection = 'Not verified'
            if event['cancelled']:
                self._log('Operation stopped. Original files were kept unchanged.')
            else:
                self._fail(event['error'])
        self.changed.emit()

    @Slot()
    def zipFiles(self):
        if self._busy:
            return
        paths = [i['path'] for i in self._files if i['kind'] == 'raw' and i['status'] != 'Archived']
        if not paths:
            self._fail('Add files to create a ZIP. Existing ZIP archives can go directly to Protect Files.')
            return
        def work(cancel, progress):
            from .archives import zip_files
            return {'path': zip_files(paths, str(self.output_dir), cancel, progress), 'sources': paths}
        self._start('zip', work)

    @Slot(str, str)
    def protectFiles(self, password, confirmation):
        if self._busy:
            return
        if not password or password != confirmation:
            self._fail('Enter the same encryption password in both fields.')
            return
        if len(password) < 12:
            self._fail('Use an encryption password of at least 12 characters. Keep it safe; it cannot be recovered.')
            return
        paths = [i['path'] for i in self._files if (i['kind'] == 'zip' and i['status'] != 'Protection created') or
                 i['kind'] == 'protected']
        if not paths:
            self._fail('Add or create a ZIP archive first. Added .7z archives can also be verified with their password.')
            return
        def work(cancel, progress):
            from .archives import protect_zip, verify_protected, check_cancel
            for index, path in enumerate(paths):
                check_cancel(cancel)
                def part(done, total, message):
                    fraction = done / total if total else 0.0
                    progress(index + fraction, len(paths), message)
                if Path(path).suffix.lower() == '.7z':
                    item = verify_protected(path, password, cancel, part)
                else:
                    item = protect_zip(path, password, str(self.output_dir), cancel, part)
                self.event.emit({'type': 'protected', 'item': item, 'source': path})
            return None
        self._start('protect', work, (password,))

    def _resolve_key(self, config, entered):
        if entered:
            return entered
        if config['key_id'] == self._config.get('key_id') and self._session_key:
            return self._session_key
        if config['key_id'] == self._config.get('key_id') and self._config.get('remember'):
            key = self.store.load_key(config['key_id'])
            if key:
                return key
        raise ValueError('Enter your Application Key in Settings. This is not your Backblaze account password.')

    @Slot()
    def uploadBackup(self):
        if self._busy:
            return
        items = [dict(i) for i in self._files if i.get('verified') and i['kind'] == 'protected']
        if not items:
            self._fail('Use Protect Files to create or verify protected archives before uploading.')
            return
        config = dict(self._config)
        def work(cancel, progress):
            from .cloud import upload_files
            key = self._resolve_key(config, '')
            result = upload_files(items, config, key, str(self.state_dir), cancel, progress)
            return {**result, '_paths': [i['path'] for i in items]}
        self._start('upload', work, (self._session_key,))

    @Slot(str, str, str, str, bool)
    def saveSettings(self, key_id, key, bucket, prefix, remember):
        values = {'key_id': key_id.strip(), 'bucket': bucket.strip(), 'prefix': prefix.strip(), 'remember': remember}
        def work(cancel, progress):
            from .settings import validate_config
            config = validate_config(values)
            secret = self._resolve_key(config, key.strip())
            self.store.save(config, secret, remember)
            return {'config': {**config, 'remember': remember}, 'key': secret}
        self._start('save', work, (key, self._session_key))

    @Slot(str, str, str, str)
    def testConnection(self, key_id, key, bucket, prefix):
        values = {'key_id': key_id.strip(), 'bucket': bucket.strip(), 'prefix': prefix.strip()}
        def work(cancel, progress):
            from .cloud import check_connection
            from .settings import validate_config
            config = validate_config(values)
            return check_connection(config, self._resolve_key(config, key.strip()), cancel)
        self._start('test', work, (key, self._session_key))
