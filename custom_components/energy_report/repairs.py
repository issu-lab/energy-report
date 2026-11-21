"""Native Home Assistant repair flow for consumption anomalies."""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import ANOMALY_ISSUE_PREFIX, DOMAIN


class AnomalyRepairFlow(RepairsFlow):
    """Explain one anomaly and apply an explicit accounting decision."""

    def __init__(self, entry_id: str, target: str) -> None:
        self._entry_id = entry_id
        self._target = target

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show evidence and handle the selected decision."""
        controller = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if controller is None:
            return self.async_abort(reason="instance_unavailable")
        item = next(
            (
                candidate
                for candidate in controller.pending_anomaly_reviews()
                if candidate["target"] == self._target
            ),
            None,
        )
        if item is None:
            return self.async_abort(reason="anomaly_already_resolved")
        # Home Assistant injects issue_id into the first call. Only a payload
        # containing decision is an actual form submission.
        if user_input is not None and "decision" in user_input:
            try:
                await controller.async_review_anomaly(
                    self._target,
                    user_input["decision"],
                )
            except ValueError:
                return self.async_abort(reason="anomaly_already_resolved")
            return self.async_create_entry(data={})

        unavailable = "not available"
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required("decision"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["accept_increment", "confirm_exclusion"],
                            translation_key="anomaly_decision",
                        )
                    )
                }
            ),
            description_placeholders={
                "instance": controller.name,
                "month": item["month_key"],
                "detected_at": str(item["detected_at"]),
                "source": str(item["source"]),
                "previous": (
                    unavailable
                    if item["previous_value_kwh"] is None
                    else f"{item['previous_value_kwh']:.6f}"
                ),
                "new": (
                    unavailable
                    if item["new_value_kwh"] is None
                    else f"{item['new_value_kwh']:.6f}"
                ),
                "interval": (
                    unavailable
                    if item["interval_minutes"] is None
                    else f"{item['interval_minutes']:.2f}"
                ),
                "excluded": f"{item['excluded_kwh']:.6f}",
                "limit": (
                    unavailable
                    if item["plausible_limit_kwh"] is None
                    else f"{item['plausible_limit_kwh']:.6f}"
                ),
                "reason": item["reason"],
                "cost": f"{item['impact_cost']:.2f}",
                "currency": item["currency"],
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for an Energy Report repair issue."""
    if not issue_id.startswith(ANOMALY_ISSUE_PREFIX) or data is None:
        return ConfirmRepairFlow()
    entry_id = data.get("entry_id")
    target = data.get("target")
    if not isinstance(entry_id, str) or not isinstance(target, str):
        return ConfirmRepairFlow()
    return AnomalyRepairFlow(entry_id, target)
