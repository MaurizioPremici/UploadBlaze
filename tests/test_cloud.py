import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest
from blaze_core import cloud
from blaze_core.archives import Cancelled


CONFIG = dict(key_id='id1', bucket='backup', prefix='safe')


class FakeAPI:
    def __init__(self):
        self.allowed = dict(capabilities=['readFiles', 'listFiles', 'writeFiles', 'listBuckets'],
                            bucketId='b1', bucketName='backup', namePrefix='safe/')
        self.account_info = SimpleNamespace(get_allowed=lambda: self.allowed)
        self.bucket = FakeBucket(self)
        self.versions = {}
        self.authorized = None
        self.info_fail = False
        self.corrupt = False
        self.large = False
        self.unverified = False
    def authorize_account(self, realm, key_id, key):
        self.authorized = (realm, key_id, key)
    def list_buckets(self, bucket_name):
        assert bucket_name == 'backup'
        return [self.bucket]
    def get_file_info(self, file_id):
        if self.info_fail:
            raise RuntimeError('SECRET transport error')
        version = self.versions[file_id]
        if self.corrupt:
            return SimpleNamespace(**(vars(version) | {'size': 1}))
        return version


class FakeBucket:
    def __init__(self, api):
        self.api, self.id_, self.name, self.type_ = api, 'b1', 'backup', 'allPrivate'
        self.calls = []
        self.disconnect_after_upload = False
        self.cancel_after_upload = None
    def upload_local_file(self, local_file, file_name, sha1_sum, file_info,
                          progress_listener, content_type):
        data = Path(local_file).read_bytes()
        assert hashlib.sha1(data).hexdigest() == sha1_sum
        progress_listener.set_total_bytes(len(data))
        progress_listener.bytes_completed(len(data))
        file_id = f'v{len(self.calls)+1}'
        self.calls.append(file_name)
        checksum = 'none' if self.api.large else sha1_sum
        if self.api.unverified:
            checksum = 'unverified:' + sha1_sum
        version = SimpleNamespace(id_=file_id, file_name=file_name, size=len(data),
            bucket_id='b1', content_sha1=checksum,
            file_info=dict(file_info, large_file_sha1=sha1_sum), action='upload')
        self.api.versions[file_id] = version
        if self.cancel_after_upload is not None:
            self.cancel_after_upload.set()
        if self.disconnect_after_upload:
            raise RuntimeError('SECRET connection lost')
        return version
    def ls(self, folder_to_list, latest_only, recursive, folder_to_list_can_be_a_file):
        return ((v, None) for v in self.api.versions.values() if v.file_name.startswith(folder_to_list))


@pytest.fixture
def service(tmp_path, monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(cloud, '_new_api', lambda cancel: api)
    path = tmp_path / 'protected.7z'
    path.write_bytes(b'opaque protected archive bytes')
    meta = dict(path=str(path), size=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), source_sha256='a'*64)
    return api, meta, tmp_path / 'state', threading.Event()


def upload(service, **config):
    api, meta, state, cancel = service
    return cloud.upload_files([meta], CONFIG | config, 'SECRET', str(state), cancel, lambda *args: None)


def test_private_restricted_key_and_normalized_prefix(service):
    api, meta, state, cancel = service
    assert cloud.check_connection(CONFIG, 'SECRET', cancel)['bucket'] == 'backup'
    assert api.authorized == ('production', 'id1', 'SECRET')


@pytest.mark.parametrize('change', [dict(capabilities=['writeFiles']), dict(bucketId='other'),
                                  dict(bucketName='other'), dict(namePrefix='different/')])
def test_rejects_wrong_key_permissions_before_upload(service, change):
    api, _, _, _ = service
    api.allowed.update(change)
    with pytest.raises(cloud.CloudError):
        upload(service)
    assert not api.bucket.calls


def test_public_bucket_rejected(service):
    service[0].bucket.type_ = 'allPublic'
    with pytest.raises(cloud.CloudError, match='private'):
        upload(service)


def test_upload_verifies_remote_and_retry_skips_confirmed_version(service):
    api, meta, state, cancel = service
    result = upload(service)
    assert result['uploaded'] == 1 and result['skipped'] == 0
    assert result['prefix'].startswith('safe/uploadblaze-')
    assert upload(service) == dict(uploaded=0, skipped=1, prefix=result['prefix'])
    assert len(api.bucket.calls) == 1
    assert Path(meta['path']).exists()
    journal = next(state.glob('*.json'))
    assert 'SECRET' not in journal.read_text()
    assert 'v1' in journal.read_text()


def test_local_metadata_must_match_content_before_network(service):
    api, meta, state, cancel = service
    Path(meta['path']).write_bytes(b'changed')
    with pytest.raises(cloud.CloudError, match='changed'):
        upload(service)
    assert api.authorized is None
    assert not api.bucket.calls


def test_remote_mismatch_never_marked_complete(service):
    api, _, _, _ = service
    api.corrupt = True
    with pytest.raises(cloud.CloudError, match='unconfirmed'):
        upload(service)
    api.corrupt = False
    assert upload(service)['skipped'] == 1
    assert len(api.bucket.calls) == 1


def test_uncertain_upload_recovers_by_version_without_duplicate(service):
    api, _, _, _ = service
    api.bucket.disconnect_after_upload = True
    with pytest.raises(cloud.CloudError, match='unconfirmed') as error:
        upload(service)
    assert 'SECRET' not in str(error.value)
    api.bucket.disconnect_after_upload = False
    assert upload(service)['skipped'] == 1
    assert len(api.bucket.calls) == 1


def test_remote_info_failure_keeps_pending_for_retry(service):
    api, _, _, _ = service
    api.info_fail = True
    with pytest.raises(cloud.CloudError, match='unconfirmed'):
        upload(service)
    api.info_fail = False
    assert upload(service)['skipped'] == 1
    assert len(api.bucket.calls) == 1


def test_cancel_before_upload_leaves_original_and_no_network(service):
    api, meta, _, cancel = service
    cancel.set()
    with pytest.raises(Cancelled):
        upload(service)
    assert not api.bucket.calls and api.authorized is None
    assert Path(meta['path']).exists()


def test_cancel_after_transfer_does_not_claim_confirmation(service):
    api, meta, _, cancel = service
    api.bucket.cancel_after_upload = cancel
    with pytest.raises(Cancelled):
        upload(service)
    cancel.clear()
    api.bucket.cancel_after_upload = None
    assert upload(service)['skipped'] == 1
    assert len(api.bucket.calls) == 1


def test_large_file_sha1_metadata_supported(service):
    service[0].large = True
    assert upload(service)['uploaded'] == 1


def test_unverified_sha1_is_not_confirmation(service):
    service[0].unverified = True
    with pytest.raises(cloud.CloudError, match='unconfirmed'):
        upload(service)


def test_changed_content_uses_new_job_prefix(service):
    api, meta, state, cancel = service
    first = upload(service)
    Path(meta['path']).write_bytes(b'new protected content')
    meta.update(size=Path(meta['path']).stat().st_size,
                sha256=hashlib.sha256(Path(meta['path']).read_bytes()).hexdigest())
    second = upload(service)
    assert first['prefix'] != second['prefix']
    assert len(api.bucket.calls) == 2


def test_missing_protection_metadata_rejected(service):
    del service[1]['source_sha256']
    with pytest.raises(cloud.CloudError):
        upload(service)
    assert not service[0].bucket.calls


def test_progress_reports_bytes_and_can_cancel(service):
    api, meta, state, cancel = service
    events = []
    def progress(done, total, message):
        events.append((done, total))
        if done:
            cancel.set()
    with pytest.raises(Cancelled):
        cloud.upload_files([meta], CONFIG, 'SECRET', str(state), cancel, progress)
    assert events
    assert Path(meta['path']).exists()


@pytest.mark.parametrize('large', [False, True])
def test_real_sdk_upload_and_retry_against_in_memory_b2_simulator(tmp_path, monkeypatch, large):
    """Exercise the installed SDK, checksum plumbing, restricted auth and ls contracts offline."""
    from b2sdk.v2 import B2Api, B2HttpApiConfig, InMemoryAccountInfo
    from b2sdk.v2.raw_simulator import RawSimulator
    raw = RawSimulator()
    factory = lambda cancel: B2Api(InMemoryAccountInfo(),
        api_config=B2HttpApiConfig(_raw_api_class=lambda http: raw))
    admin = factory(None)
    account, master_key = raw.create_account()
    admin.authorize_account('production', account, master_key)
    bucket = admin.create_bucket('simulated-private-backup', 'allPrivate')
    restricted = admin.create_key(['listBuckets', 'readFiles', 'listFiles', 'writeFiles'],
        'simulated-upload-key', name_prefix='safe/')
    monkeypatch.setattr(cloud, '_new_api', factory)
    path = tmp_path / 'protected.7z'
    path.write_bytes(b'bytes of a previously verified encrypted archive' * (100 if large else 1))
    meta = dict(path=str(path), size=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), source_sha256='a'*64)
    config = dict(key_id=restricted.id_, bucket=bucket.name, prefix='safe/')
    cancel = threading.Event()
    first = cloud.upload_files([meta], config, restricted.application_key, str(tmp_path/'state'), cancel, lambda *a: None)
    second = cloud.upload_files([meta], config, restricted.application_key, str(tmp_path/'state'), cancel, lambda *a: None)
    assert first['uploaded'] == 1
    assert second['skipped'] == 1
    assert first['prefix'] == second['prefix']
    assert len(list(bucket.ls(recursive=True, latest_only=False))) == 1


def test_protected_input_modified_during_transfer_is_unconfirmed(service):
    api, meta, state, cancel = service
    original = api.bucket.upload_local_file
    def change(**kwargs):
        result = original(**kwargs)
        Path(kwargs['local_file']).write_bytes(b'altered during upload')
        return result
    api.bucket.upload_local_file = change
    with pytest.raises(cloud.CloudError, match='unconfirmed'):
        upload(service)
    journal = json.loads(next(state.glob('*.json')).read_text())
    assert journal['completed'] == {}


def test_invalid_journal_before_first_transfer_is_safe(service):
    api, meta, state, cancel = service
    first = upload(service)
    path = next(state.glob('*.json'))
    path.write_text('{corrupt')
    with pytest.raises(cloud.CloudError, match='retry state'):
        upload(service)
    assert len(api.bucket.calls) == 1


def test_original_replacement_at_sdk_open_uploads_only_verified_snapshot(service):
    api, meta, state, cancel = service
    verified = Path(meta['path']).read_bytes()
    private_plaintext = b'PRIVATE PLAINTEXT MUST NEVER LEAVE THE COMPUTER'
    observed = []
    snapshot_paths = []
    original_upload = api.bucket.upload_local_file
    def replace_original_then_upload(**kwargs):
        Path(meta['path']).write_bytes(private_plaintext)
        snapshot_paths.append(Path(kwargs['local_file']))
        observed.append(Path(kwargs['local_file']).read_bytes())
        return original_upload(**kwargs)
    api.bucket.upload_local_file = replace_original_then_upload
    result = upload(service)
    assert result['uploaded'] == 1
    assert observed == [verified]
    assert Path(meta['path']).read_bytes() == private_plaintext
    assert snapshot_paths[0] != Path(meta['path'])
    assert all(not path.exists() for path in snapshot_paths)


def test_temporary_snapshots_are_cleaned_after_sdk_failure(service):
    api, meta, state, cancel = service
    observed = []
    def fail(**kwargs):
        snapshot = Path(kwargs['local_file'])
        observed.append(snapshot)
        assert snapshot.stat().st_mode & 0o777 == 0o600
        assert snapshot.parent.stat().st_mode & 0o777 == 0o700
        raise RuntimeError('network unavailable')
    api.bucket.upload_local_file = fail
    with pytest.raises(cloud.CloudError, match='unconfirmed'):
        upload(service)
    assert observed and all(not path.exists() for path in observed)
    assert Path(meta['path']).exists()


def test_source_swapped_to_symlink_at_open_is_rejected_before_network(service, monkeypatch):
    api, meta, state, cancel = service
    source = Path(meta['path'])
    plaintext = source.parent / 'private.txt'
    plaintext.write_bytes(b'private plaintext')
    original_open = cloud.os.open
    def replace_at_open(path, flags, *args, **kwargs):
        if Path(path) == source:
            source.unlink()
            source.symlink_to(plaintext)
        return original_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(cloud.os, 'open', replace_at_open)
    with pytest.raises(cloud.CloudError):
        upload(service)
    assert not api.bucket.calls and api.authorized is None
    assert plaintext.read_bytes() == b'private plaintext'


def test_temporary_snapshots_are_cleaned_after_cancel(service):
    api, meta, state, cancel = service
    observed = []
    original_upload = api.bucket.upload_local_file
    def upload_then_cancel(**kwargs):
        observed.append(Path(kwargs['local_file']))
        result = original_upload(**kwargs)
        cancel.set()
        return result
    api.bucket.upload_local_file = upload_then_cancel
    with pytest.raises(Cancelled):
        upload(service)
    assert observed and all(not path.exists() for path in observed)
    assert Path(meta['path']).exists()
