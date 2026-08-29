"""Source normalization and accounting decisions for Energy Report."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import LedgerState


@dataclass(frozen=True)
class EnergyDecision:
    """Result of processing a cumulative reading."""

    status: str
    delta_kwh: float = 0.0


def process_energy_reading(
    state: LedgerState,
    value_kwh: float,
    now: datetime,
    max_power_kw: float,
    tariff: float,
    currency: str,
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
        record.excluded_kwh += delta
        state.anomaly_count += 1
        state.last_error = "implausible_energy_jump"
        return EnergyDecision("excluded", delta)

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

