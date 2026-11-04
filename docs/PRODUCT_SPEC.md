# GoreeCloud Monitor — Product Specification

| Document control | Value |
| --- | --- |
| Type | GoreeCloud product capability and target specification |
| Owner | GoreeCloud |
| Status | Active product requirements; **not an implementation or deployment certification** |
| Date | 2026-11-04 |
| Canonical path | GoreeCloud/monitor/docs/PRODUCT_SPEC.md |
| Implementation state | See [feature delivery matrix](FEATURES.md) and [roadmap](ROADMAP.md) |

## Product identity

**GoreeCloud Monitor** is a comprehensive, privacy-first, self-hosted infrastructure monitoring, uptime tracking, service health, performance analytics, incident management, alerting and public status communication platform.

The platform is designed for individuals, families, developers, businesses, organizations and infrastructure administrators. It provides one unified experience for websites, APIs, servers, networks, databases, containers, applications, scheduled jobs, cloud environments and connected services.

**Design philosophy:** Clear by default. Consistent by nature. Fluid by design.

**Design promise:** Calm information. Expressive personality. Purposeful depth.

**Product promise:** Know what is running. Detect what is failing. Understand what matters.

The system follows the active [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui) design language and prioritizes privacy, reliability, security, simplicity, performance, accessibility, interoperability, infrastructure ownership and operational independence.

**Interpretation:** Each domain below describes the requested product scope. Actual code is a limited development foundation. A supported protocol, integration, platform, authentication option or operating-system capability is not implemented merely because it appears in this specification.

## 1. Core Uptime and Availability Monitoring

Continuously track websites, APIs, services, applications and infrastructure using independent monitor schedules. Detect active, pending, up, down, paused and maintenance states; heartbeat success and failure; missed heartbeats; retry thresholds; service restoration; outage frequency; time to recovery; downtime duration; and historical availability. Administrators configure check intervals (including rapid checks), timeouts, retry frequency, consecutive-failure policies, individual and grouped monitors, manual service states, and private or public endpoints.

## 2. Website and HTTP/HTTPS Monitoring

Provide HTTP/HTTPS GET, POST, PUT, PATCH, DELETE, HEAD and supported additional request methods; status-code expectations; response-time measurements; redirects and redirect limits; custom headers, user agents, JSON and form bodies; Basic authentication, token headers and supported OAuth2 flows; keyword presence or absence checks; JSON path/query assertions; custom TLS trust anchors; standard certificate verification; and optional proxies. Include browser-rendered Chromium-based probes for JavaScript-dependent sites when a safe browser-worker integration is implemented. Maintain precise outage and recovery notifications and distinguish application errors from network failures.

## 3. Network and Connectivity Monitoring

Support ICMP ping, TCP ports, DNS resolution and record validation, WebSocket handshakes, SIP OPTIONS, NTP, SMTP, SFTP, MQTT, SNMPv1/v2c/v3, RADIUS, external geographic probes and Tailscale-specific reachability when supported on the host. Allow custom resolvers, host/port selection, DNS expected values, per-protocol credentials and security controls. Private network probing must remain opt-in with explicit host egress and SSRF controls.

## 4. Server, Container and Application Monitoring

Monitor Docker containers, process managers including PM2, supported Linux system services, application processes, containerized services and infrastructure management endpoints. Detect stopped containers, unavailable processes and degraded service checks. Restrict access to container management APIs through least-privilege intermediaries rather than exposing a privileged Docker socket. Report per-application operational health centrally.

## 5. Database and Messaging Infrastructure

Support PostgreSQL, MySQL/MariaDB, Microsoft SQL Server, MongoDB, Redis and Oracle Database health checks including connection establishment, authentication, configured test queries, secure transport, latency and recovery. Support Kafka producer, RabbitMQ, MQTT and gRPC checks and expected message or response validation where applicable. Never store database passwords or access tokens in public status output.

## 6. Game Server Monitoring

Support Steam-compatible and GameDig-supported multiplayer server queries with configurable host, port and protocol settings. Track connectivity, expected responses, downtime and recovery. Publish designated game server status via public status pages.

## 7. Push Monitoring and Scheduled Job Health

Generate high-entropy tokenized endpoints for externally initiated heartbeat reports from cron, backup tasks, scheduled automation, shell scripts and application jobs. Record success/failure, optional timing and diagnostic data, expected heartbeat frequency, missed-heartbeat alarms and recovery. Provide safe integrations for scripts, schedulers and workflow automation. Include secure token rotation and deletion.

## 8. Performance Monitoring and Analytics

Record timestamps, current and historical uptime, outages, ping latency, HTTP response times, average response latency, response trends, status transitions and time-to-recovery. Provide service and group summaries, customizable analysis periods, accessible charts, historical comparisons, configurable retention and export to supported observability systems. Distinguish uptime checks from full-stack logs, traces and host telemetry.

## 9. Intelligent Alerts and Notifications

Trigger on confirmed down, recovery, consecutive failures, missing push heartbeats and imminent certificate/domain expiry. Allow multiple destinations per monitor, reusable notification definitions, default destinations, test delivery, message templates, reminder policy, deduplication and maintenance suppression. Integrate via appropriately licensed and credentialed interfaces with email/SMTP, SendGrid, Brevo, Resend, messaging services such as Telegram, Discord, Slack, Teams, Google Chat, Matrix, Mattermost, Rocket.Chat, Nextcloud Talk, LINE and Signal; push services such as ntfy, Gotify, Pushover, Bark and Pushbullet; SMS providers such as Twilio, Telnyx and Plivo; incident systems such as PagerDuty, Opsgenie, Grafana OnCall, SIGNL4 and Squadcast; Webhooks, Apprise, Home Assistant and GoreeCloud Notify. Track durable delivery and failures before claiming reliable alert delivery.

## 10. Incident Detection and Management

Maintain service-specific and manually created incidents with title, description, impacted monitors, timestamps, investigation status, updates, public announcements and resolution. Preserve downtime and recovery histories, incident timelines, pinned announcements and optional escalation integrations. Display relevant incidents on status pages and RSS, differentiating unplanned disruptions from scheduled maintenance.

## 11. Public and Private Status Communication

Create multiple independent branded status pages with title, description, slug, optional custom domain, selected published monitors, service groups, collapsible sections, current and historical uptime, incident announcements, past incidents, maintenance banners and RSS feed. Refresh published status automatically. Protect internal URLs, credentials and unpublished monitors. Support restricted pages through authenticated external gateways when appropriate. Public pages never inherit full administrator access.

## 12. Maintenance Scheduling and Management

Create named and described one-time, manual, recurring, interval, weekly, monthly and cron-based maintenance windows with time zones and explicit start/end. Select affected monitors and status pages; display maintenance banners, change their status and suppress only relevant notifications. Provide edit, clone, pause, resume, delete and historical maintenance views.

## 13. SSL/TLS Certificates and Domain Monitoring

Inspect TLS certificates, certificate validity/chain/authority, time to expiration and invalid certificates. Provide configurable warning days, badge data and notifications. Track supported domain expiration information and renewal reminders with multiple thresholds, without claiming comprehensive TLS auditing or registrar-independent accuracy where not established.

## 14. Monitoring Dashboard and Interface

Deliver a polished responsive GoreeCloud UI dashboard with live service summaries, status indicators, monitor groups, nested hierarchy, search, tags, individual detail views, response-time and heartbeat charts, recent events, uptime/downtime summaries and quick management controls. Support create/edit/clone/pause/resume/delete/bulk operations, configurable monitoring, notifications, status page assignments and dark/light/system appearance. Favor clear error, loading and empty states.

## 15. Status Badges and Embedded Widgets

Generate embeddable SVG badges for current status, uptime percentage, ping, average/current response, certificate expiration and supported time windows. Allow style, label, color, prefix and suffix customization. Provide secure public-only embedding for website footers, GitHub README files and project documentation.

## 16. APIs, Webhooks and Automation

Provide versioned, documented, authenticated administrative APIs and stable public status APIs; push endpoints, badges, RSS, protected metrics and outbound webhooks. Implement scoped API keys, expiration and revocation, stable structured JSON, automation event payloads and integration guidance. The application's internal UI protocol is not a promised stable public management API.

## 17. Prometheus and External Observability

Expose access-controlled Prometheus-compatible availability and latency gauges/counters with safe identifying labels. Offer Grafana dashboards and connectors to long-term external metrics systems. Avoid sensitive hostnames and unbounded metric cardinality. Detailed traces, full host telemetry and centralized logs may be supplied by specialized GoreeCloud or compatible systems.

## 18. Authentication and Account Security

Provide password authentication, secure sessions, two-factor authentication, account recovery and password rotation, protected administration, API key controls, authenticated integrations, token rotation, reverse-proxy awareness, encrypted database connections, least-privilege infrastructure access and secret-safe configuration. Apply CSRF protection, input validation, output encoding, audit trails, transport security, abuse controls and strong default isolation.

## 19. Privacy and Self-Hosting

Maintain local ownership of operational data, monitoring history, configuration and backups. Make external notification/probe providers optional and transparent. Keep private services unpublished unless explicitly selected. Offer controlled retention, secure recovery and private network deployment without a mandatory third-party monitoring subscription.

## 20. Deployment and Platform Compatibility

Support Docker and Docker Compose, native Node/Python-compatible or otherwise appropriate native service implementations, Linux servers, compatible Windows installations, ARM/Raspberry Pi, virtual machines, bare metal and private cloud. Allow adjustable binding, ports, persistent directories, environment configuration, reverse proxies, system service lifecycle and rootless container options. Validate each platform before labeling it supported for installation.

## 21. Data Storage and Database Management

Support SQLite and optional MariaDB as appropriate, reliable schema migrations, persistent monitor and heartbeat records, history, incidents, maintenance, notification and status-page configurations, retention policy controls, database optimization, secure connections and recoverable storage. Avoid unsupported network filesystems and loss-prone persistence patterns.

## 22. Backup, Recovery and Data Portability

Provide supported JSON configuration import/export with conflict handling, full database and volume backup, tested restore, consistency verification, secure handling of embedded tokens, encrypted backup media, version-aware migrations and rollback documentation. Configuration-only exports do not constitute a complete history-preserving backup.

## 23. Organization, Classification and Administration

Provide configurable monitor names, nested groups, tags, tag values/colors, search, filtering, cloning, bulk management, per-monitor notification and status-page assignments, maintenance selection, interval controls, retention settings and centralized administration.

## 24. Reliability and Operational Resilience

Support continuously executing health checks, independent timing, configurable retries, timeouts, persistent history, bounded concurrency, recovery signals and maintenance-aware notification behavior. Plan durable alert queues, health of the monitor engine itself, safe config changes, migration testing, backups, rollback and optional future high-availability collectors.

## 25. GoreeCloud Ecosystem Integration

Provide the owner-controlled service-health layer for GoreeCloud websites, APIs, databases, DNS, VPN, Gateway, Identity, Vault, Backup, Sync, Search, Location, Workspace, Docker infrastructure, servers, automation and internal storage endpoints. Integrate with GoreeCloud Notify through a documented, limited contract. Treat each integration as planned until the target service, endpoint, authorization and live checks are individually verified. Never invent operational health values.

## 26. User Experience and Accessibility

Adopt the active GoreeCloud UI Canvas/Surface/Lens model, canonical GC UI design tokens and appropriate components. Provide strong hierarchy, premium yet calm visual depth, consistent icons, semantic state colors with redundant text labels, accessible focus, touch and keyboard controls, screen reader cues, mobile layouts, contrast awareness, reduced-motion behavior, transparent errors, loading/empty states, date/time clarity and efficient advanced controls. Visual screenshot review and real browser testing must precede visual acceptance claims.

## 27. Primary Use Cases

Serve self-hosted home and family infrastructure; uptime and API health; cloud/server operations; developer and DevOps jobs; business service availability; customer-visible incident communication; cron and backup job heartbeats; multi-network private/remote infrastructure; and game server availability, within supported deployment and access-control boundaries.

## 28. Product Architecture and Operating Principles

Design around a monitoring engine; monitor configuration and grouping; heartbeat processing; metrics/history store; alerting and notification integration; incident workflows; maintenance scheduling; status-page publishing; APIs, badges and metrics; authentication/security; persistence, recovery and migrations; and a unified GoreeCloud UI. Separate untrusted outbound probes from management controls and use appropriately licensed dependencies only where necessary.

## 29. Core Product Objectives

Provide dependable service-health visibility, fast outage detection, useful alerts, intuitive operations, meaningful historical uptime/performance information, reduced unnecessary notifications, clear incident/maintenance communication, unified GoreeCloud integration, data ownership, maintainable and efficient self-hosting, and open technical interoperability.

## 30. Product Vision

**GoreeCloud Monitor brings infrastructure monitoring, service availability, operational awareness and incident communication into one secure, self-hosted experience.**

It makes websites, applications, APIs, networks, databases, containers, servers and automated workflows observable through a consistent interface. Each capability must be independently implemented, tested and documented before it is advertised as production-ready.

**GoreeCloud Monitor — Know what is running. Detect what is failing. Understand what matters.**

---

## Implementation status and verification

The full list above is the owner's active specification. The repository's implemented subset, test status and blockers belong in [Features](FEATURES.md), [Security](SECURITY.md), [Architecture](ARCHITECTURE.md) and [Roadmap](ROADMAP.md). Product requirements, CI success, native host acceptance and live production deployment are distinct claims and must never be conflated.

Uptime Kuma and listed third-party services are reference products or optional integrations; their capabilities and trademarks are not claimed as GoreeCloud-authored code.
