# GoreeCloud Monitor

**Development preview — not deployed, security-certified, or suitable as an unattended production paging system.**

GoreeCloud Monitor is a new, original, self-hosted uptime monitor with a Python/SQLite backend, React web console, and native Flutter Linux and Android apps. This is **not a fork** of Uptime Kuma and contains no vendored Uptime Kuma source. The old GoreeCloud Monitor repository was unavailable at its GitHub location during initial inspection; the present repository is a new implementation.

## Working implementation

- HTTP, HTTPS with normal certificate validation, and TCP checks; expected HTTP status, interval (15–86400 seconds), and timeout (1–30 seconds).
- SQLite WAL database, scheduler, bounded per-monitor check history, and transition-based incident opening/resolution.
- Private-by-default monitors; explicitly public status page API, with private target addresses omitted. Strong bearer token protects admin routes and Prometheus metrics.
- React and TypeScript responsive dashboard: monitor status, active public incidents, add/manual-check/delete actions.
- Flutter Linux desktop and Android public status viewer, foreground refresh, OS theme, no persisted credentials.
- Unit/contract tests, Flutter widget tests, GitHub CI, and optional non-root container deployment example.

**Not implemented:** notifications and escalation, DNS/SSL/keyword/cron/heartbeat/push monitors, user accounts/OIDC, maintenance windows, multiple probe sites, signed APK, production HA, automated restore drills, verified GoreeCloud Mesh or GoreeCloud Identity integration. Never rely on the preview as your sole availability alarm.

## Developer quick start

Requirements: Python 3.11+, Node 24+, Flutter SDK for native targets. The server uses **only the Python standard library**.

1. Generate a new API bearer secret locally with openssl rand -hex 32. Export it as MONITOR_API_TOKEN in your shell (do not put secrets in Git, screenshots or messages).
2. From the repository root, run: python3 service/monitor.py --host 127.0.0.1 --port 8765
3. In a separate terminal, run: cd apps/web && npm ci && npm run dev
4. Open http://127.0.0.1:5173. Sign into the admin panel with the token, then add services.
5. Alternatively, on a host with a vetted container engine and Compose installed, export MONITOR_API_TOKEN and run docker compose -f deploy/compose.yaml up --build. The browser console is mapped to local http://127.0.0.1:8088 while the API is reachable only within the Compose network. This example is **not** a production installation.
6. For a native app, run cd apps/native && flutter pub get && flutter run -d linux (or select an Android device). The native viewer requires a separately reachable HTTPS monitor API.

**Private/internal targets are blocked unless intentionally enabled** with MONITOR_ALLOW_PRIVATE_TARGETS=1. The backend resolves target DNS, rejects blocked IPs by default and pins the connection to the vetted IP; it does not follow HTTP redirects. Do not give untrusted users arbitrary monitoring administration access.

### API (preview contract)

| Method | Route | Authentication | Purpose |
| --- | --- | --- | --- |
| GET | /healthz | No | Process liveness |
| GET | /api/v1/status | No | Published services and active public incidents |
| GET | /api/v1/monitors | Bearer | All services |
| POST | /api/v1/monitors | Bearer | Create service |
| POST | /api/v1/monitors/{id}/check | Bearer | Manual probe |
| GET | /api/v1/monitors/{id}/history | Bearer | Latest 200 checks |
| DELETE | /api/v1/monitors/{id} | Bearer | Delete service and check history |
| GET | /metrics | Bearer | Prometheus text metrics |

POST JSON example: {"name":"Public API","target":"https://example.org/","interval_s":60,"timeout_s":8,"expected_status":200,"public":false}

### Safety, release, and data

The backend binds to loopback by default and has **no native TLS or multi-user authentication**. For remote access, use a separately secured HTTPS gateway with appropriate identity, rate limits and egress policies; never expose the raw administrator API directly. The example Compose stack builds both the React web app and backend, maps the web server only to host loopback, and requires explicit token injection. Web API requests are proxied to the internal backend; the API has no host port mapping. Do **not** deploy as production monitoring without independent security and recovery acceptance.

Back up the SQLite database using its backup API rather than copying only the main database file during active WAL writes. Rehearse restores on an isolated host. No analytics or outbound third-party notifications are enabled by default.

### Tests

- Python: python3 -m unittest discover -s tests -v
- Web: cd apps/web && npm ci && npm run build && npm audit --audit-level=high
- Native: cd apps/native && flutter analyze && flutter test
- Linux: flutter build linux inside apps/native on a properly configured Linux host.
- Android: flutter build apk --debug inside apps/native; debug APKs are **not** signed production artifacts.

## GoreeCloud ecosystem

GoreeCloud UI owns approved tokens and design; the alpha Iris colors/semantics in gc-ui inform this initial UI, pending fuller component adoption and founder review. GoreeShield owns privacy and consent (publication opt-in here), Wardveil owns cybersecurity, GoreeCloud Mesh owns interoperability, and GoreeCloud Identity owns authentication. Mentioning MIPS does **not** mean its live service integrations are implemented or validated.

Future opt-in notifications should connect with GoreeCloud Notify, ntfy, or other licensed transports once safeguarded, reliable delivery exists; none is active in this version. Prometheus-standard text output is local functionality without a Prometheus server requirement.

## Third-party sources and license

Original code: MIT License; see LICENSE. Runtime/tool dependencies, used as libraries and not copied into this repository, include React (MIT), Vite (MIT), Flutter (BSD-3-Clause), Python (PSF), and SQLite (public domain). The Flutter tooling generates third-party platform integration files and lockfiles; review actual artifact notices before releases. Uptime Kuma remains a comparative reference, not the code provenance of this source.

This project makes **no claim** of prior Uptime Kuma-derived feature parity or of production deployment.
