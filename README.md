# GoreeCloud Monitor

**Know what is running. Detect what is failing. Understand what matters.**

GoreeCloud Monitor is a privacy-first, self-hosted uptime, service-health and incident-awareness application built for the GoreeCloud ecosystem. The repository contains an original Python monitoring service and a responsive web console, built around the active GoreeCloud UI design language.

> **Maturity: 0.1.0 development foundation, not production-ready.** The owner's 30-section product specification is the target scope. The working subset and important gaps are documented in [Features](docs/FEATURES.md) and [Roadmap](docs/ROADMAP.md). Publishing code does not imply an instance is running or deployed.

## What works in the initial implementation

- HTTP/HTTPS GET checks with status-code and optional keyword validation.
- TCP port checks, DNS name resolution checks, and token-based push heartbeats.
- Background scheduler, per-monitor intervals, timeouts and consecutive-failure thresholds.
- SQLite WAL persistence for monitors and bounded heartbeat history.
- Private authenticated administrator console with session cookie and anti-CSRF token.
- Creation, pausing, resuming and removal of monitors; recent activity and summary cards.
- Public status page with opt-in visibility (monitors default to private).
- Manual incident and one-time maintenance records through authenticated JSON endpoints.
- Basic JSON monitoring endpoints and isolated container deployment example.
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

To monitor localhost or private subnets, set GC_ALLOW_PRIVATE_TARGETS=1 explicitly. Public-target mode rejects private, loopback, link-local and reserved IPs. HTTP checks are subject to a documented DNS-rebinding hardening gap; do not expose this early version directly to hostile networks.

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
| GET, POST | /api/maintenance | Session (POST + CSRF) | Record maintenance |
| GET | /api/public | Public | Only opt-in monitors |
| POST | /push/{token} | Push token | Receive external heartbeat |

API is experimental and not yet a stable cross-product contract.

### Push example

Create a Push monitor in the UI. Copy the secret endpoint shown exactly once. Send:

    curl -X POST 'https://your-monitor-host/push/SECRET' \
      -H 'Content-Type: application/json' \
      -d '{"status":"up"}'

Do not publish the token; rotate by recreating the monitor if exposed.

## Engineering and docs

- [Capabilities and acceptance scope](docs/FEATURES.md)
- [Architecture and operations](docs/ARCHITECTURE.md)
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
