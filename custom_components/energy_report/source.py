"""Source normalization and accounting decisions for Energy Report."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from .const import AUTO_ACCEPT_MONTHLY_EVENT_LIMIT, AUTO_ACCEPT_MONTHLY_LIMIT_KWH
from .models import AnomalyEvent, LedgerState, month_key


@dataclass(frozen=True)
class EnergyDecision:
    """Result of processing a cumulative reading."""

    status: str
    delta_kwh: float = 0.0
    anomaly_id: str | None = None


def process_energy_reading(
    state: LedgerState,
    value_kwh: float,
    now: datetime,
    max_power_kw: float,
    tariff: float,
    currency: str,
    source_entity: str | None = None,
    auto_accept_tolerance_kwh: float = 0.0,
) -> EnergyDecision:
    """Process a cumulative reading without silently accepting anomalies."""
    previous = state.last_energy_kwh
    previous_at = datetime.fromisoformat(state.last_energy_at) if state.last_energy_at else None
    state.last_energy_kwh = value_kwh
    state.last_energy_at = now.isoformat()

    if previous is None or previous_at is None or state.energy_gap_active:
        state.energy_gap_active = False
        return EnergyDecision("baseline")

    delta = value_kwh - previous
    if delta < 0:
        state.reset_count += 1
        return EnergyDecision("reset")
    if delta == 0:
        return EnergyDecision("unchanged")

    elapsed_hours = max(0.0, (now - previous_at).total_seconds() / 3600)
    plausible = max_power_kw * elapsed_hours * 1.20 + 0.01
    if delta > plausible:
        record = state.ensure_month(now, tariff, currency)
        key = month_key(now)
        auto_events = [
            event
            for event in state.anomaly_events
            if event.month_key == key
            and event.review_status == "auto_accepted_tolerance"
        ]
        auto_kwh = sum(event.excluded_kwh for event in auto_events)
        auto_accept = (
            auto_accept_tolerance_kwh > 0
            and delta <= auto_accept_tolerance_kwh + 1e-9
            and len(auto_events) < AUTO_ACCEPT_MONTHLY_EVENT_LIMIT
            and auto_kwh + delta <= AUTO_ACCEPT_MONTHLY_LIMIT_KWH + 1e-9
        )
        record.excluded_kwh += delta
        if auto_accept:
            record.reviewed_excluded_kwh += delta
            state.add_energy_delta(previous_at, now, delta, tariff, currency)
        event_id = uuid4().hex
        state.anomaly_events.append(
            AnomalyEvent(
                event_id=event_id,
                detected_at=now.isoformat(),
                month_key=key,
                source_type="cumulative_energy",
                source_entity=source_entity,
                previous_value_kwh=previous,
                new_value_kwh=value_kwh,
                previous_at=previous_at.isoformat(),
                current_at=now.isoformat(),
                elapsed_seconds=max(0.0, (now - previous_at).total_seconds()),
                excluded_kwh=delta,
                plausible_limit_kwh=plausible,
                reason=(
                    "implausible_energy_jump_below_tolerance"
                    if auto_accept
                    else "implausible_energy_jump"
                ),
                tariff_per_kwh=tariff,
                currency=currency,
                review_status=(
                    "auto_accepted_tolerance" if auto_accept else "pending"
                ),
                reviewed_at=now.isoformat() if auto_accept else None,
            )
        )
        state.anomaly_count += 1
        if auto_accept:
            return EnergyDecision("auto_accepted", delta, event_id)
        state.last_error = "implausible_energy_jump"
        return EnergyDecision("excluded", delta, event_id)

    state.add_energy_delta(previous_at, now, delta, tariff, currency)
    return EnergyDecision("accepted", delta)


def process_power_reading(
    state: LedgerState,
    value_kw: float,
    now: datetime,
    tariff: float,
    currency: str,
    use_for_accounting: bool,
) -> float:
    """Integrate power using the trapezoidal rule."""
    previous = state.last_power_kw
    previous_at = datetime.fromisoformat(state.last_power_at) if state.last_power_at else None
    state.last_power_kw = value_kw
    state.last_power_at = now.isoformat()
    if previous is None or previous_at is None or now <= previous_at:
        return 0.0
    hours = (now - previous_at).total_seconds() / 3600
    delta = (previous + value_kw) / 2 * hours
    state.add_energy_delta(
        previous_at,
        now,
        delta,
        tariff,
        currency,
        reconstructed=use_for_accounting,
        shadow=not use_for_accounting,
    )
    return delta

