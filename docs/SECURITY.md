# GoreeCloud Monitor — Security and Threat Model

| Metadata | Value |
| --- | --- |
| Owner | GoreeCloud |
| Classification | Security engineering guidance; development-stage |
| Updated | 2026-11-04 |

## Threats

Monitoring requests can access infrastructure endpoints and are therefore SSRF-sensitive. Push tokens authorize writes to individual monitor histories. Administrative credentials grant configuration access. Public status pages risk exposing internal hostnames. Container access to Docker is host-sensitive. HTTP sessions are vulnerable to theft without TLS.

## Initial controls

- Explicit operator-provided minimum-length administrator password; no default password.
- HttpOnly, SameSite=Strict session cookies; use Secure with TLS.
- Per-session anti-CSRF token on mutating administrative routes.
- Login attempt throttling per remote IP.
- No CORS wildcard and a restrictive Content Security Policy.
- No dynamic HTML insertion of external monitor names or targets.
- Private monitors excluded from public status listings by default.
- Token-based push access stored as a hash, returned once.
- Untrusted targets validated against an IP/network policy; private network probing requires explicit opt-in.
- No Docker daemon socket mount or other host-privileged operations in compose.
- Nonroot, dropped capabilities, read-only filesystem and persistence volume in sample container configuration.
- No committed passwords, tokens, credentials, production inventory or live endpoints.

## Known security gaps — release blockers for Internet exposure

1. **HTTP network-policy review:** connections pin DNS results to the validated address and retain TLS hostname verification, but this prototype still lacks complete testing of DNS answer changes, proxy behavior, IPv6, redirect handling, and network egress enforcement. Keep it private until validated.
2. **No TOTP or advanced account security:** one operator password only.
3. **No production TLS terminator shipped:** HTTPS proxy configuration, headers and security review are deployment responsibilities.
4. **No comprehensive rate limits for push tokens:** tokens are high entropy but should have per-token throttling, limits and abuse monitoring.
5. **Optional Notify credentials:** keep GC_NOTIFY_TOKEN_FILE in protected storage, use topic-scoped publish permissions and HTTPS in non-loopback configurations. Delivery is best-effort; operators must not configure untrusted endpoints.
6. **No secret-at-rest encryption:** protect the OS, secret files, SQLite and backup media.
7. **No audit trail or security-event alerting:** administrative changes lack dedicated tamper-evident event records.
8. **No external security audit or live penetration test.**
9. **No formal backup restoration validation or upgrade regression tests.**

## Operational security requirements

Keep this service on a private management network until the identified gaps are fixed and validated. Never place actual secrets in the public repo or configuration exports. Use unique long passwords and TLS. Prefer allowlisted private network targets in future releases. Review network egress policies, reverse proxy logs, data retention, backup security and access controls.

To report a vulnerability, use private owner channels rather than disclosing exploitable details in public issues.
