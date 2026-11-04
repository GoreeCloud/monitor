# GoreeCloud Monitor — Operations, Backup and Recovery

| Control | Value |
| --- | --- |
| Owner | GoreeCloud |
| Document status | Development-stage operating procedure |
| Canonical path | GoreeCloud/monitor/docs/OPERATIONS.md |
| Last updated | 2026-11-04 |

## Scope and safety

This document describes local development and recoverability validation. It does not authorize connecting the monitor to production services, changing DNS, publishing a public monitoring endpoint, mounting the host Docker socket or modifying live backups.

## Initial local verification

The standard-library service requires Python 3.12+. Install no extra dependencies for the core test suite.

    python3 -m compileall -q monitor tests
    python3 -m unittest discover -s tests -v
    node --check web/app.js

Run the app on loopback with a strong password stored in a permission-restricted secret file:

    export GC_ADMIN_PASSWORD_FILE=/a/private/path/password.txt
    export GC_DATA_DIR=/a/private/path/monitor-data
    export GC_HOST=127.0.0.1
    export GC_PORT=3001
    python3 -m monitor.server

The default port, private data directory and password-file path are examples, not an indication that a live service has been deployed.

## Online backup

Ensure destination directory exists, is access-controlled and is on storage with sufficient free space. The destination file must not exist:

    GC_DATA_DIR=/a/private/path/monitor-data \
      python3 -m monitor.backup /a/private/backups/monitor-snapshot.sqlite3

The helper uses SQLite's consistent backup API, verifies snapshot integrity, creates a mode-0600 file and reports a SHA-256 checksum. It does not overwrite an existing destination. A scratch-directory restore regression test and symlink non-overwrite test are included. Additional development CI regressions exercise **uncheckpointed committed WAL writes while another transaction is open**: the snapshot must preserve committed rows, exclude uncommitted rows, pass integrity checks, retain private maintenance visibility and boot from an isolated single-file restore. Corrupt-source failures must leave no published destination or temporary snapshot. Record the checksum separately in an authorized private location; do not publish snapshot data, monitor targets or secrets.

## Restore procedure — controlled and offline only

1. Identify the correct source snapshot and verify its checksum and SQLite integrity on an isolated scratch host.
2. Stop all GoreeCloud Monitor service instances that access the target SQLite data directory.
3. Preserve an independently recoverable copy of the currently installed data directory, including WAL and SHM files if present.
4. Restore only into an empty, private data directory on an isolated validation host. Name the restored database monitor.sqlite3, and apply the correct file ownership and permissions. **Never reuse WAL or SHM files from a different database snapshot.**
5. Run the target application version against the restored scratch directory and verify monitor count, settings, heartbeats, incidents, maintenance and public/private visibility.
6. Verify health, authentication and operating-system permissions before considering a production recovery.
7. Only after independent recovery evidence and appropriate authorization should a production restore or cutover be evaluated.

Do not delete production data, copy back a scratch restoration, or change running services solely by following this reference document.

## Isolated container acceptance

The CI workflow builds the image and runs the local-only acceptance script:

    docker build --tag goreecloud-monitor:ci .
    python3 tests/container_smoke.py goreecloud-monitor:ci

The script inspects the image's nonroot user and retained healthcheck, then
starts an ephemeral container with a read-only filesystem, temporary writable
data storage, dropped capabilities, and **no external network access or
published host ports**. It checks readiness, authentication, CSRF protection,
private status isolation, push heartbeat delivery, cleanup, and logout.
Only an unmistakable CI-only password fixture is used. This is an integration
smoke test, not production certification, reverse-proxy testing, or a
substitute for independent security review.

Podman's default OCI image format may discard Dockerfile HEALTHCHECK metadata.
For local Podman acceptance requiring that metadata, build with:

    podman build --pull=never --format docker --tag goreecloud-monitor:local .

The no-pull flag requires a pre-cached base image; do not infer that an
uncached offline build will work. No server or host port needs to be published
for the CI acceptance script.

## Automated desktop/mobile browser acceptance (development CI)

The isolated CI workflow runs a preinstalled headless Chrome browser, Node.js
22+, and the project's dependency-free `tests/browser_smoke.mjs` script:

    node tests/browser_smoke.mjs

This starts a **loopback-only development instance** backed by temporary
SQLite storage, exercises real login, private push-monitor creation, search,
filtering, keyboard navigation and public/private status boundaries, and
checks desktop (1280px) and mobile (390px) layouts for page overflow. The
mobile navigation test verifies every destination is visible in its two-row
grid. It generates four screenshot files under `artifacts/browser-ui/`; the
CI artifact is retained for three days for human inspection.

The test uses a fake CI password and dummy push service. Before screenshot
capture, it scrubs the generated one-time push URL from the notice. Never run
this script pointed at a production instance, export real session data into
artifacts, or treat its CI screenshots as proof of manual screen-reader,
cross-browser, accessible contrast, TLS reverse-proxy, or Android acceptance.

## Operational monitoring

The /healthz endpoint reports basic service responsiveness, not dependency health or proof that all scheduled checks are executing. Protected /metrics can provide operational counters when configured with a strong GC_METRICS_TOKEN. Review logs for database errors and notify connector failures, but never log or publish credentials, heartbeat tokens or private URLs.

## Known gaps

No tested deployment image, external TLS configuration, automated backup rotation, offsite encryption, alert retries, HA service or full browser visual acceptance is currently claimed. GitHub Actions success demonstrates only its configured validation steps.
