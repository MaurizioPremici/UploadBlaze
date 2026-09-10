# UploadBlaze Implementation Plan

Goal: make the approved two-window QML design a usable macOS desktop app with portable Python services, then install for user acceptance before public release and a Desktop ZIP.

Architecture: PySide6/QML with background workers and immutable job inputs. Archive operations use Python zipfile and py7zr, Backblaze uses b2sdk with in-memory authorization, credentials use the system keyring. All labels and errors are English. All source files are preserved, generated outputs are unique, partial files are cleaned, uploads are never accepted based on a filename suffix.

UI: main and Settings are separate 569x710 windows, original 455x568 design scaled 1.25. Add Files, Zip Files, Protect Files, Upload Backup, Stop, Settings; files list, progress, log, encryption password/confirmation. Settings contain Application Key ID, Application Key, Bucket Name, Remote Folder, Remember Key, Test Connection, Cancel and Save Settings. Native picking/drop supported. Original visual forms remain editable in Qt Design Studio.

Task 1: blaze_core/archives.py and tests/test_archives.py. Implement cancelable compression of selected regular files into one unique ZIP, validate ZIP input, protect each selected ZIP inside a 7z AES256 container with encrypted headers and no recompression, verify recovered inner bytes by hash, and preserve originals on success/error/cancel. Shared API in contracts below.
Task 2: blaze_core/cloud.py, blaze_core/settings.py and tests/test_cloud.py / test_settings.py. Use system keyring, atomically save nonsecret config, B2 restricted key authentication and private-bucket validation, upload per-file via SDK progress callback with cancel, confirm returned version ID/size/protocol checksum from remote info. Retry bookkeeping records completed fingerprints and version IDs under a stable job prefix. No test uploads to real user buckets.
Task 3: blaze_core/controller.py, __main__.py, app.py and live QML views. Wire nonblocking workers, safe progress/error signals, dialogs, queue item transitions, archive password validation, settings transactions, file chooser, drag/drop and cancellation/close protection. Only verified protected items may upload. No simulated files in runtime.
Task 4: portable PyInstaller spec/build helper, README, dependency pins; run real archive roundtrips and cloud contract tests, QML interaction checks, package macOS arm64, verify installed launch. Preserve original desktop .command scripts. GitHub publication and Desktop ZIP wait for the user's installed-app test as previously required.

Contracts:
- archives.Cancelled(Exception), archives.check_cancel(cancel: threading.Event)
- archives.zip_files(paths: list[str], output_dir: str, cancel, progress: callable(done:int,total:int,message:str)) -> str (unique resulting ZIP)
- archives.protect_zip(path: str, password: str, output_dir: str, cancel, progress) -> dict {path, sha256, size, source_sha256}; verifies decryption and inner ZIP CRCs using a private temporary plaintext file removed on all exits.
- archives.verify_protected(path: str, password: str, cancel, progress) -> dict {path, sha256, size, source_sha256}; accepts the app-compatible COPY/AES encrypted-header profile with exactly one safe ZIP filename; does not prove creator identity.
- settings.SettingsStore(directory: str) with load() -> dict, save(values:dict,key:str,remember:bool), load_key(key_id:str) -> str. Nonsecret values: key_id,bucket,prefix,remember. keyring service UploadBlaze.B2. Empty saved key does not mean successful auth. No secrets in disk JSON.
- cloud.check_connection(config:dict, key:str, cancel) -> dict {bucket, status}; validates private bucket and required writeFiles/listFiles/readFiles capabilities, uses config key_id,bucket,prefix.
- cloud.upload_files(files:list[dict], config:dict, key:str, state_dir:str, cancel, progress) -> dict {uploaded:int, skipped:int, prefix:str}. Each file is verified-protected metadata {path,sha256,size,source_sha256}. SDK account data in memory. Callback accepts (done,total,message). Validate local sha256 before transfer and report unconfirmed on uncertain outcomes; never delete remote/user files.

Verification: real filesystem archive roundtrips, wrong password/corruption/cancel/original hashes, settings transactions with fake test keyring, B2 fake service boundary calls only (no claim of live verification). UI events tested in disposable app profile. User performs live B2 acceptance. Packaging must not include secrets, local vaults, Qt Insight telemetry or development-only data.
