# GoreeCloud Monitor — Implemented Features

**Record type:** Repository implemented-feature inventory  
**Repository:** `GoreeCloud/monitor`  
**Repository ID:** `1336209445`  
**Lifecycle:** Advanced pre-production acceptance candidate; production activation remains gated  
**Migration state:** **Authoritative on `main` after PR #52 merged as `41d88d2a12ad705f7c30160b378738031fbed37d` and default-branch readback verified this record.**  
**Repository authority baseline:** `main` at `41d88d2a12ad705f7c30160b378738031fbed37d` (PR #52, September 22, 2026). Latest source-bearing Monitor runtime remains `f59991c2ac577662ddc6f396027b4dc1d637689a` (PR #51).  

## Authority and interpretation

This file records capabilities implemented in current GoreeCloud Monitor source. It does not claim live target acceptance, production authority, Release Candidate promotion, or Stable status unless separate authoritative runtime/release evidence establishes that state.

The former roadmap and Drive records used the stale repository name `GoreeCloud/goreecloud-monitor`. Live GitHub repository identity controls current state: the authoritative repository is `GoreeCloud/monitor`, repository ID `1336209445`.

Capabilities that are implemented in source but still require live, representative, integration, security, recovery, accessibility, rollback, or production acceptance may appear here for the implemented portion and remain open in `PLANNED-FEATURES.md` for the acceptance obligation.

## Current verified source baseline

Repository `main` entering this stabilization tranche is `b7bf959e04ddd06f3a30db2f81bc7cb6ab4c53b4`. The current candidate advances the Monitor web presentation contract from Glaze UI 1.5.1 to the current Official Stable Glaze UI 1.6.0 release while preserving Monitor's pre-production lifecycle and fail-closed authority boundaries.

The V1.6 source mapping is bound to immutable tag `v1.6.0`, accepted release source `a7180679ea851389e0f3004515f9a25f420e716d`, source qualification anchor `c7509c79256b04b0aa67cb9dd0737d7588e0ae4a`, GitHub release `392095913`, and release artifact SHA-256 `687268b5eb76917eccae9d935ffa1bead333d5dee50b6098e996a3f44cee50af`. Shared Glaze Stable/consumer eligibility does not establish Monitor application acceptance or production eligibility.

## Monitoring and evaluation

- HTTP/HTTPS availability checks with expected-status, body-text, JSON, redirect, latency, TLS validation, and certificate-expiry handling.
- TCP reachability checks.
- DNS A, AAAA, and CNAME monitoring with resolver-specific source support.
- Native low-privilege IPv4/IPv6 Ping/ICMP using Linux unprivileged datagram ping sockets rather than raw-socket capability escalation.
- Push/heartbeat monitoring with minimized acknowledgements and token rotation.
- First-class Scheduled Job / Dead-Man monitors for cron jobs, backups, maintenance jobs, and periodic workloads.
- Simple interval + grace, strict five-field cron + IANA time-zone, and native systemd OnCalendar schedule modes.
- Authenticated scheduled-job start, success, failure/exit-status, and bounded log/event ingestion using one-way-stored rotatable bearer credentials.
- Per-monitor signal rate limiting with HTTP 429 / Retry-After behavior.
- Optional UUID event IDs for durable idempotent replay; exact retries converge while mismatched ID reuse is rejected.
- Run correlation, duration capture, maximum-runtime overrun detection, missed-schedule detection, and scheduled-job event history.
- Presentation phases Awaiting, Started, Completed, Failed, and Late derived without replacing the underlying Monitor state/incident model.
- Configurable check intervals, consecutive failure/recovery thresholds, pause/enable state, maintenance windows, incident creation/recovery, and operational search/filter views.

## Administration and UI

- Django-authenticated administrative application and operational UI.
- Overview, Monitors, Incidents, Maintenance, Notifications, Security, Settings, authentication, and monitor-detail surfaces.
- Staff-gated privileged mutation and protected diagnostic/configuration views.
- System, Light, and Dark appearance.
- Responsive presentation with source handling for Reduced Motion, Reduced Transparency, contrast, Forced Colors, large text, and form-factor behavior.
- Glaze UI 1.6.0 source-adoption candidate with exact Stable release provenance, local presentation-only runtime mapping, semantic loading/stale/degraded/error presentation tokens, and fail-closed downstream acceptance.
- Wardveil Security presentation and minimized staff-only security-posture surface.
- Canonical Monitor product-identity assets and local web/favicon/manifest plus future Linux/AppImage and Android launcher identity inputs; these inputs do not claim standalone native clients are implemented.

## Notification and integration foundations

- GoreeCloud Notify producer candidate with minimized transition payloads for DOWN, RECOVERED, DEGRADED, and TLS-expiry scenarios.
- Versioned idempotency-key contract.
- PostgreSQL-backed durable `NotificationOutbox` with transactional transition/outbox persistence before publication.
- Bounded in-request retry plus persistent retry/backoff across worker cycles and same-key replay convergence.
- Fail-closed target preflight while undelivered outbox rows remain.
- Bounded retention of already-delivered outbox metadata.
- Bearer-authenticated read-only Manager summary API.
- Read-only Manager scheduled-job list/detail endpoints exposing bounded lifecycle/schedule/incident and sanitized signal metadata while excluding credentials, verifiers, run IDs, event IDs, operator messages, and mutation authority.

## Data, migration, recovery, and rollback foundations

- Django migration-managed data model with PostgreSQL production topology and SQLite local/test support.
- Database backup tooling and isolated PostgreSQL restore validation in CI.
- Versioned portable monitor-definition and maintenance-window export/import foundations with secret exclusion and regenerated push credentials.
- Preserved Uptime Kuma audit/import/reconciliation/runtime-evidence tooling for historical and authorized recovery/comparison use.
- Paused migration import and fail-closed comparison/acceptance tooling.
- Migration-aware immediate-predecessor rollback compatibility workflows, including scheduled-job migrations and fail-safe OnCalendar downgrade behavior.
- Target preflight and hardened production Compose validation.
- Disposable and target-oriented recovery evidence workflows recorded in historical changelog evidence.

## Security and privacy controls

- Strong password validation, secure cookies, CSRF controls, production HSTS/security-header requirements, Content Security Policy, and Permissions Policy.
- Same-origin resource/opener/referrer boundaries and private operational response handling.
- SSRF-aware destination validation with explicit private-network allowlists and redirect-hop revalidation.
- Bounded response sizes and secret-minimized operational logging.
- No privileged production container requirement; application services use non-root/read-only/capability-dropped boundaries in the hardened topology.
- Fixable HIGH/CRITICAL container-image vulnerability gating and runtime-content minimization checks.
- Privacy Shield source-adapter candidate and Everkeep source acceptance-policy candidate, without claiming producer-system acceptance.
- Minimized Wardveil audit/security events that avoid copying credentials, request bodies, target URLs, raw diagnostics, failed-login usernames, or client IP addresses into the structured security event stream.

## Current lifecycle boundary

Current repository README identifies GoreeCloud Monitor as an **advanced pre-production acceptance candidate**. Uptime Kuma and ntfy predecessor dependencies were retired from `goreecloud-vps-01` on September 18, 2026, but predecessor retirement does not automatically establish Monitor production authority.

Still not established by source state alone:

- current target-host deployment/readback acceptance;
- reviewed monitor activation and representative live protocol checks;
- target PostgreSQL backup/restore acceptance;
- final private Gateway/DNS/NetBird publication acceptance;
- accepted GoreeCloud Notify runtime credential/delivery and durable-outbox restart/replay under real target failure;
- independent outage alerting;
- full Glaze UI 1.6.0 rendered/accessibility/semantic-state/recovery/performance acceptance;
- remaining platform-system acceptance;
- live rollback/recovery;
- explicit production approval or Stable qualification.

See `PLANNED-FEATURES.md` for those open obligations.

## Historical predecessor evidence safety

- Retired Uptime Kuma collection is explicitly historical comparison/recovery evidence only and requires an operator acknowledgement flag before the collector will run; it cannot silently present predecessor state as current GoreeCloud Monitor production acceptance.
