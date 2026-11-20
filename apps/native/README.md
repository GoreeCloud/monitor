# GoreeCloud Monitor — native Linux and Android

A Flutter-based native status application using the Flutter Linux desktop runner and Android application embedding. This is **not** a browser WebView or a production-ready release.

## Working source

- Native Material 3 interface and accessible text/theme scaling foundations.
- Public status read API for explicitly published service names, states, response times, and active incidents.
- HTTPS-first API access with optional HTTP loopback for local Linux development only.
- User-entered server URL is only held in memory; no stored credentials, background OS service, or opt-in account sync.
- Refresh button and minute-based refresh while the app remains in foreground.

## Local validation

In this folder run flutter pub get, flutter analyze, flutter test, flutter build linux (Linux), or flutter build apk --debug (Android).

Android requires proper Internet permission, configured TLS endpoints and current signing before distribution. A CI debug APK is not a signed release. Physical-device accessibility, network/failure-state, lifecycle and update/rollback qualification remain open.

GoreeCloud UI is the mandated design authority; the initial theme uses its alpha Iris token values, but full centralized component adoption and founder visual approval are not yet verified.

The server admin token never appears in this viewer; all private monitor administration happens in the authenticated web application pending reviewed, least-privilege native identity support.
