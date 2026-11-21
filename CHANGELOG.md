# Changelog

All notable changes to Energy Report are documented here.

## 1.0.4 - 2026-11-21

- Added a configurable 0.050 kWh automatic tolerance for isolated micro-anomalies.
- Kept automatically accepted increments in the ledger and diagnostic event history with explicit provenance.
- Added monthly safeguards that require review after 0.500 kWh or 10 automatically accepted events.
- Allowed setting the tolerance to zero to retain strict manual review.

## 1.0.3 - 2026-11-21

- Fixed the native Repairs flow treating Home Assistant's initial `issue_id` payload as a submitted accounting decision.
- Aligned the Repairs form schema with Home Assistant 2026.11's native `probatio` flow API.

## 1.0.2 - 2026-11-21

- Added native Home Assistant Repairs for detailed and legacy consumption anomalies.
- Added a direct fix flow with clear evidence and explicit accept-or-exclude decisions.
- Added an enabled per-instance sensor that exposes the number and summary of pending anomalies.
- Kept the options-based review as a secondary path while preserving idempotency, provenance and backups.

## 1.0.1 - 2026-11-21

- Declared the official `energy` integration category for Home Assistant Marketplace discovery.
- Updated installation guidance for the built-in Marketplace and set Home Assistant 2026.11 as the supported baseline.
- Added package tests for the category and Marketplace installation metadata.
- Added detailed, per-instance anomaly events with explicit accept-or-exclude review actions.
- Added honest review of legacy aggregate exclusions without fabricating unavailable event details.
- Added idempotent accounting decisions, bounded pre-change backups and redacted diagnostic evidence.

## 1.0.0 - 2026-09-02

- Promoted Energy Report to the first stable production release.
- Validated notification delivery together with per-instance CSV import and export workflows.
- Reworked public documentation to be fully reusable and provider-neutral.
- Removed deployment-specific migration history and personal environment references.

## 0.1.2 - 2026-08-31

- Republished the 0.1.1 application patch under a fresh immutable tag after GitHub codeload returned HTTP 400 for the original `v0.1.1` tag.
- Included the Marketplace-safe absolute README footer URL already present on `main`.

## 0.1.1 - 2026-08-30

- Declared the integration config-entry-only after adding the authenticated export endpoint, clearing the corresponding Hassfest warning.

## 0.1.0 - 2026-08-30

- Adopted numeric-only maturity: `0.0.x` alpha, `0.x` beta and `1.x` stable.
- Enabled sending or resending the newest closed report even when it came from CSV import.
- Identified the target instance by name and stable ID throughout CSV import.
- Added per-instance current-year and previous-year CSV exports through an authenticated Home Assistant download.
- Included the open month and a fresh `snapshot_at` in current-year backups so they can be safely restored through the existing importer.
- Kept operational archives closed-only and preserved import isolation between config entries.

## 0.1.0-alpha.3 - 2026-08-30

- Added a safe current-month merge for non-overlapping CSV and native data.
- Prove non-overlap by comparing CSV `snapshot_at` with the config entry creation time.
- Preserve current source baselines during merge so post-import consumption continues without a gap.
- Keep a bounded Store backup of the native open record before merging.
- Reject merge requests when the CSV lacks a timezone-aware snapshot or overlap cannot be excluded.
- Added merge eligibility and accounting tests plus clearer English/Italian preview guidance.

## 0.1.0-alpha.2 - 2026-08-30

- Replaced typed CSV server paths with Home Assistant's native file upload selector.
- Added import preview categories for new, identical and current-month-conflicting records.
- Kept closed months immutable while allowing an explicit, backed-up current-month replacement.
- Added CSV schema version 2 with `snapshot_at` while retaining version 1 import compatibility.
- Replaced free-text notification services with selectable `notify` entities and groups.
- Added config-entry migration and a temporary legacy notification fallback.
- Expanded import tests and localized errors.

## 0.1.0-alpha.1 - 2026-08-29

- Initial native Home Assistant custom integration.
- Cumulative energy, instantaneous power and dual-verification source modes.
- Versioned ledger, resilient monthly close, tariff, forecasts and diagnostics.
- Annual CSV archive and transactional history import.
- Configurable notification destination, test notification and resend-last-report button.
- Marketplace metadata, English/Italian translations, tests and reproducible visual assets.
