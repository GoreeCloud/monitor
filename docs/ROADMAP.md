# GoreeCloud Monitor — Delivery Roadmap

| Metadata | Value |
| --- | --- |
| Owner | GoreeCloud |
| Updated | 2026-11-04 |
| Release classification | Development foundation, not deployed |

## Immediate priority: secure and stabilize

1. Add integration tests proving HTTP connections remain pinned to validated DNS results with correct TLS SNI and certificate validation.
2. Fix and validate any CI errors, add automated HTTP integration checks, and verify a container image build.
3. Add comprehensive authenticated API error cases, push request throttling, mutation audit logs and administrative password rotation.
4. Integrate published GC UI design tokens and components; perform screenshot-led responsive and keyboard audits.
5. Implement secure webhook + SMTP notifications with durable retry queues, event deduplication and maintenance-aware suppression.

## Next: monitoring depth

- JSON queries, configurable HTTP methods and authentication.
- ICMP, DNS record types, WebSocket, TLS certificate expiry and TCP protocols.
- Docker monitoring through a tightly restricted intermediary, not a privileged socket mounted into the app.
- Database drivers, message brokers and supported process monitoring.
- Per-monitor downtime thresholds, uptime windows and richer visualizations.

## Then: communication and administration

- Recurring, scoped maintenance schedules and incident lifecycles.
- Multiple branded public status pages with incident timeline and RSS.
- Harden the initial Prometheus-format metrics, SVG status badge and RSS endpoints; add a versioned API and integration guides.
- Monitor tags, grouping, advanced filtering and bulk editing.
- Tested backup/restore and migration tooling.

## Long-term

- Optional MariaDB, distributed collectors, event queue and high-availability patterns.
- Supported Linux native service packaging and platform-specific release acceptance.
- Extended notification providers, incident-management integrations and native ecosystem integrations.
- Advanced reporting, retention, audit events and security assessments.

## Exit criteria

Every capability must have a documented definition, relevant tests, safety review, secure defaults, accurate implementation-state documentation and appropriate platform runtime verification before being called stable.
