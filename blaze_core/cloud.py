"""Private B2 uploads with content verification and recoverable local journals.

Authorization is memory-only. A journal records intent before upload, and only a
fresh get_file_info response confirms a version. Multipart confirmation relies on
B2's per-part SDK checks plus the full SHA1 in large_file_sha1 metadata; it is not
a remote download verification. Original local and remote files are never deleted.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading

import requests
from b2sdk.v2 import AbstractProgressListener, B2Api, B2HttpApiConfig, InMemoryAccountInfo

from .archives import Cancelled, check_cancel
from .settings import validate_config


class CloudError(RuntimeError):
    """Safe public diagnostic without credentials or raw provider exception text."""


def _new_api(cancel):
    class BoundedSession(requests.Session):
        def request(self, *args, **kwargs):
            check_cancel(cancel)
            kwargs['timeout'] = (10, 30)
            response = super().request(*args, **kwargs)
            check_cancel(cancel)
            return response
    return B2Api(InMemoryAccountInfo(), max_upload_workers=2,
                 api_config=B2HttpApiConfig(http_session_factory=BoundedSession))


def _connect(config, key, cancel):
    clean = validate_config(config)
    if not isinstance(key, str) or not key.strip():
        raise CloudError('Application Key is required.')
    check_cancel(cancel)
    api = _new_api(cancel)
    try:
        api.authorize_account('production', clean['key_id'], key)
        check_cancel(cancel)
        allowed = api.account_info.get_allowed()
        required = {'writeFiles', 'listFiles', 'readFiles'}
        if not required.issubset(set(allowed.get('capabilities', []))):
            raise CloudError('The key requires writeFiles, listFiles and readFiles permissions.')
        if allowed.get('bucketName') not in (None, clean['bucket']):
            raise CloudError('The key is restricted to a different bucket.')
        restricted_prefix = allowed.get('namePrefix') or ''
        if not clean['prefix'].startswith(restricted_prefix):
            raise CloudError('Remote folder does not match the application key prefix restriction.')
        # A cached bucket may omit type_: explicitly request its current state.
        buckets = api.list_buckets(bucket_name=clean['bucket'])
        check_cancel(cancel)
        matching = [b for b in buckets if b.name == clean['bucket']]
        if len(matching) != 1:
            raise CloudError('The selected bucket could not be found.')
        bucket = matching[0]
        if allowed.get('bucketId') not in (None, bucket.id_):
            raise CloudError('The key is restricted to a different bucket.')
        if bucket.type_ != 'allPrivate':
            raise CloudError('The backup bucket must be private.')
        return api, bucket, clean
    except (CloudError, Cancelled):
        raise
    except Exception:
        check_cancel(cancel)
        raise CloudError('B2 connection could not be verified. Check the key, bucket, network and listBuckets permission.') from None


def check_connection(config: dict, key: str, cancel) -> dict:
    _, bucket, _ = _connect(config, key, cancel)
    return dict(bucket=bucket.name, status='Private bucket and required key permissions verified.')


def _fingerprint(meta, cancel, snapshot=None):
    try:
        path = Path(meta['path'])
        expected = meta['sha256']
        source = meta['source_sha256']
        size = meta['size']
        if (not isinstance(size, int) or isinstance(size, bool) or size <= 0
                or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected)
                or not isinstance(source, str) or not re.fullmatch('[0-9a-f]{64}', source)
                or path.is_symlink() or not path.is_file()):
            raise ValueError('Invalid protection metadata')
        identity_path = str(path.resolve())
        sha256, sha1 = hashlib.sha256(), hashlib.sha1()
        length = 0
        # Opening the final component without following links and checking the
        # descriptor prevents a raced FIFO/symlink replacement from being read.
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        with ExitStack() as stack:
            stream = stack.enter_context(os.fdopen(os.open(path, flags), 'rb'))
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size != size:
                raise CloudError('A protected file changed after verification. Verify it again before uploading.')
            output = None
            if snapshot is not None:
                fd = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                output = stack.enter_context(os.fdopen(fd, 'wb'))
            while chunk := stream.read(1024 * 1024):
                check_cancel(cancel)
                length += len(chunk)
                sha256.update(chunk)
                sha1.update(chunk)
                if output is not None:
                    output.write(chunk)
            check_cancel(cancel)
            if output is not None:
                output.flush()
                os.fsync(output.fileno())
        if length != size or sha256.hexdigest() != expected:
            raise CloudError('A protected file changed after verification. Verify it again before uploading.')
        return dict(path=identity_path, name=path.name, size=size, sha256=expected,
                    source_sha256=source, sha1=sha1.hexdigest())
    except (CloudError, Cancelled):
        raise
    except (KeyError, TypeError, ValueError, OSError):
        raise CloudError('A regular file with valid protection verification metadata is required.') from None


def _write_journal(path, journal):
    temp_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp_name = tempfile.mkstemp(prefix='.upload-', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(journal, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def _matches(version, bucket, name, fingerprint):
    checksum = version.content_sha1
    if checksum == 'none':
        checksum = version.file_info.get('large_file_sha1')
    return (version.id_ and version.bucket_id == bucket.id_
            and version.file_name == name and version.size == fingerprint['size']
            and version.action == 'upload' and checksum == fingerprint['sha1'])


def _confirmed(api, bucket, name, fingerprint, file_id, cancel):
    check_cancel(cancel)
    remote = api.get_file_info(file_id)
    check_cancel(cancel)
    if remote.id_ != file_id or not _matches(remote, bucket, name, fingerprint):
        raise CloudError('Upload is unconfirmed: remote version, size or checksum did not match.')
    return remote.id_


class _Progress(AbstractProgressListener):
    def __init__(self, cancel, progress, base, total, name):
        super().__init__(name)
        self.cancel, self.progress, self.base, self.total = cancel, progress, base, total
        self.size = 0
        self._lock = threading.Lock()

    def set_total_bytes(self, total_byte_count):
        check_cancel(self.cancel)
        self.size = total_byte_count

    def bytes_completed(self, byte_count):
        with self._lock:
            check_cancel(self.cancel)
            self.progress(self.base + min(byte_count, self.size), self.total,
                          f'Uploading {self.description}')
            check_cancel(self.cancel)


def upload_files(files: list[dict], config: dict, key: str, state_dir: str,
                 cancel, progress) -> dict:
    check_cancel(cancel)
    if not files:
        raise CloudError('Select verified protected files before uploading.')
    # No SDK operation sees the mutable source path. Every snapshot is fully
    # copied and verified against the protection metadata before authorization.
    with tempfile.TemporaryDirectory(prefix='uploadblaze-protected-') as staging:
        snapshots = {}
        fingerprints = []
        for index, meta in enumerate(files):
            snapshot = str(Path(staging) / f'{index}.7z')
            fingerprint = _fingerprint(meta, cancel, snapshot=snapshot)
            if fingerprint['path'] in snapshots:
                raise CloudError('Duplicate local files are not allowed in an upload job.')
            snapshots[fingerprint['path']] = snapshot
            fingerprints.append(fingerprint)
        fingerprints.sort(key=lambda fingerprint: fingerprint['path'])
        names = [fingerprint['name'] for fingerprint in fingerprints]
        if len(names) != len(set(names)):
            raise CloudError('Each selected archive must have a unique filename before uploading.')
        return _upload_snapshots(fingerprints, snapshots, config, key, state_dir, cancel, progress)


def _upload_snapshots(fingerprints, snapshots, config, key, state_dir, cancel, progress):
    api, bucket, clean = _connect(config, key, cancel)
    identity = dict(key_id=clean['key_id'], bucket_id=bucket.id_, prefix=clean['prefix'],
                    files=fingerprints)
    job_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    journal_path = Path(state_dir) / f'{job_id}.json'
    try:
        if journal_path.exists():
            journal = json.loads(journal_path.read_text(encoding='utf-8'))
            if (journal.get('identity') != identity
                    or not isinstance(journal.get('completed'), dict)
                    or not isinstance(journal.get('pending'), dict)
                    or journal.get('prefix') != clean['prefix']):
                raise ValueError('Journal integrity mismatch')
        else:
            journal = dict(identity=identity, prefix=clean['prefix'],
                           completed={}, pending={})
            _write_journal(journal_path, journal)
    except (OSError, ValueError, TypeError, AttributeError):
        raise CloudError('Upload retry state could not be read or saved. No files were uploaded.') from None
    total = sum(f['size'] for f in fingerprints)
    done = uploaded = skipped = 0
    for index, fingerprint in enumerate(fingerprints):
        check_cancel(cancel)
        slot = str(index)
        snapshot_metadata = fingerprint | {'path': snapshots[fingerprint['path']]}
        # Preserve the archive name so it remains recognizable in Backblaze.
        remote_name = journal['prefix'] + fingerprint['name']
        try:
            # Re-read the private snapshot, never reopen the original source.
            _fingerprint(snapshot_metadata, cancel)
            existing_id = journal['completed'].get(slot) or journal['pending'].get(slot)
            if existing_id:
                _confirmed(api, bucket, remote_name, fingerprint, existing_id, cancel)
                skipped += 1
            elif slot in journal['pending']:
                # The process may have stopped after B2 accepted bytes but before returning the ID.
                for version, _ in bucket.ls(folder_to_list=remote_name, latest_only=False,
                                             recursive=True, folder_to_list_can_be_a_file=True):
                    check_cancel(cancel)
                    if _matches(version, bucket, remote_name, fingerprint):
                        existing_id = _confirmed(api, bucket, remote_name, fingerprint, version.id_, cancel)
                        skipped += 1
                        break
            if not existing_id:
                journal['pending'][slot] = None
                _write_journal(journal_path, journal)
                listener = _Progress(cancel, progress, done, total, fingerprint['name'])
                result = bucket.upload_local_file(local_file=snapshot_metadata['path'], file_name=remote_name,
                    sha1_sum=fingerprint['sha1'], file_info={'uploadblaze_sha256': fingerprint['sha256']},
                    content_type='application/x-7z-compressed', progress_listener=listener)
                # Save the received version before confirmation so interrupted confirmation is recoverable.
                journal['pending'][slot] = result.id_
                _write_journal(journal_path, journal)
                check_cancel(cancel)
                try:
                    _fingerprint(snapshot_metadata, cancel)
                except CloudError:
                    raise CloudError('Upload is unconfirmed: the protected upload snapshot changed during transfer.') from None
                existing_id = _confirmed(api, bucket, remote_name, fingerprint, result.id_, cancel)
                uploaded += 1
            journal['completed'][slot] = existing_id
            journal['pending'].pop(slot, None)
            _write_journal(journal_path, journal)
            done += fingerprint['size']
            progress(done, total, f'Confirmed {fingerprint["name"]}')
            check_cancel(cancel)
        except Cancelled:
            raise Cancelled('Upload stopped. Any in-flight remote result is unconfirmed; retry to reconcile it.') from None
        except CloudError:
            raise
        except Exception:
            if cancel.is_set():
                raise Cancelled('Upload stopped. Any in-flight remote result is unconfirmed; retry to reconcile it.') from None
            raise CloudError('Upload is unconfirmed. Check connection and local state access, then retry to reconcile remote versions.') from None
    return dict(uploaded=uploaded, skipped=skipped, prefix=journal['prefix'])
