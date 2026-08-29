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
        },
    }

