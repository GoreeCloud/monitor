# GoreeCloud Monitor — Changelogs

**Record type:** Repository change history  
**Repository:** `GoreeCloud/monitor`  
**Repository ID:** `1336209445`  
**Lifecycle:** Advanced pre-production acceptance candidate; production activation remains gated  
**Migration state:** **Authoritative on `main` after PR #52 merged as `41d88d2a12ad705f7c30160b378738031fbed37d` and default-branch readback verified this record and its preserved histories. Drive-source retirement remains the final migration cleanup gate.**  
**Repository authority baseline:** `main` at `41d88d2a12ad705f7c30160b378738031fbed37d` (PR #52). Latest source-bearing Monitor runtime remains `f59991c2ac577662ddc6f396027b4dc1d637689a` (PR #51).  

## Authority and migration control

This file is the authoritative repository-local human-readable change history for GoreeCloud Monitor under Standard — Repository Feature Tracking and Changelog Governance v1.0.

The pre-migration repository maintained the legacy singular `CHANGELOG.md`. PR #52 preserved its exact Git blob under `docs/changelog-history/repository-changelog-pre-migration.md` and retired the singular root filename from authoritative `main`.

The Drive source `GoreeCloud/Changelogs/Change Log — Monitor.docx` was compared as a complete migration source and is represented by the evidence-preserving repository digest at `docs/changelog-history/drive-changelog-migration-digest.md`. The digest indexes every major source-validation phase and every dated/titled changelog entry from the Drive document.

Historical statements preserve their contemporaneous repository name, lifecycle, implementation evidence, validation state, deployment boundaries, and production claims. Stale historical references such as `GoreeCloud/goreecloud-monitor` remain provenance; live GitHub identity is `GoreeCloud/monitor`, repository ID `1336209445`.

The Drive roadmap and changelog now remain **migration-source-only** pending verified deletion. Their temporary continued existence does not create parallel authority; this repository-local record is authoritative after PR #52 merge and default-branch readback.

## Preserved pre-migration histories

- [Exact repository `CHANGELOG.md` content preserved before retirement](docs/changelog-history/repository-changelog-pre-migration.md)
- [Drive changelog migration digest](docs/changelog-history/drive-changelog-migration-digest.md)

The exact repository changelog preserves detailed Unreleased source history, including scheduled-job/dead-man foundations, Ping/ICMP parity, product identity, Wardveil hardening, Glaze UI work, parallel/runtime evidence, hardened production/recovery work, GoreeCloud Notify/outbox work, and later stabilization changes.

The Drive digest preserves the distinct migration chronology, source-validation phases, target-host/recovery exercises, historical Uptime Kuma evidence, production-dependency retirement, licensing decision, and post-retirement stabilization events without treating stale historical authority claims as current state.

## September 24, 2026 — Glaze UI 1.6.0 source-adoption stabilization candidate

**Change type:** Presentation-system stabilization; Platform Contract reconciliation; regression hardening.

- Moved the active Monitor web presentation target from Glaze UI 1.5.1 to current Official Stable Glaze UI 1.6.0.
- Bound Monitor's adoption ledger to immutable tag `v1.6.0`, accepted release source `a7180679ea851389e0f3004515f9a25f420e716d`, qualification source `c7509c79256b04b0aa67cb9dd0737d7588e0ae4a`, GitHub release `392095913`, and artifact SHA-256 `687268b5eb76917eccae9d935ffa1bead333d5dee50b6098e996a3f44cee50af`.
- Added a local V1.6 presentation mapping while preserving Reduced Motion, Reduced Transparency, contrast, Forced Colors, large-text, touch-target, responsive, local-only, and presentation-only authority behavior.
- Updated Monitor's machine-readable Platform Contract and regression tests to 1.6.0 and corrected its live GitHub repository identity to `GoreeCloud/monitor`.
- Kept Monitor `stable_eligible: false`; representative browser/OS accessibility, semantic-state/recovery, performance, visual, rollback, consumer-registry, target deployment, production, and Stable gates remain open.

---

## September 22, 2026 — PR #52 established repository-native feature and changelog authority

**Change type:** Governance; documentation architecture; source-of-truth migration.

PR #52, **Migrate Monitor feature tracking and changelog governance**, completed the repository-side migration required by Standard — Repository Feature Tracking and Changelog Governance v1.0.

Implemented and reconciled:

- established live repository identity as `GoreeCloud/monitor`, repository ID `1336209445`, instead of the stale `GoreeCloud/goreecloud-monitor` name in older records;
- added root-level `IMPLEMENTED-FEATURES.md`, `PLANNED-FEATURES.md`, and `CHANGELOGS.md`;
- migrated FR-001–FR-014 and current production-acceptance obligations without promoting partial or acceptance-gated work to complete status;
- preserved the former root `CHANGELOG.md` byte-for-byte as `docs/changelog-history/repository-changelog-pre-migration.md`;
- generated `docs/changelog-history/drive-changelog-migration-digest.md` from the complete Drive changelog source, indexing all major source-validation phases and dated/titled entries;
- updated `FEATURES.md` so it is a supporting current-source overview rather than a competing implemented/planned authority;
- retired root `FEATURE-ROADMAP.md`; and
- retired the legacy singular root `CHANGELOG.md` after exact content preservation.

Validation and promotion:

- exact PR head `df5ca14db4411c94d4ee3403cd92870b9c41754d` passed CI #204 / run `35723882920`, including SQLite source tests, PostgreSQL 17 tests and recovery proof, dependency vulnerability audit, container build/scan/production smoke, and disposable production topology;
- rollback compatibility #159 / run `35723883048` passed immediate-predecessor database compatibility;
- PR #52 was squash-merged to `main` as `41d88d2a12ad705f7c30160b378738031fbed37d`; and
- default-branch readback verified the three required root records after merge.

**Remaining migration cleanup:** Drive `FEATURE-ROADMAP.docx` (file ID `1bseP6Pa9L0bRG_Rw9OBXdp_LRgxOnBgA`) and Drive `Change Log — Monitor.docx` (file ID `1PZt40r8-j0QkAdGCngd8W9wxuuksi2u9`) remain migration-source-only until their permanent deletion and 404/absence verification. The stale Project Specification repository-name / Glaze-version conflict remains tracked as `DOC-RECON-01` in `PLANNED-FEATURES.md` and is not silently rewritten by this migration.

## Current factual baseline after the imported history

Current repository source records GoreeCloud Monitor as an **advanced pre-production acceptance candidate**. Uptime Kuma and ntfy were retired from `goreecloud-vps-01` on September 18, 2026, but predecessor retirement does not automatically establish Monitor production authority.

Current source includes the Glaze UI 1.6.0 source-adoption stabilization candidate, scheduled-job/dead-man monitoring, low-privilege Ping/ICMP, hardened production topology, recovery/migration tooling, Notify producer/outbox foundations, privacy/security controls, and read-only Manager integrations described in `IMPLEMENTED-FEATURES.md`.

Open production and Stable gates are recorded in `PLANNED-FEATURES.md` and must not be inferred from source, CI, historical deployment evidence, predecessor retirement, or documentation alone.

## Changelog maintenance rule

Meaningful GoreeCloud Monitor changes must be recorded through this repository-local `CHANGELOGS.md`, using linked history files when volume requires it. The legacy root `CHANGELOG.md` and Drive `Change Log — Monitor.docx` must not be recreated as alternate authoritative changelogs.

Historical facts may be corrected only through additive, traceable correction entries. Do not rewrite older evidence to resemble later architecture or lifecycle state.

## 2026-09-27

- Hardened the retired Uptime Kuma evidence collector so it fails closed unless the operator explicitly acknowledges historical-predecessor use, emits a historical-only schema/authority boundary, and cannot be mistaken for current Monitor production authority.
