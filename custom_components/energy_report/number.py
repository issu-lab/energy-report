"""Tariff number entity for Energy Report."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .controller import EnergyReportController
from .entity import EnergyReportEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    controller: EnergyReportController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EnergyReportTariff(controller, entry)])


class EnergyReportTariff(EnergyReportEntity, NumberEntity):
    _attr_translation_key = "tariff"
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 0.001
    _attr_mode = NumberMode.BOX

    def __init__(self, controller, entry) -> None:
        super().__init__(controller, entry, "tariff")

    @property
    def native_value(self) -> float:
        return self.controller.tariff

    @property
    def native_unit_of_measurement(self) -> str:
        return f"{self.controller.currency}/kWh"

    async def async_set_native_value(self, value: float) -> None:
        await self.controller.async_set_tariff(value)

