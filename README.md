![Energy Report](assets/energy-report-banner-light.png)

<div align="center">

[![Status](https://img.shields.io/badge/status-stable-2EA44F?style=flat-square)](#project-status)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.11%2B-41BDF5?style=flat-square&logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![Marketplace](https://img.shields.io/badge/Home%20Assistant-Marketplace-41BDF5?style=flat-square&logo=homeassistant&logoColor=white)](#installation-with-marketplace)
[![License](https://img.shields.io/badge/license-MIT-C346F4?style=flat-square)](https://github.com/issu-lab/energy-report/blob/main/LICENSE)

**Native Home Assistant consumption accounting and monthly cost reports.**

Energy Report creates a resilient energy ledger from an existing cumulative energy sensor, an instantaneous power sensor or both. It preserves consumption across meter resets and replacements, closes monthly periods and produces compact notifications plus portable annual CSV archives.

</div>

---

## Project Status

| Field | Current state |
|---|---|
| **Maturity** | 🟢 Stable |
| **Production use** | ✅ Validated |
| **Recommended for production** | ✅ Yes |
| **Setup difficulty** | 🟢 Beginner |
| **Documentation** | ✅ Complete |
| **Current version** | `1.0.2` |
| **Minimum Home Assistant** | 2026.11.0 |
| **Local tests** | ✅ 35 tests |
| **Import and export validation** | ✅ Complete |
| **Notification validation** | ✅ Complete |
| **Multi-instance validation** | ✅ Complete |

> [!IMPORTANT]
> During migration, keep only one system authoritative for monthly accounting and notifications. Import approved history, establish the Energy Report source baseline and disable the previous reporting workflow after validation.

---

## Why It Exists

Energy Report provides one reusable Home Assistant integration for consumption accounting that remains independent from the lifetime of a physical meter. It combines native config entries, entities, versioned storage, robust scheduling and provider-neutral notifications in a single device-oriented workflow.

### Home Assistant Integration and Device

Energy Report is installed and managed through the built-in Home Assistant Marketplace. Each configured consumption ledger is represented as one Home Assistant device that groups its energy, cost, forecast, tariff, diagnostic and report entities. It therefore appears with regular integrations instead of dispersing its configuration among Home Assistant Helpers or YAML files.

The integration consumes existing Home Assistant sensor entities. It does not communicate directly with Shelly hardware, MQTT brokers, cloud APIs or electricity providers.

---

## Features

- ⚡ Native cumulative-energy accounting.
- 📐 Trapezoidal integration of instantaneous power.
- 🔍 Optional dual-source verification and continuity.
- 🧩 Multiple independent Energy Report instances.
- 🖥️ Guided configuration, advanced options and explicit source replacement.
- 💾 Versioned ledger independent from the device lifetime counter.
- 🔄 Reset detection without subtracting or losing recorded consumption.
- 🛡️ Plausibility checks based on elapsed time and configured maximum power.
- 🧾 Auditable anomaly review with explicit accept or confirm-exclusion decisions.
- 📅 Timezone-aware monthly close with startup catch-up.
- 📊 Current month, previous month and current year entities.
- 💶 Modifiable tariff, current cost and month-end projections.
- 📬 One selectable Home Assistant notification entity or group per instance.
- 🔁 Native button to send or resend the latest closed monthly report, including imported history.
- 🗂️ Atomic annual CSV archives with a documented public schema.
- 📥 Native CSV upload with transactional preview and explicit conflict handling.
- 🩺 Native diagnostics with measured, reconstructed and incomplete data quality.
- 🌍 English and Italian UI translations.
- 📦 Home Assistant Marketplace-ready repository layout.

Energy Report intentionally handles positive consumption only. Solar production, grid export, batteries, time-of-use tariffs, fixed charges and cross-instance aggregation are not part of version 1.0.2.

---

<!-- ha-marketplace:exclude-start -->

## Installation with Marketplace

On Home Assistant 2026.11 or newer, Energy Report is installed through the built-in Marketplace:

<div align="center">

[![Open your Home Assistant instance and open Energy Report in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=issu-lab&repository=energy-report&category=integration)

</div>

The button opens Energy Report as an integration repository in the Marketplace. If it is not yet present in the catalog, Home Assistant offers to add it as a custom repository. A GitHub connection is required for custom repositories.

Energy Report uses numeric versions without GitHub pre-release suffixes: `0.0.x` identifies alpha development, `0.x` beta development and `1.x` stable releases. Marketplace follows regular version tags.

For local validation before publication, copy `custom_components/energy_report` into the Home Assistant `custom_components` directory and restart Home Assistant.

<!-- ha-marketplace:exclude-end -->

---

## Guided Setup

### 1. Identity and source mode

Enter a unique instance name, such as `Home`, and choose one strategy:

- `Cumulative energy`
- `Instantaneous power`
- `Energy with power verification`

The original name creates a stable archive directory. Changing the displayed name later does not move historical files.

### 2. Consumption sources

Select the entities required by the chosen mode. Energy Report accepts only sensors with coherent Home Assistant metadata:

| Source | Device class | State class | Units |
|---|---|---|---|
| Cumulative energy | `energy` | `total` or `total_increasing` | `Wh`, `kWh`, `MWh` |
| Instantaneous power | `power` | `measurement` | `W`, `kW`, `MW` |

Unknown, unavailable, non-numeric, non-finite and negative readings never enter accounting.

### 3. Cost and reporting

Enter the tariff per kWh and select one existing `notify` entity. A Home Assistant notification group can be selected as one destination. Energy Report can send a clearly labelled test notification before completing setup.

The initial wizard intentionally keeps plausibility, timeout and scheduling values out of the main path. They remain available from the integration's **Configure** action.

---

## Default Settings

| Setting | Default |
|---|---:|
| Tariff | 0.240 per kWh |
| Maximum plausible power | 10.0 kW |
| Cumulative-source timeout | 15 minutes |
| Monthly report hour | 08:00 |
| Forecast minimum age | 3 complete days |
| Forecast minimum coverage | 80% |

The currency and timezone come from Home Assistant.

Changing the tariff recalculates the whole open month. Closed months remain immutable.

---

## Cumulative Energy Strategy

This strategy reads positive differences between successive lifetime-energy values. The hardware value is only a source baseline; the internal Energy Report ledger remains authoritative.

When the source decreases, Energy Report treats the change as a meter reset:

1. the recorded month and year totals remain unchanged;
2. the reset is counted in diagnostics;
3. the new value becomes the source baseline;
4. only later positive increments are added.

A positive jump is evaluated against elapsed time and maximum plausible power. An implausible increment is excluded and diagnosed instead of being silently accepted or hidden behind a fixed kWh threshold.

Each new exclusion records its timestamp, source, readings, interval, plausibility limit, energy and cost impact. Energy Report immediately creates a native Home Assistant Repair linked to the affected config entry. Selecting **Fix** explains the evidence and offers two explicit decisions: include the increment as valid consumption, or confirm its exclusion after review. The device also exposes an enabled **Anomalies to review** sensor with the pending count and a concise summary. The advanced options flow remains available as a secondary path.

Decisions are idempotent, retain provenance and create a bounded pre-change backup. Older ledgers that only contain an aggregate excluded value produce a transparent legacy Repair: the aggregate remains reviewable, but Energy Report does not invent missing timestamps, readings or plausibility limits.

---

## Instantaneous Power Strategy

This strategy integrates power over time using the trapezoidal rule. The resulting energy is labelled **reconstructed from power**, because its accuracy depends on source update frequency and availability.

The integration never claims that reconstructed energy is identical to a hardware cumulative counter. Coverage and gaps remain visible in entities, CSV archives and monthly reports.

---

## Energy with Power Verification

Dual mode gives each source a distinct responsibility:

- cumulative energy provides normal accounting increments;
- power maintains an independent shadow total for comparison;
- when the cumulative source becomes unavailable or stale, power provides reconstructed continuity;
- when cumulative energy returns, it establishes a fresh baseline so the outage interval cannot be counted twice.

Power-derived and meter-derived energy are always kept distinguishable. The integration reports deviation and data quality rather than automatically declaring one physical sensor faulty.

---

## Source Replacement

Use the integration's **Reconfigure** action when a Shelly or another meter is replaced, renamed or deliberately changed.

The replacement flow validates the new entity, preserves the ledger, records the source change and establishes a fresh baseline. The absolute value already present on the new device is never added to historical consumption.

Changing an entity ID through an undocumented storage edit is unsupported.

---

## Monthly Close and Report

The previous month closes on the first day at 08:00 by default, using the Home Assistant timezone. If Home Assistant is offline at that time, overdue native periods close at startup. Missing sources never postpone closure.

Storage and CSV finalization happen before external notification delivery. A delivery failure creates a persistent Home Assistant notification and remains visible in diagnostics.

Notification text automatically follows the language configured in Home Assistant. English is used as the fallback when a translation is unavailable.

Example compact report:

```text
⚡ ENERGY REPORT · Home
📅 07/2026
📊 Consumption: 183.65 kWh
↔️ Previous month: +12.30 kWh · +7.2%
📈 Annual total: 1146.80 kWh
✅ Data coverage: 100.0%
💶 Tariff: 0.2800 EUR/kWh
💰 Total cost: 51.42 EUR
```

Reconstructed consumption appears only when present. Coverage problems, unquantified gaps and excluded increments are placed after tariff and total cost as explicit warnings.

The **Send or resend latest report** button uses the newest consolidated record, including an imported closed month. It does not recalculate the month, change storage or duplicate CSV rows. Import itself never sends notifications automatically.

---

## Entities

Each configured instance creates:

- current-month energy and cost;
- month-end energy and cost forecasts;
- current-year energy and cost;
- previous-month energy and cost;
- modifiable tariff;
- send-or-resend-latest-report button;
- disabled-by-default diagnostic sensor.

Forecasts use the average rate of the covered current-month interval. They remain unavailable during the first three complete days and when coverage is below 80%.

---

## CSV Archive

Every instance owns a stable directory:

```text
/config/energy_report/<instance-id>/energy-report-2026.csv
```

Home Assistant's versioned store is authoritative. Annual CSV files are portable derived archives, rewritten atomically from that state and intended for external backup or spreadsheet use.

The exact ordered schema is:

```csv
schema_version,record_status,year,month,period_start,period_end,measured_kwh,reconstructed_kwh,total_kwh,coverage_percent,unknown_duration_minutes,excluded_kwh,tariff_per_kwh,currency,total_cost,data_quality,origin,snapshot_at,closed_at
```

Operational annual archives contain closed records only. From **Configure → Export CSV history**, the current-year backup also includes the open month with a fresh `snapshot_at`; the previous-year backup contains closed months. The resulting instance-specific file is downloaded through an authenticated Home Assistant endpoint and can be reimported with the same CSV importer.

---

## Historical CSV Import

The documented template is available in [`examples/history-import.csv`](examples/history-import.csv).

Import rules:

1. use ISO timestamps and a decimal point;
2. use `closed` for consolidated months;
3. include at most one `open` record for the current month;
4. keep all values non-negative and internally consistent;
5. for an open current-month row, set `snapshot_at` to the timestamp represented by its totals;
6. open **Configure → Import CSV history**;
7. verify the target instance name and stable ID, choose the CSV from the device running the browser and review the preview;
8. if the current month conflicts, explicitly keep Energy Report data, safely merge non-overlapping periods or replace it with the CSV snapshot;
9. confirm only when all category counts are correct.

The complete file is validated before state changes. Missing months are imported, identical months are ignored and conflicting closed months are rejected because they are immutable. A safe merge is offered only when the timezone-aware CSV `snapshot_at` is not later than the Home Assistant config-entry creation time: the CSV balance is then added to consumption collected natively after activation, while the current hardware baselines remain in place. Replacement remains an explicit alternative; it stores a backup and resets baselines. Imported records do not send notifications. Schema version 1 remains accepted for closed-history migration, but safe current-month merging requires schema version 2.

The importer is provider-neutral: source-specific conversion remains outside the integration, while the resulting monthly records use the documented public CSV format.

---

## Diagnostics

The disabled-by-default diagnostic sensor reports:

- source mode and data quality;
- measured and reconstructed current-month energy;
- power shadow total and percentage deviation;
- coverage;
- resets, source changes and anomalous jumps;
- pending anomaly reviews, unresolved excluded energy and the latest decision;
- cumulative-source gap state;
- last valid energy and power timestamps;
- last closed report and notification outcome;
- latest actionable error.

Downloadable diagnostics include the current accounting record, annual totals, redacted anomaly events and review decisions. They exclude source entity IDs and the configured notification target.

---

## Development

Run the dependency-free accounting tests:

```shell
python3 -m unittest discover -s tests -v
```

Validate Python and JSON syntax:

```shell
python3 -m compileall custom_components tests
python3 -m json.tool custom_components/energy_report/manifest.json
```

Rebuild banner and social-preview assets from their SVG sources:

```shell
source/build-assets.sh
```

The canonical iSSU footer and integration icons are reused unchanged from the other iSSU repositories and are deliberately not reconstructed by that script.

The GitHub workflow also runs the repository validation required by Marketplace and Hassfest.

Detailed design and verification contracts are available in:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/ACCEPTANCE_CRITERIA.md`](docs/ACCEPTANCE_CRITERIA.md)

---

## Migration from Another Accounting System

Before cutover:

1. export or record the available monthly consumption history;
2. reconstruct the Energy Report CSV and review every row;
3. install Energy Report without deleting the original evidence;
4. import the approved closed months and optional current-month balance;
5. establish the native integration baseline;
6. compare the old and new values during a controlled observation window;
7. stop the previous monthly report only after validation;
8. keep rollback evidence until the first native monthly close succeeds.

Do not run two independent systems as authoritative monthly ledgers after cutover.

---

## Known Limitations

- Marketplace repository validation and Hassfest run in the GitHub workflow.
- Power integration accuracy depends on update frequency and source availability.
- Consumption-only accounting does not model photovoltaic production or export.
- Negative energy flows are unsupported.
- Time-of-use tariffs, fixed charges and progressive pricing are unsupported.
- Closed months are immutable during automatic accounting and CSV import. An explicit, backed-up anomaly review is the only audited correction path.
- Instances are independent and cannot be aggregated by Energy Report 1.0.2.
- Legacy notification services that do not expose a `notify` entity remain usable only for migrated entries until a notification entity is selected.
- The integration compatibility baseline is Home Assistant 2026.11 or newer.

---

## License

Released under the [MIT License](https://github.com/issu-lab/energy-report/blob/main/LICENSE).

---

<div align="center">

This project is part of the **iSSU Open Homelab ecosystem**.

<a href="https://github.com/issu-lab/Open-Homelab">
  <img src="https://raw.githubusercontent.com/issu-lab/energy-report/main/assets/issu-open-homelab-badge.png"
       alt="Explore iSSU Open Homelab"
       width="480">
</a>

</div>
