# Changelog

All notable changes to Energy Report are documented here.

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
- HACS metadata, English/Italian translations, tests and reproducible visual assets.
