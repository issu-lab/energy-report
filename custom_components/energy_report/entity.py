"""Shared entity base for Energy Report."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_INSTANCE_ID, DOMAIN
from .controller import EnergyReportController


class EnergyReportEntity(Entity):
    """Base entity bound to one independent controller."""

    _attr_has_entity_name = True

    def __init__(self, controller: EnergyReportController, entry: ConfigEntry, key: str) -> None:
        self.controller = controller
        self.entry = entry
        self._attr_unique_id = f"{entry.data[CONF_INSTANCE_ID]}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="iSSU Lab",
            model="Energy Report",
            sw_version=str(entry.version),
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.controller.async_add_update_listener(self._controller_updated)
        )

    def _controller_updated(self) -> None:
        self.async_write_ha_state()
