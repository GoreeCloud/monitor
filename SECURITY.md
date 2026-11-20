# GoreeCloud Monitor — security policy

This is an **early development preview**. Do not deploy as your only monitor, pager, or a publicly exposed administrative endpoint. No production SLA or security certification is claimed.

## Reporting

For suspected vulnerabilities, do not publish exploit details, secrets or user data in a public issue. Use a private GitHub vulnerability report/security advisory for the GoreeCloud/monitor repository when available. If that is unavailable, contact the repository owner privately through an established trusted channel.

## Default protections

- Local API binding and private monitors by default.
- Strong bearer token required for all administration. Configure it outside the repository.
- Public status has no private target URLs or detailed probe errors.
- Disallow non-global probe IP addresses by default. Allow internal probes only deliberately and use egress ACLs or network isolation.
- Backend has no telemetry, no unauthorized notification delivery and no dependency on external hosted APIs.
- A non-root, read-only container recipe is provided with all Linux capabilities dropped. The optional web proxy binds to loopback, not a public address.

## Important limitations

There is no OIDC, per-user permissions, request rate limiting, multi-zone monitoring, guaranteed incident delivery, independently tested disaster recovery, full penetration audit or signed mobile release. Probe URLs and publication are controlled by administrators and may reveal infrastructure. TLS termination for the browser deployment requires a separate properly configured Gateway and certificate policy. Regular dependency reviews, input validation, audit logging and staged upgrades are required before production acceptance.

See docs/ARCHITECTURE.md for the current threat model and accepted control boundaries.
