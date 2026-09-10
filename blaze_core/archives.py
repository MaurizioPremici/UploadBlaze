"""Streaming local archives. Originals are never rewritten.

Verification decrypts into a private system TemporaryFile, then streams every ZIP
member for CRC validation. The temporary is always closed and removed; its disk
space requirement is the size of the inner ZIP. No files are extracted into user
input or output directories.

Cancellation is cooperative between I/O blocks. py7zr header parsing and AES key
setup are synchronous; those small library operations cannot be interrupted.
"""
from __future__ import annotations

import errno
import hashlib
import io
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
from typing import Callable
import uuid
import zipfile

import py7zr
from py7zr.exceptions import PasswordRequired
from py7zr.io import Py7zIO, WriterFactory

Progress = Callable[[int, int, str], None]
_BLOCK = 1024 * 1024


class ArchiveChangedError(ValueError):
    """The bytes changed while the archive was being verified."""


class Cancelled(Exception):
    """A cooperative cancellation stopped the operation."""


def check_cancel(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise Cancelled('Operation cancelled.')


def _regular(path: str) -> Path:
    source = Path(path).absolute()
    try:
        info = source.lstat()
    except OSError as exc:
        raise ValueError('The selected file is unavailable.') from exc
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Select regular files only; folders and symbolic links are unsupported.')
    return source


def _open_regular(path: Path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('The selected input is not a regular file.')
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


def _identity(stream):
    info = os.fstat(stream.fileno())
    # ctime also changes for permissions/xattrs; those changes do not alter data.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _safe_name(name: str) -> bool:
    return bool(name and name not in ('.', '..') and not re.search(r'[\\/:\x00-\x1f\x7f]', name))


def _output(output_dir: str, stem: str, extension: str):
    directory = Path(output_dir).absolute()
    directory.mkdir(parents=True, exist_ok=True)
    # Random names avoid replacing any source or previous result.
    final = directory / f'{stem}-{uuid.uuid4().hex[:12]}{extension}'
    fd, name = tempfile.mkstemp(prefix='.uploadblaze-', suffix='.part', dir=directory)
    return final, Path(name), os.fdopen(fd, 'w+b')


def _publish(part: Path, final: Path):
    # Hard-link creation is atomic and refuses to replace an existing file.
    os.link(part, final)
    part.unlink()


def zip_files(paths: list[str], output_dir: str, cancel, progress: Progress) -> str:
    check_cancel(cancel)
    if not paths:
        raise ValueError('Select at least one regular file.')
    sources = [_regular(path) for path in paths]
    if any(not _safe_name(path.name) for path in sources):
        raise ValueError('A selected filename contains unsupported characters.')
    total = sum(path.stat().st_size for path in sources)
    final, part, target = _output(output_dir, 'Backup', '.zip')
    done = 0
    used = set()
    try:
        with target, zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for source in sources:
                check_cancel(cancel)
                name = source.name
                counter = 2
                while name.casefold() in used:
                    name = f'{source.stem} ({counter}){source.suffix}'
                    counter += 1
                used.add(name.casefold())
                with _open_regular(source) as stream, archive.open(name, 'w', force_zip64=True) as member:
                    identity = _identity(stream)
                    while True:
                        check_cancel(cancel)
                        chunk = stream.read(_BLOCK)
                        if not chunk:
                            break
                        member.write(chunk)
                        done += len(chunk)
                        progress(done, total, f'Compressing {source.name}')
                    if identity != _identity(stream):
                        raise ValueError('An input changed during compression; retry with stable files.')
            check_cancel(cancel)
        _publish(part, final)
        return str(final)
    finally:
        target.close()
        part.unlink(missing_ok=True)


def _validate_zip(stream, cancel, progress):
    try:
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            total = sum(entry.file_size for entry in entries)
            done = 0
            for entry in entries:
                check_cancel(cancel)
                with archive.open(entry) as member:
                    while True:
                        check_cancel(cancel)
                        chunk = member.read(_BLOCK)
                        if not chunk:
                            break
                        done += len(chunk)
                        progress(done, total, 'Validating ZIP contents')
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as exc:
        raise ValueError('The input must be a readable, uncorrupted ZIP archive.') from exc
    finally:
        stream.seek(0)


class _SourceReader(io.BufferedReader):
    def __init__(self, raw, cancel, progress, total):
        super().__init__(raw)
        self.cancel = cancel
        self.progress = progress
        self.total = total
        self.done = 0
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        check_cancel(self.cancel)
        data = super().read(_BLOCK if size < 0 else min(size, _BLOCK))
        self.digest.update(data)
        self.done += len(data)
        self.progress(self.done, self.total, 'Protecting ZIP with AES-256')
        check_cancel(self.cancel)
        return data


class _HashSink(Py7zIO):
    """Hash decrypted bytes into a privately owned seekable temporary file.

    The caller owns and closes the temporary even if py7zr raises mid-extraction.
    py7zr's output close hook must not close it before ZIP validation completes.
    """
    def __init__(self, plaintext, expected, cancel, progress):
        self.plaintext = plaintext
        self.expected = expected
        self.cancel = cancel
        self.progress = progress
        self.count = 0
        self.digest = hashlib.sha256()

    def write(self, data):
        check_cancel(self.cancel)
        if self.count + len(data) > self.expected:
            raise ValueError('The protected member exceeds its declared size.')
        written = self.plaintext.write(data)
        if written != len(data):
            raise OSError(errno.EIO, 'Incomplete write to the private verification temporary file.')
        self.digest.update(data)
        self.count += written
        self.progress(self.count, self.expected, 'Verifying decrypted ZIP bytes')
        check_cancel(self.cancel)
        return written

    def read(self, size=None):
        check_cancel(self.cancel)
        return self.plaintext.read(_BLOCK if size is None else size)

    def seek(self, offset, whence=0):
        check_cancel(self.cancel)
        return self.plaintext.seek(offset, whence)

    def flush(self):
        check_cancel(self.cancel)
        self.plaintext.flush()

    def size(self):
        return self.count

    def validate(self):
        check_cancel(self.cancel)
        if self.count != self.expected:
            raise ValueError('The decrypted ZIP size does not match the protected member.')
        self.plaintext.flush()
        self.plaintext.seek(0)
        _validate_zip(self.plaintext, self.cancel, self.progress)
        check_cancel(self.cancel)


class _HashFactory(WriterFactory):
    def __init__(self, name, sink):
        self.name = name
        self.sink = sink
        self.created = False

    def create(self, filename):
        if filename != self.name or self.created:
            raise ValueError('The protected archive contains unexpected members.')
        self.created = True
        return self.sink


def verify_protected(path: str, password: str, cancel, progress: Progress) -> dict:
    """Verify AES/header encryption, one safe ZIP member, CRC, size and SHA-256.

    Metadata describes current bytes; it is not proof of the archive's creator.
    The decrypted ZIP uses a private system temporary file for full member CRC
    validation; it is closed and removed on success, failure, and cancellation.
    """
    check_cancel(cancel)
    if not password:
        raise ValueError('Enter an encryption password.')
    source = _regular(path)
    try:
        with _open_regular(source) as stream:
            identity = _identity(stream)
            # Bind the bytes being decrypted to the final upload fingerprint.
            # A content hash catches changes even if mtime is restored; ctime
            # alone would falsely reject background metadata updates on Desktop.
            initial_hash = hashlib.sha256()
            while data := stream.read(_BLOCK):
                check_cancel(cancel)
                initial_hash.update(data)
            stream.seek(0)
            # A readable header without a password would expose its ZIP filename.
            try:
                with py7zr.SevenZipFile(stream, 'r'):
                    pass
            except PasswordRequired:
                pass
            else:
                raise ValueError('The archive must use encrypted headers.')
            check_cancel(cancel)
            stream.seek(0)
            with py7zr.SevenZipFile(stream, 'r', password=password) as archive:
                entries = archive.list()
                if len(entries) != 1:
                    raise ValueError('The protected archive must contain exactly one ZIP file.')
                member = entries[0]
                if not member.is_file or member.is_directory or member.is_symlink or not _safe_name(member.filename) or not member.filename.lower().endswith('.zip'):
                    raise ValueError('The protected archive must contain one regular, safe ZIP filename.')
                if set(archive.archiveinfo().method_names) != {'COPY', '7zAES'} or not archive.needs_password():
                    raise ValueError('The archive must use the UploadBlaze COPY and AES-256 profile.')
                if member.uncompressed < 22:
                    raise ValueError('The protected ZIP member is too small.')
                with tempfile.TemporaryFile(mode='w+b', prefix='uploadblaze-verify-') as plaintext:
                    sink = _HashSink(plaintext, member.uncompressed, cancel, progress)
                    factory = _HashFactory(member.filename, sink)
                    archive.extractall(factory=factory)
                    sink.validate()
            check_cancel(cancel)
            stream.seek(0)
            outer = hashlib.sha256()
            done = 0
            while True:
                check_cancel(cancel)
                data = stream.read(_BLOCK)
                if not data:
                    break
                outer.update(data)
                done += len(data)
                progress(done, identity[2], 'Hashing protected archive')
            check_cancel(cancel)
            if _identity(stream) != identity or outer.digest() != initial_hash.digest():
                raise ArchiveChangedError('The protected archive changed during verification. Retry with a stable file.')
            return {'path': str(source), 'sha256': outer.hexdigest(), 'size': identity[2], 'source_sha256': sink.digest.hexdigest()}
    except (Cancelled, ArchiveChangedError):
        raise
    except OSError as exc:
        if exc.errno in (errno.ENOSPC, getattr(errno, 'EDQUOT', errno.ENOSPC)):
            raise ValueError('Insufficient temporary disk space to verify the protected ZIP.') from exc
        raise ValueError('Archive verification I/O failed. Check temporary disk space, permissions, and file availability.') from exc
    except Exception as exc:
        # Library crypto/parse errors must not escape with low-level context into UI.
        raise ValueError('Protected archive verification failed: wrong password, damaged file, or unsupported archive structure.') from exc


def protect_zip(path: str, password: str, output_dir: str, cancel, progress: Progress) -> dict:
    check_cancel(cancel)
    if not password:
        raise ValueError('Enter an encryption password.')
    source = _regular(path)
    if source.suffix.lower() != '.zip' or not _safe_name(source.name):
        raise ValueError('Select a ZIP file with a safe filename.')
    part = None
    target = None
    try:
        with _open_regular(source) as raw:
            identity = _identity(raw)
            _validate_zip(raw, cancel, progress)
            if _identity(raw) != identity:
                raise ValueError('The source changed during ZIP validation.')
            final, part, target = _output(output_dir, source.stem, '.7z')
            with _SourceReader(raw, cancel, progress, identity[2]) as stream:
                with target, py7zr.SevenZipFile(target, 'w', password=password, header_encryption=True,
                        filters=[{'id': py7zr.FILTER_COPY}, {'id': py7zr.FILTER_CRYPTO_AES256_SHA256}]) as archive:
                    archive.writef(stream, source.name)
                    check_cancel(cancel)
                if _identity(stream) != identity:
                    raise ValueError('The source changed during encryption.')
                expected = stream.digest.hexdigest()
            verified = verify_protected(str(part), password, cancel, progress)
            if verified['source_sha256'] != expected:
                raise ValueError('Decrypted bytes do not match the source ZIP.')
            check_cancel(cancel)
            _publish(part, final)
            verified['path'] = str(final)
            return verified
    finally:
        if target is not None:
            target.close()
        if part is not None:
            part.unlink(missing_ok=True)
