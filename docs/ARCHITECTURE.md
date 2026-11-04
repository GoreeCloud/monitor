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
- No notification delivery, escalation routing, certificate expiry alarms or domain expiry checks.
- Public RSS, badge and opt-in metrics endpoints are present but require runtime and security validation.
- No SSO, RBAC, multi-tenancy or TOTP yet.
- No stable public administrative API.
- No live deployment or host/platform verification is asserted.
- No MariaDB backend, distributed workers, HA or automated restore.
- HTTP uses a pinned validated destination address with host-based TLS validation. Independent security and network tests remain required for hostile environments.

## Dependencies and provenance

The code uses the Python standard library, SQLite, HTML, CSS and JavaScript. No Uptime Kuma source code is copied or embedded. The GC UI design language and visual authority are maintained separately in GoreeCloud/gc-ui.
