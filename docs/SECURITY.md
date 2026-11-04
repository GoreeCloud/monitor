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
- Private monitors and maintenance records excluded from public status listings by default, including privacy-preserving migration of legacy maintenance records.
- Token-based push access stored as a hash, returned once; per-token in-memory rate limit (120 requests/minute).
- Untrusted targets validated against an IP/network policy; private network probing requires explicit opt-in.
- No Docker daemon socket mount or other host-privileged operations in compose.
- Nonroot, dropped capabilities, read-only filesystem and persistence volume in sample container configuration.
- No committed passwords, tokens, credentials, production inventory or live endpoints.

## IPv4-mapped IPv6 policy consistency

IPv4-mapped IPv6 destinations are evaluated according to their embedded IPv4
addresses before the global/private/link-local/loopback checks. This makes
denial of mapped loopback and metadata destinations, and private-network
opt-in, consistent across Python 3.12 and 3.13. The policy still validates
all DNS results and connects probes to vetted addresses; this is not a
substitute for external egress enforcement, network-layer isolation or a
complete SSRF assessment.

## In-memory session lifecycle

Each successful operator login creates a new random session ID and anti-CSRF
token. The single-process session table prunes expired records on new logins,
removes expired records when their cookies are presented, and retains at most
128 concurrent sessions by evicting those that expire first. This prevents
unbounded session-table growth from repeated logins without changing the
existing eight-hour absolute session expiration or cookie protections.

These controls are **not** distributed rate limiting, durable session
revocation across multiple instances, multi-user authentication, or
production session-management certification. Restarting the service
invalidates in-memory sessions; protect the operator password separately.

## Administrator password file permissions

On POSIX hosts, `GC_ADMIN_PASSWORD_FILE` must reference a regular file
readable only by its owner (for example, mode `0600` or `0400`).
The loader checks the opened file descriptor before reading the secret and
refuses group/world readable files, directories or special files. This
reduces accidental credential disclosure in shared environments. It
does not encrypt the file, prove correct ownership, restrict who can read
the operator's environment, or replace OS isolation. If the deployment
mounts read-only secrets, ensure they are readable by the nonroot Monitor
UID without granting group/other permissions.

## Bounded login source accounting

The development operator login endpoint tracks attempts by the **actual
socket peer IP** for an eight-attempt, 300-second sliding window; it does not
trust caller-controlled `X-Forwarded-For` for identity. A single-process
table now retains at most 4,096 distinct source addresses. Under source
pressure, expired buckets are deleted; if all buckets remain active,
new sources receive HTTP 429 without evicting any active attempt history.
Known sources remain subject to their original window and can retry after
expiry. Monotonic clock timestamps prevent wall-clock adjustments from
reversing the in-memory limit.

This fail-closed defense may temporarily deny legitimate *new* source IPs
during a distributed attack. It is **not** distributed rate limiting,
reverse-proxy client identity, an account lockout policy, DDoS prevention,
or a production authentication certification. A TLS proxy typically makes
all proxied requests share the same peer address; edge-level independent
limits and a documented trust boundary remain necessary.

## Known security gaps — release blockers for Internet exposure

1. **HTTP network-policy review:** connections pin DNS results to the validated address and retain TLS hostname verification, but this prototype still lacks complete testing of DNS answer changes, proxy behavior, IPv6, redirect handling, and network egress enforcement. Keep it private until validated.
2. **No TOTP or advanced account security:** one operator password only.
3. **No production TLS terminator shipped:** HTTPS proxy configuration, headers and security review are deployment responsibilities.
4. **Rate limits incomplete:** push tokens now have single-process per-token throttling, but distributed limits, IP controls, and abuse monitoring remain unimplemented.
5. **Optional Notify credentials:** keep GC_NOTIFY_TOKEN_FILE in protected storage, use topic-scoped publish permissions and HTTPS in non-loopback configurations. Delivery is best-effort; operators must not configure untrusted endpoints.
6. **No secret-at-rest encryption:** protect the OS, secret files, SQLite and backup media.
7. **No audit trail or security-event alerting:** administrative changes lack dedicated tamper-evident event records.
8. **No external security audit or live penetration test.**
9. **No formal backup restoration validation or upgrade regression tests.**

## HTTPS reverse-proxy boundary — development acceptance

An isolated TLS proxy fixture now checks trusted-certificate HTTPS access,
`Secure; HttpOnly; SameSite=Strict` cookies, CSRF denial, logout, private
status isolation, and denial of authentication based on forwarded identity
headers. Its HSTS header is emitted by the test gateway to model an edge
control; **the application does not implement or verify a real proxy**.
The test listeners bind to loopback, and all credentials and certificates
are disposable fixtures.

This is *not* evidence of a production TLS installation. A publicly
reachable plaintext origin, untrusted `Host`/`Forwarded` headers, incorrect
TLS termination, missing edge HTTPS redirects/HSTS, DNS rebinding, and
network-egress gaps remain deployment risks requiring independent
configuration checks. No live domain or VPS was tested.

## Operational security requirements

Keep this service on a private management network until the identified gaps are fixed and validated. Never place actual secrets in the public repo or configuration exports. Use unique long passwords and TLS. Prefer allowlisted private network targets in future releases. Review network egress policies, reverse proxy logs, data retention, backup security and access controls.

To report a vulnerability, use private owner channels rather than disclosing exploitable details in public issues.


## Backup confidentiality

SQLite backups include monitor configurations, targets, operational timestamps, and potentially sensitive incident content. The backup utility writes owner-only files with no-overwrite behavior, but it does not encrypt output or transport it. Apply filesystem encryption and access controls externally. Treat full database backups as private infrastructure records.

### Maintenance-state publication isolation

Private active maintenance windows suppress configured operational notifications and appear in authenticated administrative status, but they must not silently mark public service rows as under maintenance. Public status labels reflect only explicitly published active maintenance windows. A regression test exercises both private and public views.

## Push token lifecycle and validated mutations

The admin API supports one-time push token rotation behind session authentication and per-session CSRF validation. The database stores only the SHA-256 digest of each new random token; previous tokens stop matching as soon as rotation succeeds. Administrator monitor edits use a field allowlist, full parameter validation, and atomic SQL updates. Rotating a token or changing a check target/expectation resets stale health state to pending. Operators must update their heartbeat sender manually after rotation; no secret is sent by email or written into application history.

## TLS monitor security notes

TLS certificate probes use the same pinned-network-address policy as HTTP probes. A Python standard-library verification context checks system-trust CA chains and the requested hostname via SNI. Do not disable certificate verification to force a passing result. Expiration windows represent configured warning policy, not evidence of automated renewal. Private network targets must be explicitly enabled, and existing protections against loopback/link-local/reserved endpoints remain in effect. Certificate error output is intentionally summarized rather than retaining raw private connection details.

## Frontend appearance and asset integrity

The canonical first-party GC UI Foundations token CSS is served locally rather than fetched from a third-party CDN, reducing runtime network and supply-chain dependencies. Its release tag and source SHA are recorded in the asset header; the Apache license is bundled. The light/dark preference uses browser local storage only for appearance mode. Administrator session identifiers remain in HttpOnly cookies, push tokens are never persisted to browser storage, and the existing restrictive self-only Content Security Policy remains in force. The token integration has not yet undergone visual cross-browser acceptance.

## Maintenance notification isolation

A maintenance window scoped to a monitor suppresses that monitor's transitional notifications only; unrelated monitors continue to alert. Global windows deliberately suppress all affected monitor transitions. Public status overrides remain filtered to explicitly published maintenance. A linked maintenance row is removed with its monitor to prevent accidental expansion of its scope. Operational notifications remain best-effort and should not be treated as guaranteed delivery.

## Stale-work and secret-rotation race defense

Monitor configuration has an incrementing revision. Background checks can only persist results against their dispatch-time revision. Push heartbeats validate their hash at transaction commit time, not only at initial HTTP route lookup; the SQLite writer transaction serializes with token changes. A token rotated while a request is in flight must not allow that request to record a heartbeat after revocation. These defenses are covered by direct race-condition regression tests. They do not provide a durable event outbox or full multi-instance synchronization for independently running scheduler processes.
