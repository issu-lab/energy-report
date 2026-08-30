"""Report resend button for Energy Report."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities([EnergyReportResendButton(controller, entry)])


class EnergyReportResendButton(EnergyReportEntity, ButtonEntity):
    _attr_translation_key = "resend_last_report"

    def __init__(self, controller, entry) -> None:
        super().__init__(controller, entry, "resend_last_report")

    @property
    def available(self) -> bool:
        return self.controller.state.latest_closed_month_key is not None

    async def async_press(self) -> None:
        await self.controller.async_resend_last_report()
