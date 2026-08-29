"""Native Energy Report sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .controller import EnergyReportController
from .entity import EnergyReportEntity


@dataclass(frozen=True, kw_only=True)
class EnergyReportSensorDescription(SensorEntityDescription):
    value_fn: Callable[[EnergyReportController], Any]


SENSORS = (
    EnergyReportSensorDescription(
        key="current_month_energy",
        translation_key="current_month_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda controller: controller.current_record.total_kwh,
    ),
    EnergyReportSensorDescription(
        key="current_month_cost",
        translation_key="current_month_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda controller: controller.current_record.cost,
    ),
    EnergyReportSensorDescription(
        key="forecast_energy",
        translation_key="forecast_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda controller: controller.forecast[0],
    ),
    EnergyReportSensorDescription(
        key="forecast_cost",
        translation_key="forecast_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda controller: controller.forecast[1],
    ),
    EnergyReportSensorDescription(
        key="annual_energy",
        translation_key="annual_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda controller: controller.annual_kwh,
    ),
    EnergyReportSensorDescription(
        key="annual_cost",
        translation_key="annual_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda controller: controller.annual_cost,
    ),
    EnergyReportSensorDescription(
        key="previous_month_energy",
        translation_key="previous_month_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda controller: (
            None if controller.previous_record is None else controller.previous_record.total_kwh
        ),
    ),
    EnergyReportSensorDescription(
        key="previous_month_cost",
        translation_key="previous_month_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda controller: (
            None if controller.previous_record is None else controller.previous_record.cost
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    controller: EnergyReportController = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        EnergyReportSensor(controller, entry, description) for description in SENSORS
    ]
    entities.append(EnergyReportDiagnosticSensor(controller, entry))
    async_add_entities(entities)


class EnergyReportSensor(EnergyReportEntity, SensorEntity):
    entity_description: EnergyReportSensorDescription

    def __init__(self, controller, entry, description) -> None:
        super().__init__(controller, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        value = self.entity_description.value_fn(self.controller)
        return None if value is None else round(value, 6)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.device_class == SensorDeviceClass.MONETARY:
            return self.controller.currency
        return self.entity_description.native_unit_of_measurement


class EnergyReportDiagnosticSensor(EnergyReportEntity, SensorEntity):
    _attr_translation_key = "diagnostics"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, controller, entry) -> None:
        super().__init__(controller, entry, "diagnostics")
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str:
        return self.controller.diagnostic_status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.controller.diagnostic_attributes

