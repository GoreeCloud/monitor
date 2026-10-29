# GoreeCloud Monitor

**Status: alpha / active development.** This project builds an original GoreeCloud monitoring frontend with an independently maintained [Uptime Kuma](https://github.com/louislam/uptime-kuma) v2 backend. It is not a native desktop/mobile application or full Uptime Kuma administration replacement.

The original console follows the semantic colors and Canvas / Surface / Lens direction of [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui). UI compliance has not yet passed full device/screenshot acceptance.

## What works

- Authenticated, read-only monitoring dashboard displaying monitors, status, response times, recent heartbeats and incident information sourced from a Uptime Kuma **public status page**.
- Search, status filtering, manual refresh, UTF-8 CSV export with spreadsheet-formula protection and responsive light/dark appearance.
- Read-only public incident history and maintenance notices when published by Uptime Kuma 2.5.8.
- A server-to-server status adapter. Browser clients never receive the upstream service URL or admin credentials.
- Explicitly distinguish unavailable backend, unconfigured status page, empty monitor group and operational monitor states. Never fabricate uptime.
- Secure-by-default, loopback-bound Docker Compose services, with Kuma data in a persistent volume.

## Getting started

1. Copy .env.example to .env and set two different high-entropy random secrets: MONITOR_ACCESS_TOKEN (at least 24 characters) and MONITOR_SESSION_SECRET (at least 32 characters). Keep .env private.
2. Start with: docker compose up -d --build
3. Forward ports 4305 and 3301 from your VPS over SSH (or another approved private tunnel). Port 4305 is the GoreeCloud Monitor console; port 3301 is the original Uptime Kuma admin UI.
4. Set up Uptime Kuma's administrator and monitors in its own UI. Create a **public status page** whose slug matches KUMA_STATUS_SLUG (default goreecloud). Add monitors that are safe to publish to that page.
5. Open the Monitor console and sign in using MONITOR_ACCESS_TOKEN. Only published status-page monitors are shown.

**Privacy:** Kuma public status pages can be read by anyone with access to their endpoints. Do not publish secret monitor names, addresses or credentials. A protected frontend does not convert upstream public status-page data into private information.

## Operations and verification

Run npm test for automated tests, npm run check for JavaScript parse checks, and docker compose ps / logs to inspect services. The backend image is pinned to louislam/uptime-kuma:2.5.8-slim, reviewed on October 29, 2026. Test any image upgrade before rollout.

Before exposing the console via Caddy and DNS, confirm TLS, private/admin boundaries, origin policy and authenticated ingress. Set MONITOR_PUBLIC_ORIGIN to the exact HTTPS frontend origin. The expected frontend hostname is monitor.goreecloud.com; Uptime Kuma stays private unless separately approved.

The status-page adapter uses public endpoints of Uptime Kuma v2. These are a compatibility boundary rather than a supported full administration API. Monitor creation, notifications, edit/mutation actions and status page publishing remain in the native upstream Uptime Kuma UI. No private Socket.IO API or Docker socket is exposed to Monitor.

Back up the local Kuma volume with SQLite-consistent procedures and perform restore tests on an isolated destination. Do not commit credentials, database files or backups.

## Next capabilities

- Audited, authorized administrative adapter with tested upstream compatibility.
- Incident acknowledgement, maintenance scheduling, alert integrations with GoreeCloud Notify, certificate checks, reliability reports.
- Actual native Android, Windows, Linux, macOS and iOS applications subject to per-platform builds and acceptance.
- Approved DNS/Caddy ingress, UI screenshot-led comparison, accessibility and recovery testing.

## Ownership

Original Monitor code: copyright GoreeCloud, all rights reserved until separately licensed. Uptime Kuma is a separate, MIT-licensed upstream dependency. GC UI tokens used in this repository are from GoreeCloud/gc-ui under Apache-2.0, see THIRD_PARTY_NOTICES.md.
