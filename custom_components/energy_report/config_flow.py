"""Config, options, source replacement and history import flows."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .archive import ArchiveError, ImportPreview
from .const import (
    CONF_ENERGY_SENSOR,
    CONF_INSTANCE_ID,
    CONF_NAME,
    CONF_NOTIFICATION_SERVICE,
    CONF_POWER_SENSOR,
    CONF_SOURCE_MODE,
    CONF_TARIFF,
    DEFAULTS,
    DEFAULT_TARIFF,
    DOMAIN,
    MODE_DUAL,
    MODE_ENERGY,
    MODE_POWER,
    OPT_MAX_POWER_KW,
    OPT_NOTIFICATION_SERVICE,
    OPT_REPORT_HOUR,
    OPT_SOURCE_TIMEOUT_MINUTES,
    SOURCE_MODES,
)
from .report import render_test_report

ENERGY_UNITS = {"Wh", "kWh", "MWh"}
POWER_UNITS = {"W", "kW", "MW"}


def _entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _number(minimum: float, maximum: float, step: float = 0.1):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


class EnergyReportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up a reusable Energy Report instance."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            instance_id = slugify(user_input[CONF_NAME])
            await self.async_set_unique_id(instance_id)
            self._abort_if_unique_id_configured()
            self._data.update(user_input)
            self._data[CONF_INSTANCE_ID] = instance_id
            return await self.async_step_sources()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(CONF_SOURCE_MODE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(SOURCE_MODES),
                            translation_key="source_mode",
                        )
                    ),
                }
            ),
        )

    async def async_step_sources(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_sources(user_input, self._data[CONF_SOURCE_MODE])
            if not errors:
                self._data.update(user_input)
                return await self.async_step_reporting()
        fields: dict[Any, Any] = {}
        if self._data[CONF_SOURCE_MODE] in {MODE_ENERGY, MODE_DUAL}:
            fields[vol.Required(CONF_ENERGY_SENSOR)] = _entity_selector()
        if self._data[CONF_SOURCE_MODE] in {MODE_POWER, MODE_DUAL}:
            fields[vol.Required(CONF_POWER_SENSOR)] = _entity_selector()
        return self.async_show_form(
            step_id="sources",
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def async_step_reporting(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            service = user_input[CONF_NOTIFICATION_SERVICE]
            if not self._service_exists(service):
                errors[CONF_NOTIFICATION_SERVICE] = "notification_service_not_found"
            else:
                self._data.update(user_input)
                return await self.async_step_test_notification()
        return self.async_show_form(
            step_id="reporting",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TARIFF, default=DEFAULT_TARIFF): _number(0, 10, 0.001),
                    vol.Required(CONF_NOTIFICATION_SERVICE): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_test_notification(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input["send_test"]:
                try:
                    domain, service = self._data[CONF_NOTIFICATION_SERVICE].split(".", 1)
                    rendered = render_test_report(
                        self._data[CONF_NAME], self.hass.config.language
                    )
                    await self.hass.services.async_call(
                        domain,
                        service,
                        {
                            "title": rendered.title,
                            "message": rendered.message,
                        },
                        blocking=True,
                    )
                except Exception:
                    errors["base"] = "notification_test_failed"
            if not errors:
                return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return self.async_show_form(
            step_id="test_notification",
            data_schema=vol.Schema({vol.Required("send_test", default=True): bool}),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        """Explicitly replace validated sources while retaining the ledger."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            mode = user_input[CONF_SOURCE_MODE]
            errors = self._validate_sources(user_input, mode)
            if not errors:
                await self.async_set_unique_id(entry.unique_id)
                self._abort_if_unique_id_mismatch()
                updated = dict(entry.data)
                updated.update(user_input)
                if mode == MODE_ENERGY:
                    updated.pop(CONF_POWER_SENSOR, None)
                elif mode == MODE_POWER:
                    updated.pop(CONF_ENERGY_SENSOR, None)
                return self.async_update_reload_and_abort(entry, data_updates=updated)
        current = entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE_MODE, default=current[CONF_SOURCE_MODE]): (
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=list(SOURCE_MODES),
                                translation_key="source_mode",
                            )
                        )
                    ),
                    vol.Optional(
                        CONF_ENERGY_SENSOR,
                        default=current.get(CONF_ENERGY_SENSOR),
                    ): _entity_selector(),
                    vol.Optional(
                        CONF_POWER_SENSOR,
                        default=current.get(CONF_POWER_SENSOR),
                    ): _entity_selector(),
                }
            ),
            errors=errors,
        )

    def _validate_sources(self, data: dict[str, Any], mode: str) -> dict[str, str]:
        errors: dict[str, str] = {}
        if mode in {MODE_ENERGY, MODE_DUAL}:
            entity_id = data.get(CONF_ENERGY_SENSOR)
            if not entity_id or not self._valid_sensor(entity_id, "energy", ENERGY_UNITS):
                errors[CONF_ENERGY_SENSOR] = "invalid_energy_sensor"
        if mode in {MODE_POWER, MODE_DUAL}:
            entity_id = data.get(CONF_POWER_SENSOR)
            if not entity_id or not self._valid_sensor(entity_id, "power", POWER_UNITS):
                errors[CONF_POWER_SENSOR] = "invalid_power_sensor"
        return errors

    def _valid_sensor(self, entity_id: str, device_class: str, units: set[str]) -> bool:
        state = self.hass.states.get(entity_id)
        expected_state_classes = (
            {"total", "total_increasing"}
            if device_class == "energy"
            else {"measurement"}
        )
        return bool(
            state
            and state.attributes.get(ATTR_DEVICE_CLASS) == device_class
            and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) in units
            and state.attributes.get("state_class") in expected_state_classes
        )

    def _service_exists(self, service_ref: str) -> bool:
        try:
            domain, service = service_ref.split(".", 1)
        except ValueError:
            return False
        return self.hass.services.has_service(domain, service)

    @staticmethod
    def async_get_options_flow(config_entry):
        return EnergyReportOptionsFlow()


class EnergyReportOptionsFlow(config_entries.OptionsFlow):
    """Advanced settings, notification test and transactional import."""

    def __init__(self) -> None:
        self._preview: ImportPreview | None = None

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "test_notification", "import_history"],
        )

    def _current(self, key: str):
        return self.config_entry.options.get(key, DEFAULTS.get(key))

    async def async_step_settings(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not EnergyReportConfigFlow._service_exists(self, user_input[OPT_NOTIFICATION_SERVICE]):
                errors[OPT_NOTIFICATION_SERVICE] = "notification_service_not_found"
            else:
                return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPT_NOTIFICATION_SERVICE,
                        default=self.config_entry.options.get(
                            OPT_NOTIFICATION_SERVICE,
                            self.config_entry.data[CONF_NOTIFICATION_SERVICE],
                        ),
                    ): selector.TextSelector(),
                    vol.Required(OPT_MAX_POWER_KW, default=self._current(OPT_MAX_POWER_KW)): _number(0.1, 100, 0.1),
                    vol.Required(
                        OPT_SOURCE_TIMEOUT_MINUTES,
                        default=self._current(OPT_SOURCE_TIMEOUT_MINUTES),
                    ): _number(1, 1440, 1),
                    vol.Required(OPT_REPORT_HOUR, default=self._current(OPT_REPORT_HOUR)): _number(0, 23, 1),
                }
            ),
            errors=errors,
        )

    async def async_step_test_notification(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        service = self.config_entry.options.get(
            OPT_NOTIFICATION_SERVICE,
            self.config_entry.data[CONF_NOTIFICATION_SERVICE],
        )
        if user_input is not None:
            controller = self.hass.data[DOMAIN][self.config_entry.entry_id]
            if await controller.async_send_test_notification(service):
                return self.async_create_entry(title="", data=self.config_entry.options)
            errors["base"] = "notification_test_failed"
        return self.async_show_form(
            step_id="test_notification",
            data_schema=vol.Schema({vol.Required("confirm", default=True): bool}),
            errors=errors,
            description_placeholders={"service": service},
        )

    async def async_step_import_history(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            controller = self.hass.data[DOMAIN][self.config_entry.entry_id]
            try:
                self._preview = await controller.async_preview_import(user_input["filename"])
                return await self.async_step_confirm_import()
            except ArchiveError as err:
                errors["base"] = "history_import_invalid"
        return self.async_show_form(
            step_id="import_history",
            data_schema=vol.Schema({vol.Required("filename"): selector.TextSelector()}),
            errors=errors,
        )

    async def async_step_confirm_import(self, user_input=None) -> ConfigFlowResult:
        if self._preview is None:
            return self.async_abort(reason="missing_import_preview")
        if user_input is not None:
            if user_input["confirm"]:
                controller = self.hass.data[DOMAIN][self.config_entry.entry_id]
                await controller.async_apply_import(self._preview)
            return self.async_create_entry(title="", data=self.config_entry.options)
        return self.async_show_form(
            step_id="confirm_import",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={
                "filename": self._preview.path.name,
                "closed_count": str(self._preview.closed_count),
                "open_count": str(self._preview.open_count),
            },
        )
