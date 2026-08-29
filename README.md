![Energy Report](assets/energy-report-banner-light.png)

<div align="center">

[![Status](https://img.shields.io/badge/status-active%20development-F0B429?style=flat-square)](#project-status)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5?style=flat-square&logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-custom%20integration-C346F4?style=flat-square)](https://www.hacs.xyz/)
[![License](https://img.shields.io/badge/license-MIT-C346F4?style=flat-square)](https://github.com/issu-lab/energy-report/blob/main/LICENSE)

**Native Home Assistant consumption accounting and monthly cost reports.**

Energy Report creates a resilient energy ledger from an existing cumulative energy sensor, an instantaneous power sensor or both. It preserves consumption across meter resets and replacements, closes monthly periods and produces compact notifications plus portable annual CSV archives.

</div>

---

## Project Status

| Field | Current state |
|---|---|
| **Maturity** | 🟡 Active Development |
| **Used in my homelab** | ❌ Not yet |
| **Recommended for production** | ❌ Not yet |
| **Setup difficulty** | 🟢 Beginner |
| **Documentation** | ✅ Complete for initial testing |
| **Current version** | `0.1.0` |
| **Minimum Home Assistant** | 2026.8.0 |
| **Local tests** | ✅ 21 tests |
| **Cumulative-energy validation** | ❌ Not yet |
| **Power-only validation** | ❌ Not yet |
| **Dual-source validation** | ❌ Not yet |

> [!WARNING]
> Version 0.1.0 is an initial testing release. Its accounting logic has dependency-free unit coverage, but the integration has not yet completed installation, migration or month-boundary validation on a live Home Assistant system.

> [!IMPORTANT]
> Do not run Energy Report and the previous AppDaemon monitor against the same accounting workflow after cutover. Reconstruct and approve the historical CSV, establish the new source baseline, then stop the old monthly reporting path to avoid conflicting reports.

---

## Why It Exists

Energy Report grew from a real-world need: replace a site-specific AppDaemon energy monitor with one reusable Home Assistant integration that does not lose its accounting history when a meter resets or is replaced.

The original application consumed one cumulative Shelly energy sensor, stored month and year totals in a local JSON file, applied one tariff, projected the current month and sent a Telegram report. It also exposed important limitations:

- the monthly reset could be missed while AppDaemon was offline;
- large deltas were discarded using a fixed threshold;
- the hardware counter remained too closely coupled to the accounting history;
- the notification destination was site-specific;
- only one cumulative source type was supported;
- historical data was not exported as a portable annual archive.

Energy Report keeps the useful experience while replacing those assumptions with native config entries, entities, versioned storage, robust scheduling and provider-neutral notifications.

### Home Assistant Integration and Device

Energy Report is installed and managed as a HACS custom integration. Each configured consumption ledger is represented as one Home Assistant device that groups its energy, cost, forecast, tariff, diagnostic and report entities. It therefore appears with regular integrations instead of dispersing its configuration among Home Assistant Helpers or YAML files.

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
- 📅 Timezone-aware monthly close with startup catch-up.
- 📊 Current month, previous month and current year entities.
- 💶 Modifiable tariff, current cost and month-end projections.
- 📬 One configurable Home Assistant notification service per instance.
- 🔁 Native button to resend the last immutable monthly report.
- 🗂️ Atomic annual CSV archives with a documented public schema.
- 📥 Transactional CSV history import with preview and conflict rejection.
- 🩺 Native diagnostics with measured, reconstructed and incomplete data quality.
- 🌍 English and Italian UI translations.
- 📦 HACS-ready repository layout.

Energy Report intentionally handles positive consumption only. Solar production, grid export, batteries, time-of-use tariffs, fixed charges and cross-instance aggregation are not part of version 0.1.0.

---

## Installation with HACS

Energy Report is prepared as a custom HACS repository:

<div align="center">

[![Open your Home Assistant instance and open Energy Report inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=issu-lab&repository=energy-report&category=integration)

</div>

The button opens Energy Report directly as a custom integration repository in HACS. Alternatively, add it manually:

1. Open **HACS** in Home Assistant.
2. Open the top-right menu and select **Custom repositories**.
3. Add `https://github.com/issu-lab/energy-report`.
4. Select **Integration** as the repository type.
5. Download Energy Report.
6. Restart Home Assistant.
7. Open **Settings → Devices & services → Add integration**.
8. Search for **Energy Report**.

For local validation before publication, copy `custom_components/energy_report` into the Home Assistant `custom_components` directory and restart Home Assistant.

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

Enter the tariff per kWh and one existing notification service, for example `notify.mobile_app_phone`. Energy Report can send a clearly labelled test notification before completing setup.

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

The **Resend last report** button uses the already consolidated record. It does not recalculate the month, change storage or duplicate CSV rows.

---

## Entities

Each configured instance creates:

- current-month energy and cost;
- month-end energy and cost forecasts;
- current-year energy and cost;
- previous-month energy and cost;
- modifiable tariff;
- resend-last-report button;
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
schema_version,record_status,year,month,period_start,period_end,measured_kwh,reconstructed_kwh,total_kwh,coverage_percent,unknown_duration_minutes,excluded_kwh,tariff_per_kwh,currency,total_cost,data_quality,origin,closed_at
```

Generated annual archives contain closed records only.

---

## Historical CSV Import

The documented template is available in [`examples/history-import.csv`](examples/history-import.csv).

Import rules:

1. use ISO timestamps and a decimal point;
2. use `closed` for consolidated months;
3. include at most one `open` record for the current month;
4. keep all values non-negative and internally consistent;
5. copy the file to `/config/energy_report/import`;
6. open **Configure → Import CSV history**;
7. enter the filename and review the preview;
8. confirm only when month counts are correct.

The complete file is validated before state changes. Any existing-month conflict rejects the entire import. Imported records do not send notifications.

For the initial Lodi migration, monthly Shelly data will be reconstructed and reviewed in this public CSV format. The legacy AppDaemon JSON remains comparison evidence only; no Shelly- or AppDaemon-specific converter is embedded in the integration.

---

## Diagnostics

The disabled-by-default diagnostic sensor reports:

- source mode and data quality;
- measured and reconstructed current-month energy;
- power shadow total and percentage deviation;
- coverage;
- resets, source changes and anomalous jumps;
- cumulative-source gap state;
- last valid energy and power timestamps;
- last closed report and notification outcome;
- latest actionable error.

Downloadable diagnostics include the current accounting record and annual totals. They exclude source entity IDs and the configured notification target.

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

The GitHub workflow also runs HACS validation and Hassfest.

Detailed design and verification contracts are available in:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/ACCEPTANCE_CRITERIA.md`](docs/ACCEPTANCE_CRITERIA.md)

---

## Migration from AppDaemon

Before cutover:

1. export or record the available monthly Shelly history;
2. reconstruct the Energy Report CSV and review every row;
3. install Energy Report without deleting the legacy evidence;
4. import the approved closed months and optional current-month balance;
5. establish the native integration baseline;
6. compare native and AppDaemon values during a controlled observation window;
7. stop the AppDaemon monthly report only after validation;
8. keep rollback evidence until the first native monthly close succeeds.

Do not run two independent systems as authoritative monthly ledgers after cutover.

---

## Known Limitations

- Live Home Assistant validation has not started.
- HACS and Hassfest currently run only in the prepared GitHub workflow.
- Power integration accuracy depends on update frequency and source availability.
- Consumption-only accounting does not model photovoltaic production or export.
- Negative energy flows are unsupported.
- Time-of-use tariffs, fixed charges and progressive pricing are unsupported.
- Closed months are intentionally immutable.
- Instances are independent and cannot be aggregated by Energy Report 0.1.0.
- The initial compatibility baseline is Home Assistant 2026.8 or newer.

---

## License

Released under the [MIT License](https://github.com/issu-lab/energy-report/blob/main/LICENSE).

---

<div align="center">

This project is part of the **iSSU Open Homelab ecosystem**.

<a href="https://github.com/issu-lab/Open-Homelab">
  <img src="assets/issu-open-homelab-badge.png"
       alt="Explore iSSU Open Homelab"
       width="480">
</a>

</div>
