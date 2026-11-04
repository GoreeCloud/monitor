# GoreeCloud Monitor — GoreeCloud UI Integration

**Owner:** GoreeCloud
**Product:** GoreeCloud Monitor
**Date:** 2026-11-04
**Status:** Active token-foundation integration; full visual acceptance outstanding

## Authoritative design system

GoreeCloud UI (GoreeCloud/gc-ui) remains the sole design-language authority for Monitor. Its tagged Foundations 1.0.1 release supplies the semantic tokens for this frontend; Monitor does not define an alternative design system.

## Verified source and local integration

- Source: https://github.com/GoreeCloud/gc-ui
- Tag: https://github.com/GoreeCloud/gc-ui/releases/tag/foundations-v1.0.1
- File: styles/tokens.css at tag foundations-v1.0.1
- Verified blob SHA: 3ffe26a1c62f59a2ee3c9478dcb31ecc0f9cf444
- Vendored CSS: web/gc-ui-tokens.css; source preserved beneath an attribution header
- License: Apache-2.0; included in LICENSES/GC-UI-APACHE-2.0.txt
- Served from /assets/gc-ui-tokens.css before web/style.css

Tokens supply Canvas, Surface, Lens, typography, accent, semantic colors, spacing, radii and motion. Monitor retains its own application-specific layouts and interaction code. No external font or stylesheet URL is loaded at runtime.

## Appearance behavior

- The HTML default is Iris/dark to avoid an unstyled initial page.
- On load, the operating-system light/dark preference applies unless the user previously selected a mode.
- Both administrator and public status interfaces expose appearance toggles.
- The chosen appearance is stored locally under gc-monitor-theme; secrets are never stored there.
- The upstream token CSS defines reduced motion, reduced transparency and elevated contrast behavior.
- The existing Content Security Policy allows only self-hosted scripts and styles.

## Acceptance gaps

This is a verified source-token integration, not a complete GC UI component migration. Full component consistency, color-contrast checks, keyboard and screen-reader behavior, mobile screenshots, cross-browser visual review and founder visual acceptance remain outstanding. Unit and syntax tests alone cannot establish UI acceptance.

## Upgrade procedure

1. Verify the next upstream release, license, source tree, checksum and compatibility.
2. Compare the canonical tokens against Monitor layout overrides.
3. Update pinned source, source SHA, license and this record together.
4. Run tests, review both appearances in browser on desktop/mobile and validate fallback preferences.
5. Preserve a rollback point and do not modify the canonical design system from this consumer.
