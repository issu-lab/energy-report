"""Runtime orchestration for Energy Report."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .archive import CsvArchive, ImportPreview
from .const import (
    ANOMALY_ISSUE_PREFIX,
    CONF_ENERGY_SENSOR,
    CONF_INSTANCE_ID,
    CONF_NAME,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_TARGET,
    CONF_POWER_SENSOR,
    CONF_SOURCE_MODE,
    CONF_TARIFF,
    DEFAULTS,
    DOMAIN,
    EVENT_REPORT_GENERATED,
    MODE_DUAL,
    MODE_ENERGY,
    MODE_POWER,
    OPT_AUTO_ACCEPT_TOLERANCE_KWH,
    OPT_MAX_POWER_KW,
    OPT_NOTIFICATION_SERVICE,
    OPT_NOTIFICATION_TARGET,
    OPT_REPORT_HOUR,
    OPT_SOURCE_TIMEOUT_MINUTES,
    STORE_KEY_PREFIX,
    STORE_VERSION,
)
from .models import (
    LedgerState,
    MonthRecord,
    energy_to_kwh,
    forecast_month,
    month_key,
    power_to_kw,
)
from .report import RenderedReport, render_monthly_report
from .source import process_energy_reading, process_power_reading

_LOGGER = logging.getLogger(__name__)


class EnergyReportController:
    """Own listeners, accounting, persistence, archive and reports."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(
            hass,
            STORE_VERSION,
            f"{STORE_KEY_PREFIX}.{entry.entry_id}",
        )
        self.archive = CsvArchive(hass.config.config_dir, entry.data[CONF_INSTANCE_ID])
        self.state = LedgerState()
        self._listeners: list[Callable[[], None]] = []
        self._update_listeners: list[Callable[[], None]] = []
        self._shutdown = False

    @property
    def name(self) -> str:
        return self.entry.data[CONF_NAME]

    @property
    def mode(self) -> str:
        return self.entry.data[CONF_SOURCE_MODE]

    @property
    def currency(self) -> str:
        return self.hass.config.currency or "EUR"

    def option(self, key: str) -> Any:
        return self.entry.options.get(key, DEFAULTS.get(key))

    @property
    def current_record(self) -> MonthRecord:
        now = dt_util.now()
        return self.state.ensure_month(now, self.tariff, self.currency)

    @property
    def tariff(self) -> float:
        current = self.state.months.get(month_key(dt_util.now()))
        if current is not None:
            return current.tariff_per_kwh
        return float(self.entry.data[CONF_TARIFF])

    @property
    def annual_kwh(self) -> float:
        year = dt_util.now().year
        return sum(record.total_kwh for record in self.state.months.values() if record.year == year)

    @property
    def annual_cost(self) -> float:
        year = dt_util.now().year
        return sum(record.cost for record in self.state.months.values() if record.year == year)

    @property
    def previous_record(self) -> MonthRecord | None:
        first = dt_util.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.state.months.get(month_key(first - timedelta(seconds=1)))

    @property
    def forecast(self) -> tuple[float | None, float | None]:
        return forecast_month(self.current_record, dt_util.now())

    @property
    def diagnostic_status(self) -> str:
        if (
            self.current_record.data_quality == "incomplete"
            or self.state.pending_anomaly_count > 0
            or self.state.last_error
        ):
            return "attention"
        if self.state.energy_gap_active:
            return "degraded"
        return "ok"

    @property
    def diagnostic_attributes(self) -> dict[str, Any]:
        record = self.current_record
        deviation = None
        if record.shadow_power_kwh > 0 and record.total_kwh > 0:
            deviation = (record.shadow_power_kwh - record.total_kwh) / record.total_kwh * 100
        return {
            "mode": self.mode,
            "data_quality": record.data_quality,
            "coverage_percent": round(record.coverage_percent, 2),
            "measured_kwh": round(record.measured_kwh, 4),
            "reconstructed_kwh": round(record.reconstructed_kwh, 4),
            "shadow_power_kwh": round(record.shadow_power_kwh, 4),
            "power_deviation_percent": None if deviation is None else round(deviation, 2),
            "reset_count": self.state.reset_count,
            "source_change_count": self.state.source_change_count,
            "anomaly_count": self.state.anomaly_count,
            "auto_accepted_anomaly_count": sum(
                event.review_status == "auto_accepted_tolerance"
                for event in self.state.anomaly_events
            ),
            "pending_anomaly_count": self.state.pending_anomaly_count,
            "unresolved_excluded_kwh": round(record.unresolved_excluded_kwh, 6),
            "anomaly_review_backup_count": len(self.state.anomaly_review_backups),
            "last_anomaly_review": (
                self.state.anomaly_reviews[-1] if self.state.anomaly_reviews else None
            ),
            "energy_gap_active": self.state.energy_gap_active,
            "last_energy_at": self.state.last_energy_at,
            "last_power_at": self.state.last_power_at,
            "last_report_key": self.state.last_report_key,
            "last_notification_at": self.state.last_notification_at,
            "last_notification_error": self.state.last_notification_error,
            "last_import_at": self.state.last_import_at,
            "last_import_summary": self.state.last_import_summary,
            "import_backup_count": len(self.state.import_backups),
            "last_error": self.state.last_error,
        }

    async def async_initialize(self) -> None:
        """Restore state, reconcile source identity and start listeners."""
        raw = await self.store.async_load() or {}
        self.state = LedgerState.from_dict(raw)
        energy_entity = self.entry.data.get(CONF_ENERGY_SENSOR)
        power_entity = self.entry.data.get(CONF_POWER_SENSOR)
        if self.state.source_energy_entity not in {None, energy_entity}:
            self.state.source_change_count += 1
            self.state.last_energy_kwh = None
            self.state.last_energy_at = None
        if self.state.source_power_entity not in {None, power_entity}:
            self.state.source_change_count += 1
            self.state.last_power_kw = None
            self.state.last_power_at = None
        self.state.source_energy_entity = energy_entity
        self.state.source_power_entity = power_entity
        self.state.ensure_month(dt_util.now(), self.tariff, self.currency)

        if energy_entity:
            self._listeners.append(
                async_track_state_change_event(self.hass, [energy_entity], self._async_energy_event)
            )
            await self._async_seed_energy(self.hass.states.get(energy_entity))
        if power_entity:
            self._listeners.append(
                async_track_state_change_event(self.hass, [power_entity], self._async_power_event)
            )
            await self._async_seed_power(self.hass.states.get(power_entity))
        report_hour = int(self.option(OPT_REPORT_HOUR))
        self._listeners.append(
            async_track_time_change(
                self.hass,
                self._async_scheduled_close,
                hour=report_hour,
                minute=0,
                second=0,
            )
        )
        self._listeners.append(
            async_track_time_interval(self.hass, self._async_watchdog, timedelta(minutes=1))
        )
        await self._async_close_overdue_months()
        await self._async_save()
        self._sync_anomaly_issue()

    async def async_shutdown(self) -> None:
        self._shutdown = True
        for remove in self._listeners:
            remove()
        self._listeners.clear()
        await self._async_save()

    async def _async_seed_energy(self, state: State | None) -> None:
        if state is None:
            return
        value = energy_to_kwh(state.state, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))
        if value is not None and self.state.last_energy_kwh is None:
            self.state.last_energy_kwh = value
            self.state.last_energy_at = dt_util.now().isoformat()

    async def _async_seed_power(self, state: State | None) -> None:
        if state is None:
            return
        value = power_to_kw(state.state, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))
        if value is not None and self.state.last_power_kw is None:
            self.state.last_power_kw = value
            self.state.last_power_at = dt_util.now().isoformat()

    async def _async_energy_event(self, event: Event) -> None:
        new_state: State | None = event.data.get("new_state")
        now = dt_util.now()
        if new_state is None:
            self._mark_energy_gap(now)
            return
        value = energy_to_kwh(
            new_state.state,
            new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
        )
        if value is None:
            self._mark_energy_gap(now)
            await self._async_save_and_publish()
            return
        if self.mode == MODE_DUAL and self.state.energy_gap_active:
            power_entity = self.entry.data.get(CONF_POWER_SENSOR)
            power_state = self.hass.states.get(power_entity) if power_entity else None
            if power_state is not None:
                power_value = power_to_kw(
                    power_state.state,
                    power_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
                )
                if power_value is not None:
                    process_power_reading(
                        self.state,
                        power_value,
                        now,
                        self.tariff,
                        self.currency,
                        True,
                    )
        decision = process_energy_reading(
            self.state,
            value,
            now,
            float(self.option(OPT_MAX_POWER_KW)),
            self.tariff,
            self.currency,
            self.entry.data.get(CONF_ENERGY_SENSOR),
            float(self.option(OPT_AUTO_ACCEPT_TOLERANCE_KWH)),
        )
        if decision.status in {"accepted", "baseline", "reset"}:
            self.state.last_error = None
        self.state.energy_gap_started_at = None
        await self._async_save_and_publish()

    async def _async_power_event(self, event: Event) -> None:
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return
        value = power_to_kw(
            new_state.state,
            new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
        )
        if value is None:
            return
        use_for_accounting = self.mode == MODE_POWER or (
            self.mode == MODE_DUAL and self.state.energy_gap_active
        )
        process_power_reading(
            self.state,
            value,
            dt_util.now(),
            self.tariff,
            self.currency,
            use_for_accounting,
        )
        await self._async_save_and_publish()

    def _mark_energy_gap(self, now: datetime) -> None:
        if self.mode != MODE_DUAL:
            return
        if not self.state.energy_gap_active:
            self.state.energy_gap_active = True
            self.state.energy_gap_started_at = now.isoformat()
            if self.state.last_power_kw is not None:
                # Begin reconstructed accounting exactly at the gap boundary;
                # the preceding power interval remains shadow-only.
                self.state.last_power_at = now.isoformat()

    async def _async_watchdog(self, now: datetime) -> None:
        if self.mode != MODE_DUAL or not self.state.last_energy_at:
            return
        timeout = timedelta(minutes=int(self.option(OPT_SOURCE_TIMEOUT_MINUTES)))
        if now - datetime.fromisoformat(self.state.last_energy_at) > timeout:
            self._mark_energy_gap(now)
            await self._async_save_and_publish()

    async def _async_scheduled_close(self, now: datetime) -> None:
        if now.day == 1:
            await self._async_close_overdue_months()

    async def _async_close_overdue_months(self) -> None:
        now = dt_util.now()
        current_key = month_key(now)
        open_keys = sorted(
            key
            for key, record in self.state.months.items()
            if key < current_key and record.status == "open"
        )
        for key in open_keys:
            record = self.state.months[key]
            if self.state.energy_gap_started_at:
                gap_start = datetime.fromisoformat(self.state.energy_gap_started_at)
                period_start = datetime.fromisoformat(record.period_start)
                period_end = datetime.fromisoformat(record.period_end)
                power_timeout = timedelta(minutes=int(self.option(OPT_SOURCE_TIMEOUT_MINUTES)))
                power_recent = bool(
                    self.state.last_power_at
                    and now - datetime.fromisoformat(self.state.last_power_at) <= power_timeout
                )
                if gap_start <= period_end and not power_recent:
                    effective_start = max(period_start, gap_start)
                    record.unknown_seconds += max(
                        0.0, (period_end - effective_start).total_seconds()
                    )
            closed = self.state.close_month(key, now)
            if closed is None:
                continue
            await self.hass.async_add_executor_job(self.archive.write_year, self.state, closed.year)
            await self._async_save()
            await self._async_send_record(closed)
        pending_reports = sorted(
            (
                record
                for record in self.state.months.values()
                if record.status == "closed"
                and record.origin == "native"
                and record.notification_sent_at is None
            ),
            key=lambda record: (record.year, record.month),
        )
        for record in pending_reports:
            await self._async_send_record(record)
        self.state.ensure_month(now, self.tariff, self.currency)
        await self._async_save_and_publish()

    async def _async_send_record(self, record: MonthRecord, *, resend: bool = False) -> bool:
        if not resend and record.notification_sent_at is not None:
            return True
        previous = self.state.months.get(self._previous_key(record))
        annual = sum(
            item.total_kwh for item in self.state.months.values() if item.year == record.year
        )
        rendered = render_monthly_report(
            self.name,
            record,
            previous,
            annual,
            self.hass.config.language,
        )
        now = dt_util.now().isoformat()
        if not resend:
            # Persist the attempt before the external call. This favors avoiding
            # duplicate monthly messages after a crash; manual resend remains available.
            record.notification_sent_at = now
            await self._async_save()
        success = await self.async_send_notification(rendered)
        if success:
            self.state.last_notification_at = now
            self.state.last_notification_error = None
        if not resend:
            self.hass.bus.async_fire(
                EVENT_REPORT_GENERATED,
                {
                    "entry_id": self.entry.entry_id,
                    "title": rendered.title,
                    "message": rendered.message,
                },
            )
        await self._async_save_and_publish()
        return success

    async def async_send_notification(
        self,
        rendered: RenderedReport,
        target_override: str | None = None,
    ) -> bool:
        target = target_override or self.entry.options.get(
            OPT_NOTIFICATION_TARGET, self.entry.data.get(CONF_NOTIFICATION_TARGET)
        )
        try:
            if target:
                if not self.hass.services.has_service("notify", "send_message"):
                    raise ValueError("notify_send_message_not_found")
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {
                        "entity_id": target,
                        "title": rendered.title,
                        "message": rendered.message,
                    },
                    blocking=True,
                )
            else:
                # Compatibility path for config entries created before version 2.
                service_ref = self.entry.options.get(
                    OPT_NOTIFICATION_SERVICE,
                    self.entry.data.get(CONF_NOTIFICATION_SERVICE),
                )
                if not service_ref:
                    raise ValueError("notification_target_not_configured")
                domain, service = service_ref.split(".", 1)
                if not self.hass.services.has_service(domain, service):
                    raise ValueError("notification_service_not_found")
                await self.hass.services.async_call(
                    domain,
                    service,
                    {"title": rendered.title, "message": rendered.message},
                    blocking=True,
                )
            return True
        except Exception as err:  # Home Assistant service failures vary by provider.
            _LOGGER.warning("Energy Report notification failed: %s", err)
            self.state.last_notification_error = str(err)
            persistent_notification.async_create(
                self.hass,
                rendered.message,
                title=rendered.title,
                notification_id=f"energy_report_{self.entry.entry_id}",
            )
            return False

    async def async_send_test_notification(self, target: str | None = None) -> bool:
        from .report import render_test_report

        return await self.async_send_notification(
            render_test_report(self.name, self.hass.config.language),
            target_override=target,
        )

    async def async_resend_last_report(self) -> bool:
        report_key = self.state.latest_closed_month_key
        if report_key is None:
            return False
        record = self.state.months.get(report_key)
        return False if record is None else await self._async_send_record(record, resend=True)

    async def async_set_tariff(self, value: float) -> None:
        self.state.set_tariff(dt_util.now(), value, self.currency)
        await self._async_save_and_publish()

    async def async_preview_import(self, filename: str) -> ImportPreview:
        preview = await self.hass.async_add_executor_job(
            self.archive.preview_import,
            filename,
            self.state,
        )
        return self._finalize_import_preview(preview)

    async def async_preview_import_path(self, path: str | Path) -> ImportPreview:
        preview = await self.hass.async_add_executor_job(
            self.archive.preview_import_path,
            Path(path),
            self.state,
        )
        return self._finalize_import_preview(preview)

    async def async_preview_uploaded_file(self, uploaded_file_id: str) -> ImportPreview:
        """Consume a Home Assistant upload and return a validated preview."""
        def _preview_upload() -> ImportPreview:
            with process_uploaded_file(self.hass, uploaded_file_id) as file_path:
                return self.archive.preview_import_path(file_path, self.state)

        preview = await self.hass.async_add_executor_job(_preview_upload)
        return self._finalize_import_preview(preview)

    def _finalize_import_preview(self, preview: ImportPreview) -> ImportPreview:
        """Validate the open period and prove whether a current merge is safe."""
        open_records = [record for record in preview.records if record.status == "open"]
        if open_records:
            record = open_records[0]
            now = dt_util.now()
            if (record.year, record.month) != (now.year, now.month):
                from .archive import ArchiveError

                raise ArchiveError("open_month_must_be_current")
        return self.archive.prepare_current_merge(preview, self.entry.created_at)

    async def async_apply_import(
        self,
        preview: ImportPreview,
        current_month_strategy: str = "keep_native",
    ) -> None:
        years = self.archive.apply_import(
            preview,
            self.state,
            current_month_strategy,
            dt_util.now().isoformat(),
        )
        await self._async_save()
        for year in years:
            await self.hass.async_add_executor_job(self.archive.write_year, self.state, year)
        self._sync_anomaly_issue()
        self._publish()

    def pending_anomaly_reviews(self) -> list[dict[str, Any]]:
        """Return detailed events and honest legacy aggregates awaiting review."""
        pending: list[dict[str, Any]] = []
        for event in self.state.anomaly_events:
            if event.review_status != "pending":
                continue
            pending.append(
                {
                    "target": f"event:{event.event_id}",
                    "month_key": event.month_key,
                    "detected_at": event.detected_at,
                    "source": event.source_entity or event.source_type,
                    "previous_value_kwh": event.previous_value_kwh,
                    "new_value_kwh": event.new_value_kwh,
                    "interval_minutes": event.elapsed_seconds / 60,
                    "excluded_kwh": event.excluded_kwh,
                    "plausible_limit_kwh": event.plausible_limit_kwh,
                    "reason": event.reason,
                    "impact_cost": event.impact_cost,
                    "currency": event.currency,
                    "details_available": True,
                }
            )
        for key in sorted(self.state.months, reverse=True):
            amount = self.state.legacy_unresolved_kwh(key)
            if amount <= 0.000001:
                continue
            record = self.state.months[key]
            pending.append(
                {
                    "target": f"legacy:{key}",
                    "month_key": key,
                    "detected_at": "not available",
                    "source": "historical aggregate",
                    "previous_value_kwh": None,
                    "new_value_kwh": None,
                    "interval_minutes": None,
                    "excluded_kwh": amount,
                    "plausible_limit_kwh": None,
                    "reason": "legacy_exclusion_without_event_details",
                    "impact_cost": amount * record.tariff_per_kwh,
                    "currency": record.currency,
                    "details_available": False,
                }
            )
        return pending

    async def async_review_anomaly(self, target: str, decision: str) -> None:
        """Persist one anomaly decision and refresh its annual archive."""
        key = self.state.review_anomaly(target, decision, dt_util.now())
        if (
            self.state.pending_anomaly_count == 0
            and self.state.last_error == "implausible_energy_jump"
        ):
            self.state.last_error = None
        await self._async_save()
        await self.hass.async_add_executor_job(
            self.archive.write_year,
            self.state,
            int(key[:4]),
        )
        self._sync_anomaly_issue()
        self._publish()

    async def async_export_year(self, year: int) -> Path:
        """Generate an import-compatible annual backup for this entry."""
        return await self.hass.async_add_executor_job(
            self.archive.write_export,
            self.state,
            year,
            dt_util.now().isoformat(),
        )

    async def _async_save_and_publish(self) -> None:
        await self._async_save()
        self._sync_anomaly_issue()
        self._publish()

    def _sync_anomaly_issue(self) -> None:
        """Create, update or clear the native repair for this config entry."""
        issue_id = f"{ANOMALY_ISSUE_PREFIX}{self.entry.entry_id}"
        pending = self.pending_anomaly_reviews()
        if not pending:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        item = pending[0]
        placeholders = {
            "instance": self.name,
            "month": item["month_key"],
            "excluded": f"{item['excluded_kwh']:.6f}",
            "cost": f"{item['impact_cost']:.2f}",
            "currency": item["currency"],
            "pending_count": str(len(pending)),
        }
        if item["details_available"]:
            placeholders.update(
                {
                    "detected_at": str(item["detected_at"]),
                    "source": str(item["source"]),
                    "previous": f"{item['previous_value_kwh']:.6f}",
                    "new": f"{item['new_value_kwh']:.6f}",
                    "interval": f"{item['interval_minutes']:.2f}",
                    "limit": f"{item['plausible_limit_kwh']:.6f}",
                }
            )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            config_entry_id=self.entry.entry_id,
            data={"entry_id": self.entry.entry_id, "target": item["target"]},
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=(
                "consumption_anomaly"
                if item["details_available"]
                else "legacy_consumption_anomaly"
            ),
            translation_placeholders=placeholders,
        )

    async def _async_save(self) -> None:
        await self.store.async_save(self.state.to_dict())

    def async_add_update_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._update_listeners.append(listener)

        def remove() -> None:
            if listener in self._update_listeners:
                self._update_listeners.remove(listener)

        return remove

    @callback
    def _publish(self) -> None:
        if self._shutdown:
            return
        for listener in tuple(self._update_listeners):
            listener()

    @staticmethod
    def _previous_key(record: MonthRecord) -> str:
        first = datetime.fromisoformat(record.period_start)
        return month_key(first - timedelta(seconds=1))
