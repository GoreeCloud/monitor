# GoreeCloud Monitor — Architecture and Operations

| Metadata | Value |
| --- | --- |
| Owner | GoreeCloud |
| Version | 0.1.0 development |
| Updated | 2026-11-04 |
| Canonical path | docs/ARCHITECTURE.md |

## Components

- monitor/server.py: Python HTTP server, administrator authentication, REST-style endpoints, validation and scheduling.
- SQLite: persistent monitor configuration, heartbeat history, manual incidents and maintenance.
- Scheduler: two-second polling loop and bounded thread pool (eight workers), independent monitor schedules and two-failure outage threshold.
- Web: browser UI, status page, service lists, recent events, monitor creation and lifecycle actions.
- Dockerfile/compose.yaml: development-stage Linux container deployment recipe, nonroot user, local port binding and secret file.
- GitHub Actions: syntax and unit-test validation on push/PR.

## Data model

Monitors hold name, check type, target, frequency, timeout, HTTP status/keyword expectations, current state, private/public flag and an optional SHA-256 digest of the push token. Heartbeats hold check times, results and response latencies. Incidents and maintenance are stored as separate records. The initial implementation retains at most 2000 heartbeats per monitor; this is NOT an advanced time-based retention policy.

## Scheduling semantics

Each enabled HTTP/TCP/DNS monitor runs when due. A per-monitor in-flight set prevents duplicate overlapping scheduled checks. Two consecutive failed checks are required to mark a previously healthy or pending monitor down. A successful check marks it up. Push monitors receive a unique secret token returned only at creation; a missing heartbeat beyond two intervals transitions the monitor down.

## Backup

Stop the app or use SQLite's online backup API for consistent database snapshots. Preserve /data or GC_DATA_DIR securely, including WAL/SHM when copying a live database. Restore on a staging instance before using it in production. No automated backup job or tested restore utility is shipped yet.

## Reverse proxy

Keep container service bound to 127.0.0.1 and publish through an HTTPS reverse proxy. Configure GC_COOKIE_SECURE=1 in TLS-protected environments. If testing locally without TLS, run the native Python service on 127.0.0.1 with GC_COOKIE_SECURE=0. Do not expose development versions to untrusted networks.

## Operational limitations

- No full Docker, network protocol or database-specific probe portfolio yet.
- Optional best-effort outbound GoreeCloud Notify v1 connector; no durable alert queue, escalation routing, certificate expiry alarms or domain expiry checks.
- Public RSS, badge and opt-in metrics endpoints are present but require runtime and security validation.
- No SSO, RBAC, multi-tenancy or TOTP yet.
- No stable public administrative API.
- No live deployment or host/platform verification is asserted.
- No MariaDB backend, distributed workers, HA or automated restore.
- HTTP uses a pinned validated destination address with host-based TLS validation. Independent security and network tests remain required for hostile environments.

## Dependencies and provenance

The code uses the Python standard library, SQLite, HTML, CSS and JavaScript. No Uptime Kuma source code is copied or embedded. The GC UI design language and visual authority are maintained separately in GoreeCloud/gc-ui.


## GoreeCloud Notify integration

Transition alerts are dispatched asynchronously from a bounded two-worker pool. The target is operator-configured using GC_NOTIFY_URL, GC_NOTIFY_TOKEN_FILE and GC_NOTIFY_TOPIC; disabled when unset. HTTPS uses a validated, pinned public destination and TLS hostname verification. Loopback HTTP to 127.0.0.1 is supported for same-host development. No third-party provider credentials are bundled. The connector is alpha and best-effort, not guaranteed notification delivery.


## Private maintenance and schema evolution

Maintenance entries now carry a public INTEGER column defaulting to zero. On application startup, existing databases without this column receive an in-place ALTER TABLE migration that preserves original records and treats them as unpublished. Public status retrieval filters for public=1. The maintenance scheduler itself remains global in this early foundation and still requires per-monitor scoping.

## Push protection

Each valid push-token digest receives a 120-submission rolling-minute limit in process memory. Accepted requests record heartbeat history. Denied requests return HTTP 429. Restart clears the counter and independent workers do not share it.

## Backup process

The optional monitor.backup module connects to SQLite's online-backup API with the source database opened read-only. It verifies PRAGMA integrity_check on the snapshot, stores an owner-restricted temporary file in the destination directory, atomically links to a new destination name, and reports a SHA-256 digest. Existing files are not overwritten. The helper does not provide restore automation, encryption, offsite storage or schedules. Follow [OPERATIONS.md](OPERATIONS.md) for cautious recovery.

## Recent check pass-rate analytics

The authenticated /api/stats endpoint reports recorded check counts, successful counts, success rate and average response latency over the previous 24 hours. Public status JSON includes aggregates only for monitors explicitly marked public. This is a sample-based metric, **not time-weighted uptime**; records with no recent checks yield a null percentage.

## Service health and readiness

The /healthz endpoint only establishes that the Python HTTP server responds. The separate /readyz endpoint queries the SQLite monitor table and returns HTTP 503 when the database is unavailable. The example Docker image uses this readiness endpoint for its container health check. These checks do not prove that individual monitors or scheduled probes are operational, and an external runtime deployment remains unverified.

### Private versus public maintenance status

Operational maintenance checks consider all active windows, while public status rendering considers only explicitly published active windows. This prevents a nonpublic maintenance schedule from exposing its existence through otherwise public monitor status labels. The first implementation still uses global rather than per-monitor maintenance scope.

## Monitor updates and secret rotation

Monitor type is immutable to preserve the correct authentication/probe model. The PATCH endpoint admits a strict allowlist of configuration fields and uses the existing validation rules. Health-affecting changes reset stale state. POST /api/monitors/{id}/rotate-token replaces the stored hash of a push URL's secret and returns a new token once; old tokens are immediately rejected. This release does not include a dual-token grace period, remote client reconfiguration, or a credential delivery service.
