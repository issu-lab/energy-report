# Acceptance criteria

Version 0.1 is acceptable only when all applicable checks pass.

## Accounting

- Cumulative, power-only and dual modes produce isolated totals.
- Wh/kWh/MWh and W/kW/MW normalize correctly.
- Negative, unknown and unavailable values never enter totals.
- Cumulative reset and source replacement preserve the ledger.
- Plausibility uses elapsed time and configured maximum power.
- Power fallback cannot double-count the cumulative recovery interval.
- Intervals spanning a month boundary are split deterministically.
- Closed months cannot be modified by later readings.

## Periods and costs

- First-of-month closure is timezone-aware, idempotent and recovered after restart.
- Source absence cannot postpone closure.
- Tariff changes recalculate only the open month.
- Forecast is hidden for the first three days and when coverage is below 80%.

## Archive and migration

- Annual CSV uses the documented ordered schema and atomic replacement.
- Generated archives contain closed months only.
- On-demand current-year export contains the open month with a timezone-aware snapshot; previous-year export contains closed months.
- Exported files round-trip through the public importer and are scoped to the selected config entry.
- Import uploads through the native file selector and validates the whole file before preview.
- Preview distinguishes new, identical, closed-conflicting and open-conflicting months.
- Identical months are ignored; conflicting closed months are rejected.
- Current-month replacement is explicit, backed up and followed by a fresh source baseline.
- Current-month merge is offered only with proof of non-overlap and preserves the active source baseline.
- At most one open current-month record can be imported.
- Imported data does not send notifications.
- The public importer contains no AppDaemon- or Shelly-specific code.

## Home Assistant and delivery

- Multiple config entries remain independent.
- Source selectors reject incompatible metadata.
- Reconfigure explicitly replaces sources and establishes new baselines.
- One available notification entity or group is selectable and testable.
- Monthly report is compact and exposes reconstructed or incomplete data.
- Send/resend uses the newest closed record, including imported history, and does not touch the archive.
- Failure creates a persistent notification and diagnostic evidence.
- Diagnostics contain no notification target or source entity IDs.

## Package

- Manifest, VERSION and HACS metadata agree.
- English and Italian translation key shapes agree.
- Python compilation and unit tests pass.
- Banner and 1280 x 640 social preview are reproducible; footer and brand icons reuse the canonical iSSU repository assets unchanged.
- No credentials, runtime state, backup files or site-specific entity IDs are included.
