import json
import pytest
from blaze_core import settings


class MemoryKeyring:
    def __init__(self):
        self.values = {}
        self.fail = False
    def get_password(self, service, account):
        if self.fail:
            raise RuntimeError('SECRET backend failure')
        return self.values.get((service, account))
    def set_password(self, service, account, password):
        if self.fail:
            raise RuntimeError('SECRET backend failure')
        self.values[service, account] = password
    def delete_password(self, service, account):
        if self.fail:
            raise RuntimeError('SECRET backend failure')
        self.values.pop((service, account), None)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    backend = MemoryKeyring()
    monkeypatch.setattr(settings, '_secure_backend', lambda: backend)
    return settings.SettingsStore(str(tmp_path)), backend, tmp_path


def values(**changes):
    return dict(key_id='id1', bucket='backup', prefix='folder', **changes)


def test_save_remember_uses_keyring_and_never_persists_secret(storage):
    store, backend, root = storage
    store.save(values(), 'SECRET', True)
    assert store.load() == dict(key_id='id1', bucket='backup', prefix='folder/', remember=True)
    assert store.load_key('id1') == 'SECRET'
    assert all(b'SECRET' not in f.read_bytes() for f in root.iterdir() if f.is_file())
    assert (root / 'settings.json').stat().st_mode & 0o777 == 0o600


def test_no_remember_removes_old_key_and_saves_no_secret(storage):
    store, backend, root = storage
    store.save(values(), 'SECRET', True)
    store.save(values(), '', False)
    assert store.load_key('id1') == ''
    assert backend.values == {}
    assert store.load()['remember'] is False


def test_missing_key_is_not_implicit_reuse(storage):
    store, backend, root = storage
    store.save(values(), 'SECRET', True)
    with pytest.raises(ValueError, match='key'):
        store.save(values(), '', True)
    assert store.load_key('id1') == 'SECRET'


def test_keyring_failure_preserves_config(storage):
    store, backend, root = storage
    store.save(values(), 'SECRET', True)
    before = (root / 'settings.json').read_bytes()
    backend.fail = True
    with pytest.raises(settings.SettingsError) as error:
        store.save(values(), 'NEWSECRET', True)
    assert 'SECRET' not in str(error.value)
    assert (root / 'settings.json').read_bytes() == before


@pytest.mark.parametrize('remember', [True, False])
def test_disk_commit_failure_rolls_back_keyring(storage, monkeypatch, remember):
    store, backend, root = storage
    store.save(values(), 'SECRET', True)
    before = (root / 'settings.json').read_bytes()
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr(settings.os, 'replace', fail)
    with pytest.raises(settings.SettingsError):
        store.save(values(), 'NEWSECRET', remember)
    assert backend.values == {(settings.SERVICE, 'id1'): 'SECRET'}
    assert (root / 'settings.json').read_bytes() == before
    assert list(root.iterdir()) == [root / 'settings.json']


def test_switch_account_removes_old_key_after_success(storage):
    store, backend, root = storage
    store.save(values(), 'SECRET', True)
    store.save(dict(key_id='id2',bucket='new',prefix=''), 'OTHER', True)
    assert backend.values == {(settings.SERVICE, 'id2'): 'OTHER'}


def test_config_validation_and_corrupt_disk_fail_closed(storage):
    store, backend, root = storage
    with pytest.raises(ValueError):
        store.save(dict(key_id='id',bucket='b',prefix='../elsewhere'), 'SECRET', True)
    assert not list(root.iterdir())
    (root/'settings.json').write_text('{broken')
    with pytest.raises(settings.SettingsError):
        store.load()


def test_default_load_does_not_touch_keyring(storage):
    store, backend, root = storage
    backend.fail = True
    assert store.load() == dict(key_id='', bucket='', prefix='', remember=False)
    store.save(values(), 'SECRET', False)
    assert store.load()['remember'] is False


def test_secure_backend_rejects_plaintext_provider(monkeypatch):
    plaintext = type('PlaintextKeyring', (), {'__module__': 'keyrings.alt.file'})()
    monkeypatch.setattr(settings.keyring, 'get_keyring', lambda: plaintext)
    with pytest.raises(settings.SettingsError, match='operating-system keyring'):
        settings._secure_backend()


def test_new_key_account_disk_failure_restores_both_accounts(storage, monkeypatch):
    store, backend, root = storage
    store.save(values(), 'SECRET', True)
    original = (root/'settings.json').read_bytes()
    monkeypatch.setattr(settings.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('full')))
    with pytest.raises(settings.SettingsError):
        store.save(dict(key_id='id2', bucket='other', prefix=''), 'NEWSECRET', True)
    assert backend.values == {(settings.SERVICE, 'id1'): 'SECRET'}
    assert (root/'settings.json').read_bytes() == original


def test_keyring_write_then_error_is_rolled_back(storage):
    store, backend, root = storage
    store.save(values(), 'SECRET', True)
    real_set = backend.set_password
    def mutate_then_fail(service, account, key):
        real_set(service, account, key)
        if key == 'NEWSECRET':
            raise RuntimeError('SECRET backend failure after mutation')
    backend.set_password = mutate_then_fail
    with pytest.raises(settings.SettingsError):
        store.save(values(), 'NEWSECRET', True)
    assert store.load_key('id1') == 'SECRET'


@pytest.mark.parametrize('prefix', ['../private', 'folder/../private', 'folder//private', r'folder\private', 'folder\x00'])
def test_remote_prefix_rejects_traversal_and_unsafe_names(prefix):
    with pytest.raises(ValueError):
        settings.normalize_prefix(prefix)


def test_save_recovers_corrupt_settings_and_preserves_exact_bytes(storage):
    store, backend, root = storage
    corrupt = b'{"key_id":"unknown", "remember":true, broken\xff'
    (root/'settings.json').write_bytes(corrupt)
    backend.values[settings.SERVICE, 'unknown'] = 'OLDSECRET'
    store.save(values(), 'SECRET', True)
    assert store.load()['key_id'] == 'id1'
    assert store.load_key('id1') == 'SECRET'
    assert backend.values[settings.SERVICE, 'unknown'] == 'OLDSECRET'
    backups = list(root.glob('settings.corrupt-*.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == corrupt
    assert backups[0].stat().st_mode & 0o777 == 0o600
    (root/'settings.json').write_bytes(b'other broken config')
    store.save(values(), '', False)
    assert len(list(root.glob('settings.corrupt-*.json'))) == 2
    assert backend.values[settings.SERVICE, 'unknown'] == 'OLDSECRET'


def test_recovery_commit_failure_preserves_original_and_rolls_back_key(storage, monkeypatch):
    store, backend, root = storage
    corrupt = b'{broken'
    (root/'settings.json').write_bytes(corrupt)
    monkeypatch.setattr(settings.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('full')))
    with pytest.raises(settings.SettingsError):
        store.save(values(), 'SECRET', True)
    assert (root/'settings.json').read_bytes() == corrupt
    assert backend.values == {}
    assert [p.read_bytes() for p in root.glob('settings.corrupt-*.json')] == [corrupt]


def test_recovery_backup_failure_never_overwrites_corrupt_original(storage, monkeypatch):
    store, backend, root = storage
    corrupt = b'{broken'
    (root/'settings.json').write_bytes(corrupt)
    monkeypatch.setattr(settings.tempfile, 'mkstemp', lambda *a, **kw: (_ for _ in ()).throw(OSError('full')))
    with pytest.raises(settings.SettingsError):
        store.save(values(), 'SECRET', True)
    assert (root/'settings.json').read_bytes() == corrupt
    assert backend.values == {}
