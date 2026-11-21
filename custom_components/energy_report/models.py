"""Dependency-light accounting models for Energy Report."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import asdict, dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any


INVALID_STATES = {None, "", "unknown", "unavailable"}


def finite_non_negative(value: object) -> float | None:
    """Return a finite non-negative number, or None."""
    if value in INVALID_STATES:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number >= 0 else None


def energy_to_kwh(value: object, unit: str | None) -> float | None:
    """Normalize a Home Assistant energy value to kWh."""
    number = finite_non_negative(value)
    if number is None:
        return None
    factors = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}
    factor = factors.get(unit or "")
    return None if factor is None else number * factor


def power_to_kw(value: object, unit: str | None) -> float | None:
    """Normalize a Home Assistant power value to kW."""
    number = finite_non_negative(value)
    if number is None:
        return None
    factors = {"W": 0.001, "kW": 1.0, "MW": 1000.0}
    factor = factors.get(unit or "")
    return None if factor is None else number * factor


def month_key(moment: datetime) -> str:
    """Return a stable YYYY-MM key."""
    return f"{moment.year:04d}-{moment.month:02d}"


@dataclass
class MonthRecord:
    """Accounting record for one calendar month."""

    year: int
    month: int
    period_start: str
    period_end: str
    status: str = "open"
    measured_kwh: float = 0.0
    reconstructed_kwh: float = 0.0
    shadow_power_kwh: float = 0.0
    covered_seconds: float = 0.0
    unknown_seconds: float = 0.0
    excluded_kwh: float = 0.0
    reviewed_excluded_kwh: float = 0.0
    tariff_per_kwh: float = 0.0
    currency: str = "EUR"
    origin: str = "native"
    snapshot_at: str | None = None
    imported_snapshot_measured_kwh: float | None = None
    imported_snapshot_reconstructed_kwh: float | None = None
    closed_at: str | None = None
    notification_sent_at: str | None = None

    @property
    def total_kwh(self) -> float:
        return self.measured_kwh + self.reconstructed_kwh

    @property
    def cost(self) -> float:
        return self.total_kwh * self.tariff_per_kwh

    @property
    def period_seconds(self) -> float:
        start = datetime.fromisoformat(self.period_start)
        end = datetime.fromisoformat(self.period_end)
        return max(0.0, (end - start).total_seconds())

    @property
    def coverage_percent(self) -> float:
        if self.period_seconds <= 0:
            return 0.0
        return min(100.0, 100.0 * self.covered_seconds / self.period_seconds)

    @property
    def data_quality(self) -> str:
        if (
            self.unknown_seconds > 0
            or self.unresolved_excluded_kwh > 0.000001
            or (self.status == "closed" and self.coverage_percent < 99.5)
        ):
            return "incomplete"
        if self.reconstructed_kwh > 0:
            return "reconstructed"
        return "complete"

    @property
    def unresolved_excluded_kwh(self) -> float:
        """Return excluded energy that still needs an explicit review."""
        return max(0.0, self.excluded_kwh - self.reviewed_excluded_kwh)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MonthRecord":
        fields = cls.__dataclass_fields__
        return cls(**{key: value for key, value in raw.items() if key in fields})


@dataclass
class AnomalyEvent:
    """Auditable cumulative-energy anomaly and its review decision."""

    event_id: str
    detected_at: str
    month_key: str
    source_type: str
    source_entity: str | None
    previous_value_kwh: float
    new_value_kwh: float
    previous_at: str
    current_at: str
    elapsed_seconds: float
    excluded_kwh: float
    plausible_limit_kwh: float
    reason: str
    tariff_per_kwh: float
    currency: str
    review_status: str = "pending"
    reviewed_at: str | None = None

    @property
    def impact_cost(self) -> float:
        return self.excluded_kwh * self.tariff_per_kwh

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AnomalyEvent":
        fields = cls.__dataclass_fields__
        return cls(**{key: value for key, value in raw.items() if key in fields})


def new_month(moment: datetime, tariff: float, currency: str) -> MonthRecord:
    """Create an open record for the month containing moment."""
    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days = monthrange(start.year, start.month)[1]
    end = start.replace(day=days, hour=23, minute=59, second=59, microsecond=999999)
    return MonthRecord(
        year=start.year,
        month=start.month,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        tariff_per_kwh=tariff,
        currency=currency,
    )


@dataclass
class LedgerState:
    """Versioned state that survives Home Assistant restarts."""

    schema_version: int = 2
    months: dict[str, MonthRecord] = field(default_factory=dict)
    last_energy_kwh: float | None = None
    last_energy_at: str | None = None
    last_power_kw: float | None = None
    last_power_at: str | None = None
    energy_gap_active: bool = False
    energy_gap_started_at: str | None = None
    source_energy_entity: str | None = None
    source_power_entity: str | None = None
    reset_count: int = 0
    source_change_count: int = 0
    anomaly_count: int = 0
    anomaly_events: list[AnomalyEvent] = field(default_factory=list)
    anomaly_reviews: list[dict[str, Any]] = field(default_factory=list)
    anomaly_review_backups: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None
    last_report_key: str | None = None
    last_notification_at: str | None = None
    last_notification_error: str | None = None
    import_backups: list[dict[str, Any]] = field(default_factory=list)
    last_import_at: str | None = None
    last_import_summary: str | None = None

    def ensure_month(self, moment: datetime, tariff: float, currency: str) -> MonthRecord:
        key = month_key(moment)
        if key not in self.months:
            self.months[key] = new_month(moment, tariff, currency)
        return self.months[key]

    def set_tariff(self, moment: datetime, tariff: float, currency: str) -> None:
        record = self.ensure_month(moment, tariff, currency)
        if record.status == "open":
            record.tariff_per_kwh = tariff
            record.currency = currency

    def add_energy_delta(
        self,
        start: datetime,
        end: datetime,
        delta_kwh: float,
        tariff: float,
        currency: str,
        reconstructed: bool = False,
        shadow: bool = False,
    ) -> None:
        """Distribute an interval across calendar months."""
        seconds = max(0.0, (end - start).total_seconds())
        if seconds <= 0 or delta_kwh < 0:
            return
        cursor = start
        while cursor < end:
            if cursor.month == 12:
                boundary = cursor.replace(
                    year=cursor.year + 1,
                    month=1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                boundary = cursor.replace(
                    month=cursor.month + 1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            segment_end = min(end, boundary)
            segment_seconds = (segment_end - cursor).total_seconds()
            fraction = segment_seconds / seconds
            record = self.ensure_month(cursor, tariff, currency)
            amount = delta_kwh * fraction
            if record.status == "closed":
                cursor = segment_end
                continue
            if shadow:
                record.shadow_power_kwh += amount
            elif reconstructed:
                record.reconstructed_kwh += amount
                record.covered_seconds += segment_seconds
            else:
                record.measured_kwh += amount
                record.covered_seconds += segment_seconds
            cursor = segment_end

    def close_month(self, key: str, closed_at: datetime) -> MonthRecord | None:
        record = self.months.get(key)
        if record is None or record.status == "closed":
            return None
        record.status = "closed"
        record.closed_at = closed_at.isoformat()
        self.last_report_key = key
        return record

    @property
    def pending_anomaly_count(self) -> int:
        """Return detailed and legacy exclusions awaiting review."""
        detailed = sum(event.review_status == "pending" for event in self.anomaly_events)
        detailed_by_month: dict[str, float] = {}
        for event in self.anomaly_events:
            if event.review_status != "pending":
                continue
            detailed_by_month[event.month_key] = (
                detailed_by_month.get(event.month_key, 0.0) + event.excluded_kwh
            )
        legacy = sum(
            max(0.0, record.unresolved_excluded_kwh - detailed_by_month.get(key, 0.0))
            > 0.000001
            for key, record in self.months.items()
        )
        return detailed + legacy

    def legacy_unresolved_kwh(self, key: str) -> float:
        """Return unresolved aggregate not represented by detailed events."""
        record = self.months[key]
        detailed = sum(
            event.excluded_kwh
            for event in self.anomaly_events
            if event.month_key == key and event.review_status == "pending"
        )
        return max(0.0, record.unresolved_excluded_kwh - detailed)

    def review_anomaly(self, target: str, decision: str, reviewed_at: datetime) -> str:
        """Apply one explicit, idempotent anomaly decision and return its month."""
        if decision not in {"accept_increment", "confirm_exclusion"}:
            raise ValueError("invalid_anomaly_decision")
        before = self.to_dict()
        before.pop("anomaly_review_backups", None)

        if target.startswith("event:"):
            event_id = target.removeprefix("event:")
            event = next(
                (item for item in self.anomaly_events if item.event_id == event_id),
                None,
            )
            if event is None:
                raise ValueError("anomaly_not_found")
            if event.review_status != "pending":
                if event.review_status == decision:
                    return event.month_key
                raise ValueError("anomaly_already_reviewed")
            record = self.months[event.month_key]
            if decision == "accept_increment":
                record.measured_kwh += event.excluded_kwh
            record.reviewed_excluded_kwh = min(
                record.excluded_kwh,
                record.reviewed_excluded_kwh + event.excluded_kwh,
            )
            event.review_status = decision
            event.reviewed_at = reviewed_at.isoformat()
            key = event.month_key
        elif target.startswith("legacy:"):
            key = target.removeprefix("legacy:")
            amount = self.legacy_unresolved_kwh(key)
            if amount <= 0.000001:
                return key
            record = self.months[key]
            if decision == "accept_increment":
                record.measured_kwh += amount
            record.reviewed_excluded_kwh = min(
                record.excluded_kwh,
                record.reviewed_excluded_kwh + amount,
            )
        else:
            raise ValueError("anomaly_not_found")

        self.anomaly_review_backups.append(
            {
                "created_at": reviewed_at.isoformat(),
                "target": target,
                "decision": decision,
                "state": before,
            }
        )
        self.anomaly_review_backups = self.anomaly_review_backups[-10:]
        self.anomaly_reviews.append(
            {
                "reviewed_at": reviewed_at.isoformat(),
                "target": target,
                "month_key": key,
                "decision": decision,
                "excluded_kwh": (
                    event.excluded_kwh if target.startswith("event:") else amount
                ),
                "details_available": target.startswith("event:"),
            }
        )
        return key

    @property
    def latest_closed_month_key(self) -> str | None:
        """Return the newest closed month, including imported history."""
        closed_keys = [
            key for key, record in self.months.items() if record.status == "closed"
        ]
        return max(closed_keys, default=None)

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["months"] = {key: value.to_dict() for key, value in self.months.items()}
        raw["anomaly_events"] = [event.to_dict() for event in self.anomaly_events]
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LedgerState":
        fields = cls.__dataclass_fields__
        data = {
            key: value
            for key, value in raw.items()
            if key in fields and key not in {"months", "anomaly_events"}
        }
        state = cls(**data)
        state.schema_version = 2
        state.months = {
            key: MonthRecord.from_dict(value)
            for key, value in raw.get("months", {}).items()
            if isinstance(value, dict)
        }
        state.anomaly_events = [
            AnomalyEvent.from_dict(value)
            for value in raw.get("anomaly_events", [])
            if isinstance(value, dict)
        ]
        return state


def forecast_month(record: MonthRecord, now: datetime) -> tuple[float | None, float | None]:
    """Return a simple coverage-aware month-end energy and cost forecast."""
    if record.status != "open" or now.day <= 3 or record.covered_seconds <= 0:
        return None, None
    elapsed = (now - datetime.fromisoformat(record.period_start)).total_seconds()
    if elapsed <= 0 or record.covered_seconds / elapsed < 0.8:
        return None, None
    projected = record.total_kwh / record.covered_seconds * record.period_seconds
    return projected, projected * record.tariff_per_kwh
