"""Energy Report native Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_TARGET,
    DOMAIN,
    PLATFORMS,
)
from .controller import EnergyReportController
from .http import EnergyReportExportView


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register integration-wide authenticated HTTP views."""
    hass.http.register_view(EnergyReportExportView())
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one independent Energy Report instance."""
    controller = EnergyReportController(hass, entry)
    await controller.async_initialize()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one Energy Report instance."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        controller: EnergyReportController = hass.data[DOMAIN].pop(entry.entry_id)
        await controller.async_shutdown()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy notify services to notify entities when available."""
    if entry.version >= 2:
        return True
    data = dict(entry.data)
    legacy = data.get(CONF_NOTIFICATION_SERVICE)
    if legacy and legacy.startswith("notify."):
        registry = er.async_get(hass)
        if hass.states.get(legacy) is not None or registry.async_get(legacy) is not None:
            data[CONF_NOTIFICATION_TARGET] = legacy
    hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
