"""Monthly report rendering for Energy Report."""

from __future__ import annotations

from dataclasses import dataclass

from .models import MonthRecord


@dataclass(frozen=True)
class RenderedReport:
    title: str
    message: str


def render_monthly_report(
    name: str,
    record: MonthRecord,
    previous: MonthRecord | None,
    annual_kwh: float,
    language: str = "en",
) -> RenderedReport:
    """Render portable plain text with Unicode icons."""
    italian = language.lower().startswith("it")
    month_name = f"{record.month:02d}/{record.year}"
    labels = (
        {
            "consumption": "Consumo",
            "previous": "Mese precedente",
            "annual": "Totale annuale",
            "coverage": "Copertura dati",
            "reconstructed": "Ricostruita da potenza",
            "tariff": "Tariffa",
            "cost": "Costo totale",
            "warning": "Da verificare",
            "gap": "lacuna",
            "excluded": "incrementi esclusi",
            "coverage_warning": "copertura incompleta",
        }
        if italian
        else {
            "consumption": "Consumption",
            "previous": "Previous month",
            "annual": "Annual total",
            "coverage": "Data coverage",
            "reconstructed": "Reconstructed from power",
            "tariff": "Tariff",
            "cost": "Total cost",
            "warning": "Check required",
            "gap": "gap",
            "excluded": "excluded increments",
            "coverage_warning": "incomplete coverage",
        }
    )
    lines = [
        f"⚡ ENERGY REPORT · {name}",
        f"📅 {month_name}",
        f"📊 {labels['consumption']}: {record.total_kwh:.2f} kWh",
    ]
    if previous is not None:
        difference = record.total_kwh - previous.total_kwh
        percentage = None if previous.total_kwh == 0 else difference / previous.total_kwh * 100
        comparison = f"{difference:+.2f} kWh"
        if percentage is not None:
            comparison += f" · {percentage:+.1f}%"
        lines.append(f"↔️ {labels['previous']}: {comparison}")
    lines.append(f"📈 {labels['annual']}: {annual_kwh:.2f} kWh")
    lines.append(f"✅ {labels['coverage']}: {record.coverage_percent:.1f}%")
    if record.reconstructed_kwh > 0:
        lines.append(f"🔄 {labels['reconstructed']}: {record.reconstructed_kwh:.2f} kWh")
    lines.extend(
        [
            f"💶 {labels['tariff']}: {record.tariff_per_kwh:.4f} {record.currency}/kWh",
            f"💰 {labels['cost']}: {record.cost:.2f} {record.currency}",
        ]
    )
    warnings: list[str] = []
    if record.unknown_seconds > 0:
        warnings.append(f"{labels['gap']}: {record.unknown_seconds / 60:.0f} min")
    if record.excluded_kwh > 0:
        warnings.append(f"{labels['excluded']}: {record.excluded_kwh:.2f} kWh")
    if record.coverage_percent < 99.5 and record.unknown_seconds == 0:
        warnings.append(
            f"{labels['coverage_warning']}: {record.coverage_percent:.1f}%"
        )
    if warnings:
        lines.append(f"⚠️ {labels['warning']}: " + "; ".join(warnings))
    return RenderedReport(
        title=f"Energy Report · {name} · {month_name}",
        message="\n".join(lines),
    )


def render_test_report(name: str, language: str = "en") -> RenderedReport:
    """Render a clearly non-accounting test message."""
    message = (
        "✅ Energy Report è configurato correttamente. Questa è una notifica di prova senza dati di consumo reali."
        if language.lower().startswith("it")
        else "✅ Energy Report is configured correctly. This is a test notification with no real consumption data."
    )
    return RenderedReport(title=f"Energy Report · {name}", message=message)
