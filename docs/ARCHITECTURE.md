# Architecture

## Boundary

Energy Report is a calculated Home Assistant device integration. It consumes states from existing sensor entities and targets one existing Home Assistant `notify` entity or group through `notify.send_message`. It does not communicate directly with meters, Shelly devices, brokers or cloud APIs.

Each config entry owns one controller, one versioned ledger, one stable archive directory and one set of entities. Entries never aggregate or mutate each other's data.

## Components

- `config_flow.py` validates source metadata and owns setup, source replacement, advanced options, notification testing, import preview and export selection.
- `controller.py` owns listeners, scheduling, persistence, archive generation and notification delivery.
- `models.py` contains dependency-light ledger records, month splitting and forecasts.
- `source.py` contains cumulative delta and power integration decisions.
- `archive.py` owns atomic annual CSV output and transactional import validation.
- `http.py` exposes authenticated, config-entry-scoped annual CSV downloads.
- `report.py` renders provider-neutral plain-text reports.
- `sensor.py`, `number.py` and `button.py` expose native Home Assistant entities.
- `diagnostics.py` returns non-sensitive operational evidence.

## Source precedence

- Energy mode: accepted cumulative deltas are measured energy.
- Power mode: trapezoidal integration is reconstructed energy.
- Dual mode: cumulative deltas are measured and authoritative; power is a shadow comparison. When the cumulative source is unavailable or stale, power becomes reconstructed accounting until the cumulative source returns and establishes a fresh baseline.

The internal ledger, not the device lifetime counter, is authoritative for month, year, cost and reports.

## Safety invariants

- Negative states never enter accounting.
- A cumulative reset updates the baseline without subtracting energy.
- A source replacement never adds the new source's absolute value.
- Implausible positive deltas are excluded, diagnosed and followed by a fresh baseline.
- Dual-source fallback cannot also consume the cumulative delta spanning the same outage.
- Closed months are immutable.
- Notification failure never blocks storage or CSV finalization.
- An overdue close is recovered at startup and is idempotent.
- Import validates the complete file before changing in-memory state.
- Identical imported months are idempotently ignored.
- Conflicting closed months reject the complete import and are never overwritten.
- Replacing a conflicting open month requires an explicit user choice, preserves a Store backup and resets source baselines.
- A current-month merge is available only when `snapshot_at <= config_entry.created_at`; it adds the imported balance to later native accounting and preserves active source baselines.
- Persistent state is versioned; archive schema is independently versioned.
- Import and export always resolve one controller by config entry; one entry cannot mutate or export another entry's ledger.

## Storage

Home Assistant `Store` data is authoritative and keyed by config entry. It holds month records, baselines, source health, import backups and delivery evidence. CSV is a derived annual archive under `/config/energy_report/<instance-id>/`. Import files are selected through Home Assistant's upload control and consumed from temporary managed storage; arbitrary server paths are not accepted by the UI. On-demand exports are limited to the current and previous year, are regenerated from the selected entry's ledger and are downloaded through an authenticated endpoint. They restore accounting history, not transient baselines or diagnostics.

The instance directory is derived once from the original name and does not change when the displayed title changes.

## Out of scope for 0.1

Solar production, export, batteries, negative flows, time-of-use tariffs, fixed charges, cross-entry aggregation, raw sample import and direct device communication.
