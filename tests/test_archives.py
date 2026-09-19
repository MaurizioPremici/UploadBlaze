"""Real archive roundtrips; all inputs live in pytest temporary directories."""
import hashlib
import os
from pathlib import Path
import threading
import zipfile

import pytest

from blaze_core import archives


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def zipped(tmp_path):
    path = tmp_path / 'original.zip'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as output:
        output.writestr('data.txt', b'important original data' * 1000)
    return path


def noop(*args):
    pass


def test_zip_roundtrip_unique_names_and_originals(tmp_path):
    left = tmp_path / 'left'
    right = tmp_path / 'right'
    left.mkdir()
    right.mkdir()
    a, b = left / 'report.txt', right / 'report.txt'
    a.write_bytes(b'first')
    b.write_bytes(b'second')
    before = [digest(a), digest(b)]
    output = tmp_path / 'out'
    result = archives.zip_files([str(a), str(b)], str(output), threading.Event(), noop)
    other = archives.zip_files([str(a)], str(output), threading.Event(), noop)
    assert result != other
    with zipfile.ZipFile(result) as archive:
        assert len(set(archive.namelist())) == 2
        assert sorted(archive.read(n) for n in archive.namelist()) == [b'first', b'second']
        assert all('/' not in n and '\\' not in n for n in archive.namelist())
    assert [digest(a), digest(b)] == before


def test_single_file_zip_keeps_the_original_basename(tmp_path):
    source = tmp_path / 'testUPLOAD.jpeg'
    source.write_bytes(b'image bytes')

    result = archives.zip_files([str(source)], str(tmp_path / 'out'), threading.Event(), noop)

    assert Path(result).name == 'testUPLOAD.zip'
    with zipfile.ZipFile(result) as archive:
        assert archive.namelist() == ['testUPLOAD.jpeg']


def test_zip_cancellation_removes_partial_and_preserves_original(tmp_path):
    source = tmp_path / 'source.bin'
    source.write_bytes(os.urandom(3 * 1024 * 1024))
    original = digest(source)
    cancel = threading.Event()
    output = tmp_path / 'out'
    def progress(done, total, message):
        if done:
            cancel.set()
    with pytest.raises(archives.Cancelled):
        archives.zip_files([str(source)], str(output), cancel, progress)
    assert digest(source) == original
    assert not list(output.iterdir())


def test_rejects_directories_symlinks_and_empty_selection(tmp_path):
    link = tmp_path / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    for selection in [[], [str(tmp_path)], [str(link)]]:
        with pytest.raises(ValueError):
            archives.zip_files(selection, str(tmp_path / 'out'), threading.Event(), noop)


def test_protection_roundtrip_encrypted_headers_copy_and_metadata(tmp_path):
    import py7zr
    source = zipped(tmp_path)
    original = digest(source)
    out = tmp_path / 'out'
    result = archives.protect_zip(str(source), 'correct password', str(out), threading.Event(), noop)
    assert result['source_sha256'] == original
    assert result['sha256'] == digest(result['path'])
    assert result['size'] == Path(result['path']).stat().st_size
    assert digest(source) == original
    assert list(out.iterdir()) == [Path(result['path'])]
    with pytest.raises(Exception):
        with py7zr.SevenZipFile(result['path']) as archive:
            archive.getnames()
    with py7zr.SevenZipFile(result['path'], password='correct password') as archive:
        assert archive.getnames() == [source.name]
        assert '7zAES' in archive.archiveinfo().method_names
        assert not any('LZMA' in method for method in archive.archiveinfo().method_names)
    assert archives.verify_protected(result['path'], 'correct password', threading.Event(), noop) == result


def test_wrong_password_and_corruption_fail_without_plaintext(tmp_path):
    source = zipped(tmp_path)
    result = archives.protect_zip(str(source), 'correct password', str(tmp_path / 'out'), threading.Event(), noop)
    before = set(tmp_path.rglob('*'))
    with pytest.raises(ValueError):
        archives.verify_protected(result['path'], 'wrong password', threading.Event(), noop)
    assert set(tmp_path.rglob('*')) == before
    payload = Path(result['path']).read_bytes()
    Path(result['path']).write_bytes(payload[:len(payload)//2])
    with pytest.raises(ValueError):
        archives.verify_protected(result['path'], 'correct password', threading.Event(), noop)
    assert set(tmp_path.rglob('*')) == before


def test_protection_rejects_fake_zip_and_empty_password(tmp_path):
    source = tmp_path / 'fake.zip'
    source.write_text('not a ZIP')
    for password in ['', 'real password']:
        with pytest.raises(ValueError):
            archives.protect_zip(str(source), password, str(tmp_path / 'out'), threading.Event(), noop)
    assert not (tmp_path / 'out').exists() or not list((tmp_path / 'out').iterdir())


def test_protection_cancellation_preserves_original_and_cleans_output(tmp_path):
    source = zipped(tmp_path)
    original = digest(source)
    output = tmp_path / 'out'
    cancel = threading.Event()
    def progress(done, total, message):
        if message.startswith('Protecting') and done:
            cancel.set()
    with pytest.raises(archives.Cancelled):
        archives.protect_zip(str(source), 'password', str(output), cancel, progress)
    assert digest(source) == original
    assert not output.exists() or not list(output.iterdir())


@pytest.mark.parametrize('name,encrypted', [('inside.zip', False), ('../inside.zip', True), ('inside.txt', True)])
def test_verify_rejects_unencrypted_unsafe_or_nonzip_members(tmp_path, name, encrypted):
    import py7zr
    source = zipped(tmp_path)
    target = tmp_path / 'outside.7z'
    with py7zr.SevenZipFile(target, 'w', password='password' if encrypted else None, header_encryption=encrypted) as archive:
        archive.write(source, arcname=name)
    with pytest.raises(ValueError):
        archives.verify_protected(str(target), 'password', threading.Event(), noop)


def test_large_binary_and_empty_zip_roundtrip(tmp_path):
    payload = os.urandom(3 * 1024 * 1024 + 137)
    source = tmp_path / 'large.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('binary.dat', payload)
    calls = []
    result = archives.protect_zip(str(source), 'a private phrase', str(tmp_path / 'out'), threading.Event(), lambda *args: calls.append(args))
    assert result['source_sha256'] == digest(source)
    assert any(done > 1024 * 1024 for done, _, message in calls if message.startswith('Protecting'))
    assert all('a private phrase' not in message for _, _, message in calls)
    empty = tmp_path / 'empty.zip'
    with zipfile.ZipFile(empty, 'w'):
        pass
    result = archives.protect_zip(str(empty), 'password', str(tmp_path / 'out'), threading.Event(), noop)
    assert result['source_sha256'] == digest(empty)


def test_cancel_during_decryption_leaves_only_encrypted_output(tmp_path):
    source = zipped(tmp_path)
    result = archives.protect_zip(str(source), 'password', str(tmp_path / 'out'), threading.Event(), noop)
    before = set(tmp_path.rglob('*'))
    cancel = threading.Event()
    def progress(done, total, message):
        if message.startswith('Verifying'):
            cancel.set()
    with pytest.raises(archives.Cancelled):
        archives.verify_protected(result['path'], 'password', cancel, progress)
    assert set(tmp_path.rglob('*')) == before


def test_corrupted_inner_zip_is_rejected_before_output(tmp_path):
    source = tmp_path / 'corrupted.zip'
    with zipfile.ZipFile(source, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('data', b'KNOWN_CONTENT')
    data = source.read_bytes().replace(b'KNOWN_CONTENT', b'WRONG_CONTENT')
    source.write_bytes(data)
    before = digest(source)
    with pytest.raises(ValueError):
        archives.protect_zip(str(source), 'password', str(tmp_path / 'out'), threading.Event(), noop)
    assert digest(source) == before
    assert not (tmp_path / 'out').exists()


def test_verify_rejects_multiple_members_and_fake_inner_zip(tmp_path):
    import py7zr
    source = zipped(tmp_path)
    for count in (1, 2):
        output = tmp_path / f'invalid-{count}.7z'
        with py7zr.SevenZipFile(output, 'w', password='password', header_encryption=True) as archive:
            if count == 1:
                archive.writestr(b'This is not really a ZIP archive despite its name.', 'fake.zip')
            else:
                archive.write(source, 'one.zip')
                archive.write(source, 'two.zip')
        with pytest.raises(ValueError):
            archives.verify_protected(str(output), 'password', threading.Event(), noop)


def test_zip_input_change_aborts_and_removes_partial(tmp_path):
    source = tmp_path / 'change.bin'
    source.write_bytes(os.urandom(2 * 1024 * 1024))
    out = tmp_path / 'out'
    modified = False
    def progress(done, total, message):
        nonlocal modified
        if not modified:
            with source.open('ab') as stream:
                stream.write(b'modified by concurrent writer')
            modified = True
    with pytest.raises(ValueError, match='changed'):
        archives.zip_files([str(source)], str(out), threading.Event(), progress)
    assert not list(out.iterdir())


def test_already_cancelled_has_no_side_effects(tmp_path):
    cancel = threading.Event()
    cancel.set()
    out = tmp_path / 'out'
    with pytest.raises(archives.Cancelled):
        archives.zip_files([], str(out), cancel, noop)
    with pytest.raises(archives.Cancelled):
        archives.protect_zip('missing.zip', 'password', str(out), cancel, noop)
    assert not out.exists()


def test_verify_requires_copy_aes_profile_and_encrypted_headers(tmp_path):
    import py7zr
    source = zipped(tmp_path)
    for headers, filters in [(True, None), (False, [{'id': py7zr.FILTER_COPY}, {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}])]:
        output = tmp_path / f'other-profile-{headers}.7z'
        with py7zr.SevenZipFile(output, 'w', password='password', header_encryption=headers, filters=filters) as archive:
            archive.write(source, 'inner.zip')
        with pytest.raises(ValueError):
            archives.verify_protected(str(output), 'password', threading.Event(), noop)


def protected_fixture(tmp_path, corrupt=False):
    """Build a real encrypted container independently of the production verifier."""
    import py7zr
    source = tmp_path / 'fixture.zip'
    with zipfile.ZipFile(source, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('data', b'KNOWN_CONTENT' * 1000)
    if corrupt:
        source.write_bytes(source.read_bytes().replace(b'KNOWN_CONTENT', b'WRONG_CONTENT', 1))
    output = tmp_path / 'fixture.7z'
    with py7zr.SevenZipFile(output, 'w', password='password', header_encryption=True,
            filters=[{'id': py7zr.FILTER_COPY}, {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}]) as archive:
        archive.write(source, 'inner.zip')
    return output


def test_verify_rejects_valid_7z_with_corrupted_inner_member_crc(tmp_path):
    protected = protected_fixture(tmp_path, corrupt=True)
    before = digest(protected)
    with pytest.raises(ValueError):
        archives.verify_protected(str(protected), 'password', threading.Event(), noop)
    assert digest(protected) == before


@pytest.mark.parametrize('outcome', ['success', 'crc_error', 'cancel_decrypt', 'cancel_crc'])
def test_private_plaintext_temporary_closes_for_every_outcome(tmp_path, monkeypatch, outcome):
    import stat
    protected = protected_fixture(tmp_path, corrupt=outcome == 'crc_error')
    created = []
    real_temporary_file = archives.tempfile.TemporaryFile
    def tracked_file(*args, **kwargs):
        temp = real_temporary_file(*args, **kwargs)
        assert stat.S_IMODE(os.fstat(temp.fileno()).st_mode) == 0o600
        if os.name == 'posix':
            assert os.fstat(temp.fileno()).st_nlink == 0
        created.append(temp)
        return temp
    monkeypatch.setattr(archives.tempfile, 'TemporaryFile', tracked_file)
    before = set(tmp_path.rglob('*'))
    cancel = threading.Event()
    def progress(done, total, message):
        if outcome == 'cancel_decrypt' and message.startswith('Verifying decrypted'):
            cancel.set()
        if outcome == 'cancel_crc' and message.startswith('Validating ZIP'):
            cancel.set()
    if outcome == 'success':
        archives.verify_protected(str(protected), 'password', cancel, progress)
    else:
        with pytest.raises(archives.Cancelled if outcome.startswith('cancel') else ValueError):
            archives.verify_protected(str(protected), 'password', cancel, progress)
    assert len(created) == 1
    assert created[0].closed
    assert set(tmp_path.rglob('*')) == before


def test_verification_disk_full_closes_private_temp_and_preserves_input(tmp_path, monkeypatch):
    import errno
    protected = protected_fixture(tmp_path)
    before = digest(protected)
    real_temporary_file = archives.tempfile.TemporaryFile
    opened = []
    class FullDisk:
        def __init__(self, temp):
            self.temp = temp
        def __getattr__(self, name):
            return getattr(self.temp, name)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.temp.close()
        def write(self, data):
            raise OSError(errno.ENOSPC, 'No space left on device')
    def full_file(*args, **kwargs):
        temp = real_temporary_file(*args, **kwargs)
        opened.append(temp)
        return FullDisk(temp)
    monkeypatch.setattr(archives.tempfile, 'TemporaryFile', full_file)
    with pytest.raises(ValueError, match='disk space'):
        archives.verify_protected(str(protected), 'password', threading.Event(), noop)
    assert len(opened) == 1 and opened[0].closed
    assert digest(protected) == before


def test_metadata_only_change_during_verification_keeps_valid_archive(tmp_path):
    source = zipped(tmp_path)
    result = archives.protect_zip(str(source), 'correct password', str(tmp_path / 'out'), threading.Event(), noop)
    path = Path(result['path'])
    changed = False
    def metadata_update(done, total, message):
        nonlocal changed
        if not changed and message.startswith('Verifying decrypted'):
            changed = True
            before = path.stat()
            path.chmod(0o400 if before.st_mode & 0o200 else 0o600)
            after = path.stat()
            assert before.st_mtime_ns == after.st_mtime_ns
            assert before.st_size == after.st_size
    checked = archives.verify_protected(str(path), 'correct password', threading.Event(), metadata_update)
    assert changed
    assert checked == result


def test_content_change_even_with_restored_mtime_is_rejected(tmp_path):
    source = zipped(tmp_path)
    result = archives.protect_zip(str(source), 'correct password', str(tmp_path / 'out'), threading.Event(), noop)
    path = Path(result['path'])
    changed = False
    def content_update(done, total, message):
        nonlocal changed
        if not changed and message.startswith('Validating ZIP'):
            changed = True
            before = path.stat()
            with path.open('r+b') as stream:
                original = stream.read(1)
                stream.seek(0)
                stream.write(bytes([original[0] ^ 1]))
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(ValueError, match='changed during verification'):
        archives.verify_protected(str(path), 'correct password', threading.Event(), content_update)
    assert changed
