# GoreeCloud Monitor — Features and Capabilities

| Control | Value |
| --- | --- |
| Document type | Product specification and delivery matrix |
| Owner | GoreeCloud |
| Canonical code | GoreeCloud/monitor |
| Date | 2026-11-04 |
| Status | Target specification with explicitly identified implemented subset |
| Product vision | Know what is running. Detect what is failing. Understand what matters. |

GoreeCloud Monitor is a self-hosted, privacy-first service intelligence platform for individuals, families, developers, businesses and organizations. It is intended to unify health checks, uptime history, notifications, incident communication, maintenance and service dashboards using GoreeCloud UI.

**Legend:** Implemented means code is present in this repository, not necessarily verified on a live deployment. Partial means a subset is implemented. Planned means not delivered.

| # | Capability domain | Current scope | Next implementation target |
| --- | --- | --- | --- |
| 1 | Core uptime and availability | **Partial:** scheduler, failure thresholds, recovery, states, history | Per-monitor retry policy, historical uptime calculations |
| 2 | HTTP/HTTPS monitoring | **Partial:** configurable GET, expected status, keyword, TLS verification | All methods, JSON queries, auth, browser probes, proxy, redirect policy |
| 3 | Network/connectivity | **Partial:** TCP, DNS resolution and TLS certificate probe | ICMP, DNS record types, SNMP, NTP, SMTP, WebSocket, SIP, RADIUS, Tailscale, Globalping |
| 4 | Server/container/process | **Planned** | Docker API with restricted socket proxy, systemd, PM2 |
| 5 | Databases and message brokers | **Planned** | PostgreSQL, MySQL, SQL Server, Oracle, MongoDB, Redis, Kafka, RabbitMQ, MQTT, gRPC |
| 6 | Game servers | **Planned** | Steam protocol, GameDig integrations |
| 7 | Push and scheduled jobs | **Partial:** token-based POST, token rotation, per-token push rate limit, missed heartbeat check | Timing details, failure messages, token rotation |
| 8 | Performance and analytics | **Partial:** recent heartbeat, response time and explicit 24-hour check pass-rate analytics | Time-weighted uptime, trends, charts, reports and custom retention |
| 9 | Alerts and notifications | **Partial:** GoreeCloud Notify v1 outage/recovery publish connector | Durable retries, SMTP, webhook and provider integrations |
| 10 | Incident management | **Partial:** create/list/resolve and opt-in RSS | Incident resolve/edit, association, public publishing, automated incidents |
| 11 | Public/private status | **Partial:** opt-in status page, incidents, maintenance, RSS | Multiple branded pages, groups, RSS, incident display, custom domains |
| 12 | Maintenance | **Partial:** one-time global or monitor-scoped maintenance, create/delete UI, selective suppression and private-by-default public announcements | Per-monitor scopes, recurring schedules, alert suppression |
| 13 | Certificates/domains | **Partial:** verified TLS hostname/chain check, configurable certificate-expiry warning monitor | Certificate details/badges, domain expiry and renewals |
| 14 | Dashboard and UI | **Partial:** pinned GC UI Foundations tokens, responsive console and light/dark appearance controls | Component migration, charts, complete management forms and visual QA |
| 15 | Status badges | **Partial:** opt-in SVG status badge | Uptime/ping/certificate badges |
| 16 | APIs/webhooks | **Partial:** authenticated JSON and push | Stable versioned API, webhooks, key management |
| 17 | Prometheus/external observability | **Partial:** protected /metrics endpoint | Grafana examples, long-term telemetry |
| 18 | Authentication/security | **Partial:** password session, rate limit, CSRF | Two-factor auth, password rotation, audit events |
| 19 | Privacy/self-hosting | **Partial:** local storage, opt-in publishing | Detailed privacy policy, encrypted provider secrets |
| 20 | Deployment/platform | **Partial:** Python service and container recipe | Native service installers, platform CI and signed releases |
| 21 | Data storage | **Partial:** SQLite WAL and bounded history | MariaDB, migrations, retention policy controls |
| 22 | Backup/recovery | **Partial:** consistent SQLite snapshot utility with integrity check and no-overwrite semantics | Full restore tests, export/import, encryption and automation |
| 23 | Organization/admin | **Partial:** list, create, edit, pause, resume, delete and push credential rotation | Groups, nested hierarchy, tags, bulk editing |
| 24 | Reliability/resilience | **Partial:** bounded worker pool, retry threshold | HA design, queue-backed alert delivery, backups, telemetry |
| 25 | GoreeCloud ecosystem | **Planned** | Explicit verified service endpoints and consent-based integration |
| 26 | UX/accessibility | **Partial:** responsive layout, canonical semantic token foundations, theme preference, semantic controls and reduced motion | Full GC UI component use and manual browser visual review |
| 27 | Use cases | **Partial:** HTTP, TCP, DNS and scheduled jobs | Full protocol and infrastructure portfolio |
| 28 | Product architecture | **Partial:** server, scheduler, DB, UI, status | Modular probe drivers, notifications, plugins, controlled APIs |
| 29 | Product objectives | **Active product direction** | Measure uptime, response times, alert quality and operational cost |
| 30 | Product vision | **Active product direction** | Unified operational awareness across the GoreeCloud ecosystem |

## Scope commitment

All items in the owner's 30-section GoreeCloud Monitor product vision form the target feature inventory. Individual third-party notification provider names, database drivers, game protocols, mobile platforms and enterprise integrations **do not become implemented capabilities by being named**. Each requires verified engineering, licensing review, credentials, tests and supported deployment.

## Acceptance criteria for the initial slice

- Authenticated administrator can create and manage HTTP, TCP, DNS and Push monitors.
- Private monitors never appear in the public listing without explicit opt-in.
- Monitor outcomes persist across application restart.
- Invalid input and private-address policy violations are rejected.
- Session authentication and CSRF checks protect administrator mutations.
- UI loads on mobile and desktop and does not interpolate server-provided text as HTML.
- Python tests and JavaScript syntax checks pass in CI.
- Default deployment binds to loopback and does not publish infrastructure secrets.

These are criteria, not claims of independently verified live acceptance.


## 2026-11-04 hardening increment

- Maintenance notices now require explicit publication; new and migrated legacy records default to private. The public API returns only opt-in announcements.
- Push heartbeat submissions have a per-token rolling-minute request limit. No per-IP global denial-of-service protection or distributed rate limiting is claimed.
- RSS incident dates use the standard RFC 2822 format.
- Added a local online SQLite backup helper with integrity validation, restrictive file permissions, non-overwrite semantics and automated snapshot tests.
- Added regression tests for maintenance-publication isolation, legacy database migration, push throttling and snapshot integrity.

These changes are a development-stage security improvement, not a full security review or production release.

## Monitor management update (2026-11-04)

Administrators can modify validated monitor names, endpoints, intervals, timeouts, visibility, and HTTP expectations without changing monitor type or leaking hashed push secrets. A separate CSRF-protected push token rotation endpoint atomically invalidates the previous token. Changing check definitions or rotating a token resets the last service state to pending. The interface provides edit and rotate controls; integration tests cover invalid fields, authorization and revoked tokens.

## TLS certificate monitor increment (2026-11-04)

Added a dedicated `tls` monitor accepting `host:port`. It verifies the TLS peer certificate through the platform trust store using SNI, enforces the configured pre-expiration threshold, records a sanitized failure state, and uses the existing outage/recovery notification integration where configured. The monitor schema includes `warning_days` with a private, backwards-compatible migration. Unit/integration tests exercise address pinning, hostname propagation, impending expiry, invalid configuration and legacy database migration. Expiration badges, domain registrar checks and all-platform TLS acceptance are still pending.

## GoreeCloud UI integration increment (2026-11-04)

The Monitor frontend consumes a local, pinned copy of the Apache-2.0 GoreeCloud UI Foundations 1.0.1 semantic token stylesheet from the canonical GoreeCloud/gc-ui tagged release. The global Canvas/Surface/Lens, typography, motion and accent roles now use canonical token values instead of a separate token authority. Both the administrative console and public status page provide saved light/dark appearance selection. HTML and CSS are served locally, avoiding an external runtime CDN requirement. This is token-level integration, not verified adoption of all GC UI components or full visual acceptance.

## Scoped maintenance increment (2026-11-04)

One-time windows can target a single monitor or all monitors. Monitoring status and optional GoreeCloud Notify suppression now respect selected scope. Public status continues to require explicit publication. Deleting a monitor cascades to maintenance windows scoped to that monitor instead of silently converting them to global suppression. The SQLite schema adds a nullable monitor reference with an additive migration; prior windows retain global scope. Recurring rules and multi-monitor groups remain planned.

## Check/result concurrency protection — November 4, 2026

Each monitor stores a configuration revision. Editing monitor settings, changing active state or rotating a push credential advances that revision. Scheduled checks record the revision when dispatched, and late results from an older revision are discarded. Push submissions are checked against the current stored secret digest when their heartbeat is committed, preventing a request authorized under an earlier token from writing after rotation. Heartbeat read/modify/write operations use a short SQLite immediate transaction to serialize with configuration mutations, avoiding stale-state overwrite and lost failure-counter updates. Additive migration initializes revision 1 for preexisting monitors. Regression tests cover in-flight scheduled work, rotation during a push request, legacy schema migration and pause/resume invalidation.
