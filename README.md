# GoreeCloud Monitor

**Know what is running. Detect what is failing. Understand what matters.**

GoreeCloud Monitor is a privacy-first, self-hosted uptime, service-health and incident-awareness application built for the GoreeCloud ecosystem. The repository contains an original Python monitoring service and a responsive web console, built around the active GoreeCloud UI design language.

> **Maturity: 0.1.0 development foundation, not production-ready.** The owner's 30-section product specification is the target scope. The working subset and important gaps are documented in [Features](docs/FEATURES.md) and [Roadmap](docs/ROADMAP.md). Publishing code does not imply an instance is running or deployed.

## What works in the initial implementation

- HTTP/HTTPS GET checks with status-code and optional keyword validation.
- TCP port checks, DNS name resolution checks, and token-based push heartbeats.
- Background scheduler, per-monitor intervals, timeouts and consecutive-failure thresholds.
- SQLite WAL persistence for monitors and bounded heartbeat history; consistent non-overwriting backup utility.
- Private authenticated administrator console with session cookie and anti-CSRF token.
- Creation, pausing, resuming and removal of monitors; recent activity and summary cards.
- Public status page with opt-in visibility (monitors and maintenance notices default to private).
- Manual incident creation/resolution and one-time maintenance records with dashboard controls.
- Public incident RSS feed, opt-in SVG status badges, and protected Prometheus-format metrics.
- Basic JSON monitoring endpoints and isolated container deployment example.
- Optional authenticated integration with the existing GoreeCloud Notify publish API.
- GitHub Actions Python and JavaScript checks.

## Run locally

Requirements: **Python 3.12+**. The standard-library service requires no Python package install.

1. Create a strong administrator password (at least 12 characters). Keep it out of the repository.
2. Bind only to loopback for local development.
3. Start the app:

    export GC_ADMIN_PASSWORD='a unique long development password'
    python -m monitor.server

4. Open http://127.0.0.1:3001 and sign in.

The example above uses an environment variable for convenience. For persistent deployment, use GC_ADMIN_PASSWORD_FILE with a permission-restricted secret file. Never put actual credentials in git, shell history or public documentation.

To monitor private routable subnets, set GC_ALLOW_PRIVATE_TARGETS=1 explicitly. Loopback, link-local, multicast and reserved addresses remain disallowed. Public-target mode rejects private, loopback, link-local and reserved IPs. HTTP checks are subject to a documented DNS-rebinding hardening gap; do not expose this early version directly to hostile networks.

## Container deployment

The provided compose.yaml is a **deployment recipe, not a production deployment**. It requires a password file and TLS-terminating reverse proxy:

    mkdir -p secrets
    chmod 700 secrets
    # Create secrets/admin_password.txt securely, outside shell history
    chmod 600 secrets/admin_password.txt
    docker compose up -d --build

Compose binds only to 127.0.0.1:3001 and requires GC_COOKIE_SECURE=1; access the UI through a TLS reverse proxy, not directly over plain HTTP. To test with HTTP on localhost, use the Python command above. No production services, DNS entries or remote hosts are modified by this repository.

## Core API

| Method | Endpoint | Authentication | Purpose |
| --- | --- | --- | --- |
| GET | /healthz | Public | Minimal process health |
| POST | /api/login | Password | Start administrator session |
| POST | /api/logout | Session + CSRF | End session |
| GET | /api/me | Session | Session and CSRF status |
| GET, POST | /api/monitors | Session (POST + CSRF) | List and create monitors |
| PATCH, DELETE | /api/monitors/{id} | Session + CSRF | Pause, resume or delete |
| GET | /api/summary | Session | Monitor counts |
| GET | /api/history | Session | Recent heartbeats |
| GET, POST | /api/incidents | Session (POST + CSRF) | Record incidents |
| PATCH | /api/incidents/{id} | Session + CSRF | Resolve/reopen an incident |
| GET, POST | /api/maintenance | Session (POST + CSRF) | Record maintenance |
| DELETE | /api/maintenance/{id} | Session + CSRF | Remove maintenance |
| GET | /api/public | Public | Opt-in monitors, public incidents and upcoming maintenance |
| GET | /status.rss | Public | RSS feed for published incidents |
| GET | /badge/{id}.svg | Public if monitor opted in | SVG availability badge |
| GET | /metrics | Bearer token, opt-in | Prometheus-format metrics |
| POST | /push/{token} | Push token | Receive external heartbeat |

API is experimental and not yet a stable cross-product contract.

### Push example

Create a Push monitor in the UI. Copy the secret endpoint shown exactly once. Send:

    curl -X POST 'https://your-monitor-host/push/SECRET' \
      -H 'Content-Type: application/json' \
      -d '{"status":"up"}'

Do not publish the token; rotate by recreating the monitor if exposed.

## Engineering and docs

- [Full 30-domain product requirements](docs/PRODUCT_SPEC.md)
- [Capabilities and acceptance scope](docs/FEATURES.md)
- [Architecture and operations](docs/ARCHITECTURE.md)
- [Backup, recovery and operating procedures](docs/OPERATIONS.md)
- [Security and threat model](docs/SECURITY.md)
- [Delivery roadmap and gaps](docs/ROADMAP.md)
- [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui)
- [Governing account-specific project instructions](https://drive.google.com/drive/folders/1WQcWOzmqQAEf8IimePKzpGyH9jILCPeR) (private)

Run validation:

    python -m compileall -q monitor tests
    python -m unittest discover -s tests -v
    node --check web/app.js

## Project identity and provenance

Original implementation authored for GoreeCloud. Uses Python, SQLite and browser platform APIs; no third-party application fork is bundled. The full Uptime Kuma-inspired feature list supplied by the owner is a specification benchmark, **not a claim that GoreeCloud has implemented Uptime Kuma**. Third-party products and provider names remain the property of their respective owners.

**Status:** Development foundation · 2026-11-04 · No production readiness assertion.

### Optional metrics

Set GC_METRICS_TOKEN to a unique random secret of at least 24 characters. The protected /metrics endpoint then accepts Authorization: Bearer TOKEN. Do not expose the token to browsers, logs or public dashboards. Metrics contain monitor IDs, not private targets.


### Optional GoreeCloud Notify integration

GoreeCloud Monitor can submit outage and recovery events to the existing [GoreeCloud Notify](https://github.com/GoreeCloud/notify) service via its alpha publish API. This is optional best-effort integration. Neither notification delivery nor an existing deployed Notify instance is assumed.

Set these environment variables:

- GC_NOTIFY_URL: trusted HTTPS base URL or local-only http://127.0.0.1:8080
- GC_NOTIFY_TOKEN_FILE: restricted file with a Notify token authorized for topic publication
- GC_NOTIFY_TOPIC: valid topic identifier (default monitor)

Only confirmed DOWN and DOWN-to-UP transitions are published. Initial UP does not generate noise. Any active global maintenance window suppresses publication. Failed deliveries are not yet durably queued. Sample compose.yaml intentionally does not configure Notify credentials.


### Consistent backup (development / local)

With GC_DATA_DIR pointing to the active data directory, create an online SQLite snapshot:

    python -m monitor.backup /a/preexisting/protected/directory/monitor-2026-11-04.sqlite3

The destination must not already exist. The tool verifies SQLite integrity, writes a restrictive 0600 file, avoids overwriting existing backups, and returns a SHA-256 digest. Store backup media securely, verify restore in isolation, and see [operations](docs/OPERATIONS.md) for exact precautions. No automatic offsite backup or restore automation is provided.
