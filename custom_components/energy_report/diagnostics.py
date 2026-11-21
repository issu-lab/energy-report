"""Downloadable non-sensitive diagnostics for Energy Report."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .controller import EnergyReportController


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict:
    controller: EnergyReportController = hass.data[DOMAIN][entry.entry_id]
    anomaly_events = []
    for event in controller.state.anomaly_events:
        raw = event.to_dict()
        raw.pop("source_entity", None)
        raw["impact_cost"] = event.impact_cost
        anomaly_events.append(raw)
    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "mode": controller.mode,
        },
        "runtime": controller.diagnostic_attributes,
        "accounting": {
            "current_month": controller.current_record.to_dict(),
            "month_count": len(controller.state.months),
            "annual_kwh": controller.annual_kwh,
            "annual_cost": controller.annual_cost,
            "anomaly_events": anomaly_events,
            "anomaly_reviews": controller.state.anomaly_reviews,
            "legacy_unresolved_exclusions": {
                key: controller.state.legacy_unresolved_kwh(key)
                for key in controller.state.months
                if controller.state.legacy_unresolved_kwh(key) > 0.000001
            },
        },
    }

