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
| 2 | HTTP/HTTPS monitoring | **Partial:** GET, expected status, keyword, TLS verification | All methods, JSON queries, auth, browser probes, proxy, redirect policy |
| 3 | Network/connectivity | **Partial:** TCP connect and DNS resolution | ICMP, DNS record types, SNMP, NTP, SMTP, WebSocket, SIP, RADIUS, Tailscale, Globalping |
| 4 | Server/container/process | **Planned** | Docker API with restricted socket proxy, systemd, PM2 |
| 5 | Databases and message brokers | **Planned** | PostgreSQL, MySQL, SQL Server, Oracle, MongoDB, Redis, Kafka, RabbitMQ, MQTT, gRPC |
| 6 | Game servers | **Planned** | Steam protocol, GameDig integrations |
| 7 | Push and scheduled jobs | **Partial:** token-based POST, missed heartbeat check | Timing details, failure messages, token rotation |
| 8 | Performance and analytics | **Partial:** recent heartbeat and response time | Uptime windows, trends, charts, reports and custom retention |
| 9 | Alerts and notifications | **Planned** | Secure outbound webhook and SMTP first, then integrations |
| 10 | Incident management | **Partial:** create/list/resolve and opt-in RSS | Incident resolve/edit, association, public publishing, automated incidents |
| 11 | Public/private status | **Partial:** opt-in status page, incidents, maintenance, RSS | Multiple branded pages, groups, RSS, incident display, custom domains |
| 12 | Maintenance | **Partial:** one-time global maintenance records, create/delete UI | Per-monitor scopes, recurring schedules, alert suppression |
| 13 | Certificates/domains | **Partial:** HTTPS TLS validation | Expiration warnings, certificate chain, domain renewals |
| 14 | Dashboard and UI | **Partial:** GC UI-inspired responsive console | Design-token package integration, charts, full management forms, visual QA |
| 15 | Status badges | **Partial:** opt-in SVG status badge | Uptime/ping/certificate badges |
| 16 | APIs/webhooks | **Partial:** authenticated JSON and push | Stable versioned API, webhooks, key management |
| 17 | Prometheus/external observability | **Partial:** protected /metrics endpoint | Grafana examples, long-term telemetry |
| 18 | Authentication/security | **Partial:** password session, rate limit, CSRF | Two-factor auth, password rotation, audit events |
| 19 | Privacy/self-hosting | **Partial:** local storage, opt-in publishing | Detailed privacy policy, encrypted provider secrets |
| 20 | Deployment/platform | **Partial:** Python service and container recipe | Native service installers, platform CI and signed releases |
| 21 | Data storage | **Partial:** SQLite WAL and bounded history | MariaDB, migrations, retention policy controls |
| 22 | Backup/recovery | **Planned** | Consistent snapshot utility, restore tests and secure JSON portability |
| 23 | Organization/admin | **Partial:** list, create, pause, resume, delete | Groups, nested hierarchy, tags, bulk editing |
| 24 | Reliability/resilience | **Partial:** bounded worker pool, retry threshold | HA design, queue-backed alert delivery, backups, telemetry |
| 25 | GoreeCloud ecosystem | **Planned** | Explicit verified service endpoints and consent-based integration |
| 26 | UX/accessibility | **Partial:** responsive layout, semantic controls, reduced motion | Full GC UI component use, WCAG audit and manual screenshot review |
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
