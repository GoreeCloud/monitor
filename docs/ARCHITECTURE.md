# GoreeCloud Monitor — architecture and security review

## Current system

- Python standard-library ThreadingHTTPServer is a small, self-hosted JSON API. It binds to loopback unless explicitly configured otherwise.
- A four-worker scheduler checks HTTP/HTTPS/TCP endpoints. It validates DNS answers to reduce SSRF risk, pins the resolved IP for each probe, applies TLS certificate verification and does not follow HTTP redirects.
- SQLite WAL stores monitors, historical checks (bounded at 5,000 per monitor) and incident transitions. A separate SQLite connection is created for each operation; SQL values use bound parameters.
- React/Vite web console reads public status and, after a supplied API bearer token, performs limited administrator actions. The token is held only in React component memory, not local storage.
- Flutter Linux/Android app requests only public published status. No account credentials are saved to disk. Foreground-only refresh is provided.
- The Prometheus exposition endpoint requires the same bearer token; no automatic metrics export.

## Risks and acceptance blockers

1. **SSRF:** Admin-selected monitors control network egress. Reject non-global IP by default, but an operator opting into internal probes should set external firewall limits, target allowlists, isolate workload and avoid sharing admin tokens. Inspect proxy/IDNA/redirect handling before expanding.
2. **Auth:** Single bearer secret, no per-user roles, independent sessions, server-side rate limiting, audit log or OIDC. Admin API should not be Internet exposed without separate access controls.
3. **Privacy:** All monitors are private initially; public status hides target URLs and detailed error messages. Publication of monitor name and incident timing still reveals information and needs consent. Custom retention and export controls are pending.
4. **Uptime reliability:** Single process and probe location; no out-of-band paging, redundancy, maintenance windows, escalation or confirmed SLA. Not suitable for production-critical independent monitoring.
5. **Durability:** SQLite WAL requires SQLite-consistent backups and independent restore drills. The container recipe is not a production installation or evidence of backups.
6. **Supply chain and platforms:** Validate dependency locks, native Flutter Linux and Android builds, version compatibility, Android TLS/permission behavior, accessibility, device tests, debug vs signed build provenance and release lifecycle.

## MIPS responsibility boundary

GoreeCloud UI is the design language (alpha Iris token sample). GoreeShield sets privacy and consent; Wardveil sets cybersecurity; GoreeCloud Mesh governs authorized integrations; GoreeCloud Identity governs authentication and authorization. No live cross-product integration is claimed.

## Roadmap

Prioritize edit monitor, suppress flapping/retries, clean service health API, configurable data retention, optional secure multi-channel notifications (GoreeCloud Notify, ntfy, SMTP), uptime history graphs, certificate expiry/DNS checks, status page management, Mesh event contracts, Identity/OIDC, redundant probes, health metrics and authenticated APIs for native administration. Each requires tests and privacy/security acceptance.
