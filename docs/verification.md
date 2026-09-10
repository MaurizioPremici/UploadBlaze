# Local verification — 2026-09-10

- Python 3.11.16, macOS Apple Silicon; pinned dependencies in requirements files.
- Final suite: `QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest tests -q` — **72 passed in 15.73 s**.
- Real filesystem tests cover ZIP/7z roundtrips, inner ZIP corruption, wrong passwords, input mutation, temporary-file cleanup, cancellation, disk-full handling and preservation of originals.
- B2 tests use offline doubles and the SDK simulator, including multipart behavior. They do not prove live account/network behavior. Credentials tests use a fake keyring; no real user credentials were loaded or saved by the tests.
- The QML test loads the actual forms, clicks Zip/Protect/Settings/Save/Stop, verifies produced archives and nonsecret settings, and checks that editing settings clears an earlier successful connection-test display. Its connection endpoint is stubbed. Both windows measure 569 × 710. Rendered screenshots were inspected.
- A read-only review found and prompted fixes for unverified upload bytes after source replacement, incomplete imported ZIP validation, and corrupt-settings recovery; the fixes and their regression tests were reviewed.
- PyInstaller produced `dist/UploadBlaze.app` (arm64). `codesign --verify --deep --strict` passed before installation and on the installed copy.
- Installed `/Applications/UploadBlaze.app`, with `~/Desktop/UploadBlaze.app` pointing to it. The installed app opened its main window and separate Settings window. Further automated UI interaction stopped when the window was being used. No packaged live upload or restore is claimed.
- The build reports an unused Qt labs assetdownloader plugin absent from the PySide6 distribution; the app does not import that module. Other missing-module reports concern optional/platform-specific backends.

Pending acceptance: user's real B2 connection, upload and restore; native Windows/Linux builds and tests; macOS distribution signing/notarization if distributing beyond local testing. Public GitHub release and Desktop backup ZIP remain gated on the user's successful installed-app trial.

## Follow-up acceptance and fix — 2026-09-10

- Final regression suite after the metadata fix: **80 passed in 53.85 s**.
- Reproduced a real Desktop failure: device/inode/size/mtime stayed equal while only ctime changed. Verification incorrectly classified this metadata update as changed archive content and masked the cause with a password error. Content checks now exclude ctime and compare SHA-256 before and after decryption. Genuine changes still fail, including a test restoring mtime. ArchiveChangedError is reported distinctly.
- After the fix, 12 consecutive real Desktop protect/verify roundtrips passed. The rebuilt app was installed and its signature verified. Its live activity log subsequently showed successful Desktop protection and confirmed upload.
- macOS 15.3.1, Archive Utility 10.15 (162): correct known test password was repeatedly rejected for UploadBlaze COPY/AES, a py7zr LZMA2/AES fixture, and official 7-Zip encrypted fixtures with and without encrypted headers. The Unarchiver 4.3.8 (146) extracted the same UploadBlaze fixture and recovered a byte-identical ZIP. Official 7-Zip 26.03 also recovered an identical ZIP. The README and GUI now name compatible extractors.
- Real B2 test using saved credentials: private-bucket check, upload of a disposable encrypted fixture, identical batch retry (0 uploaded / 1 skipped), download SHA-256 equality, and independent extraction passed.
- Real 32 MiB in-flight upload cancellation was acknowledged. Retrying the same batch completed successfully; its downloaded SHA-256 matched the original protected archive. One earlier attempt stopped on a pre-transfer connection error; authorization was rechecked and the subsequent attempt passed.
- Two disposable acceptance backup objects remain in the configured private bucket, one small archive and one about 32 MiB. No user backup objects were removed. Remote prefixes and local diagnostic paths are kept in a temporary acceptance record outside this source tree.
- Local original/download pairs supplied during diagnosis also matched by SHA-256. Their private passwords were not used in automated tests.

Remaining limits: Windows/Linux native builds and credential-store tests are still outstanding. Changing Remember Key against the user's production credential was deliberately avoided; save/remove rollback behavior is covered by isolated tests. Native app input/output and logs were inspected; exhaustive native interaction under every timing condition is not claimed. Public GitHub and Desktop release ZIP remain subject to the user's release decision.
