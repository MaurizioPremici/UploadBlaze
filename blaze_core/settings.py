"""Nonsecret preferences and transactional system-keyring credential storage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading

import keyring

SERVICE = 'UploadBlaze.B2'
_DEFAULT = dict(key_id='', bucket='', prefix='', remember=False)


class SettingsError(RuntimeError):
    """A safe error that never includes a credential or backend exception text."""


def normalize_prefix(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('Remote folder must be text.')
    value = value.strip()
    if not value:
        return ''
    if '\\' in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Remote folder contains invalid characters.')
    parts = value.strip('/').split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('Remote folder must not contain empty or traversal components.')
    return '/'.join(parts) + '/'


def validate_config(values: dict) -> dict:
    if not isinstance(values, dict):
        raise ValueError('Settings must be an object.')
    clean = {}
    for name, label in [('key_id', 'Application Key ID'), ('bucket', 'Bucket Name')]:
        value = values.get(name, '')
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{label} is required.')
        value = value.strip()
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError(f'{label} contains invalid characters.')
        clean[name] = value
    clean['prefix'] = normalize_prefix(values.get('prefix', ''))
    return clean


def _secure_backend():
    backend = keyring.get_keyring()
    # Refuse alternate/plaintext backends; application keys belong in an OS vault.
    allowed = {'keyring.backends.macOS', 'keyring.backends.Windows',
               'keyring.backends.SecretService', 'keyring.backends.kwallet'}
    if type(backend).__module__ not in allowed:
        raise SettingsError('A supported operating-system keyring is unavailable.')
    return backend


class SettingsStore:
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.path = self.directory / 'settings.json'
        self._lock = threading.RLock()

    def load(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return dict(_DEFAULT)
            try:
                raw = json.loads(self.path.read_text(encoding='utf-8'))
                clean = validate_config(raw)
                if not isinstance(raw.get('remember'), bool):
                    raise ValueError('Invalid remember setting')
                clean['remember'] = raw['remember']
                return clean
            except (OSError, ValueError, TypeError) as exc:
                raise SettingsError('Saved settings could not be read. Enter and save new settings to preserve and replace the damaged file.') from None

    def load_key(self, key_id: str) -> str:
        with self._lock:
            saved = self.load()
            if not saved['remember'] or saved['key_id'] != key_id:
                return ''
            try:
                return _secure_backend().get_password(SERVICE, key_id) or ''
            except Exception:
                raise SettingsError('The application key could not be read from the system keyring.') from None

    def save(self, values: dict, key: str, remember: bool):
        clean = validate_config(values)
        if not isinstance(remember, bool) or not isinstance(key, str):
            raise ValueError('Invalid key or remember option.')
        if remember and not key.strip():
            raise ValueError('An application key is required to remember credentials.')
        clean['remember'] = remember
        with self._lock:
            try:
                previous = self.load()
            except SettingsError:
                # Recovery never trusts a partly readable account ID. Preserve the
                # original bytes before replacing anything, and leave unknown vault
                # entries alone. A supplied new account is handled normally below.
                backup_name = None
                try:
                    damaged = self.path.read_bytes()
                    fd, backup_name = tempfile.mkstemp(
                        prefix='settings.corrupt-', suffix='.json', dir=self.directory)
                    with os.fdopen(fd, 'wb') as backup:
                        backup.write(damaged)
                        backup.flush()
                        os.fsync(backup.fileno())
                except OSError:
                    if backup_name is not None:
                        Path(backup_name).unlink(missing_ok=True)
                    raise SettingsError('Damaged settings could not be backed up. The original file was preserved; check disk access.') from None
                previous = dict(_DEFAULT)
            affected = set()
            if previous['remember']:
                affected.add(previous['key_id'])
            if remember:
                affected.add(clean['key_id'])
            old_secrets = {}
            backend = None
            temp_name = None
            changed = []
            try:
                # Stage disk contents before changing the vault.
                self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                fd, temp_name = tempfile.mkstemp(prefix='.settings-', dir=self.directory)
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(clean, stream, indent=2)
                    stream.write('\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                if affected:
                    backend = _secure_backend()
                    for account in sorted(affected):
                        old_secrets[account] = backend.get_password(SERVICE, account)
                    for account in sorted(affected):
                        replacement = key if remember and account == clean['key_id'] else None
                        if replacement == old_secrets[account]:
                            continue
                        # Include the attempted mutation in rollback: backend may fail after writing.
                        changed.append(account)
                        if replacement is None:
                            if old_secrets[account] is not None:
                                backend.delete_password(SERVICE, account)
                        else:
                            backend.set_password(SERVICE, account, replacement)
                os.replace(temp_name, self.path)
                temp_name = None
            except Exception:
                rollback_failed = False
                for account in reversed(changed):
                    try:
                        old = old_secrets[account]
                        if old is None:
                            if backend.get_password(SERVICE, account) is not None:
                                backend.delete_password(SERVICE, account)
                        else:
                            backend.set_password(SERVICE, account, old)
                    except Exception:
                        rollback_failed = True
                if rollback_failed:
                    raise SettingsError('Settings were not saved; keyring rollback failed. Review the saved key before retrying.') from None
                raise SettingsError('Settings were not saved. Check disk access and the system keyring.') from None
            finally:
                if temp_name is not None:
                    Path(temp_name).unlink(missing_ok=True)
