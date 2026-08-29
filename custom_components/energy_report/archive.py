"""CSV archive and history import for Energy Report."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .const import ARCHIVE_FIELDS, CSV_SCHEMA_VERSION
from .models import LedgerState, MonthRecord


@dataclass(frozen=True)
class ImportPreview:
    """Validated history import awaiting confirmation."""

    path: Path
    records: tuple[MonthRecord, ...]
    closed_count: int
    open_count: int


class ArchiveError(ValueError):
    """Raised when an archive cannot be validated."""


class CsvArchive:
    """Write annual archives and validate portable history imports."""

    def __init__(self, config_dir: str, instance_id: str) -> None:
        self.root = Path(config_dir) / "energy_report"
        self.instance_dir = self.root / instance_id
        self.import_dir = self.root / "import"

    def write_year(self, state: LedgerState, year: int) -> Path:
        """Atomically rewrite one annual archive from authoritative state."""
        self.instance_dir.mkdir(parents=True, exist_ok=True)
        target = self.instance_dir / f"energy-report-{year}.csv"
        records = sorted(
            (
                record
                for record in state.months.values()
                if record.year == year and record.status == "closed"
            ),
            key=lambda record: record.month,
        )
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=self.instance_dir,
            prefix=f".{target.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=ARCHIVE_FIELDS)
            writer.writeheader()
            for record in records:
                writer.writerow(self._row(record))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return target

    def preview_import(self, filename: str, state: LedgerState) -> ImportPreview:
        """Validate a file from the fixed import directory without changing state."""
        self.import_dir.mkdir(parents=True, exist_ok=True)
        candidate = (self.import_dir / filename).resolve()
        if candidate.parent != self.import_dir.resolve() or candidate.suffix.lower() != ".csv":
            raise ArchiveError("invalid_import_path")
        if not candidate.is_file():
            raise ArchiveError("import_file_not_found")

        records: list[MonthRecord] = []
        seen: set[str] = set()
        with candidate.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != ARCHIVE_FIELDS:
                raise ArchiveError("invalid_headers")
            for line_number, row in enumerate(reader, start=2):
                record = self._parse_row(row, line_number)
                key = f"{record.year:04d}-{record.month:02d}"
                existing = state.months.get(key)
                replaceable_open = bool(
                    existing
                    and existing.status == "open"
                    and record.status == "open"
                    and existing.total_kwh == 0
                    and existing.excluded_kwh == 0
                )
                if key in seen or (existing is not None and not replaceable_open):
                    raise ArchiveError(f"month_conflict:{key}")
                seen.add(key)
                records.append(record)

        if not records:
            raise ArchiveError("empty_import")
        open_records = [record for record in records if record.status == "open"]
        if len(open_records) > 1:
            raise ArchiveError("multiple_open_months")
        return ImportPreview(
            path=candidate,
            records=tuple(records),
            closed_count=len(records) - len(open_records),
            open_count=len(open_records),
        )

    @staticmethod
    def apply_import(preview: ImportPreview, state: LedgerState) -> set[int]:
        """Apply an already validated preview atomically in memory."""
        additions = {
            f"{record.year:04d}-{record.month:02d}": record
            for record in preview.records
        }
        for key, incoming in additions.items():
            existing = state.months.get(key)
            if existing is None:
                continue
            if not (
                existing.status == "open"
                and incoming.status == "open"
                and existing.total_kwh == 0
                and existing.excluded_kwh == 0
            ):
                raise ArchiveError("import_changed_since_preview")
        state.months.update(additions)
        return {record.year for record in preview.records if record.status == "closed"}

    @staticmethod
    def _row(record: MonthRecord) -> dict[str, Any]:
        return {
            "schema_version": CSV_SCHEMA_VERSION,
            "record_status": record.status,
            "year": record.year,
            "month": record.month,
            "period_start": record.period_start,
            "period_end": record.period_end,
            "measured_kwh": f"{record.measured_kwh:.6f}",
            "reconstructed_kwh": f"{record.reconstructed_kwh:.6f}",
            "total_kwh": f"{record.total_kwh:.6f}",
            "coverage_percent": f"{record.coverage_percent:.3f}",
            "unknown_duration_minutes": f"{record.unknown_seconds / 60:.3f}",
            "excluded_kwh": f"{record.excluded_kwh:.6f}",
            "tariff_per_kwh": f"{record.tariff_per_kwh:.6f}",
            "currency": record.currency,
            "total_cost": f"{record.cost:.2f}",
            "data_quality": record.data_quality,
            "origin": record.origin,
            "closed_at": record.closed_at or "",
        }

    @staticmethod
    def _parse_row(row: dict[str, str], line_number: int) -> MonthRecord:
        try:
            if int(row["schema_version"]) != CSV_SCHEMA_VERSION:
                raise ArchiveError("unsupported_schema")
            status = row["record_status"]
            if status not in {"closed", "open"}:
                raise ArchiveError("invalid_record_status")
            year = int(row["year"])
            month = int(row["month"])
            if not 1 <= month <= 12:
                raise ArchiveError("invalid_month")
            measured = float(row["measured_kwh"])
            reconstructed = float(row["reconstructed_kwh"])
            total = float(row["total_kwh"])
            unknown = float(row["unknown_duration_minutes"])
            excluded = float(row["excluded_kwh"])
            tariff = float(row["tariff_per_kwh"])
            coverage = float(row["coverage_percent"])
            if min(measured, reconstructed, total, unknown, excluded, tariff, coverage) < 0:
                raise ArchiveError("negative_value")
            if abs(total - measured - reconstructed) > 0.001:
                raise ArchiveError("inconsistent_total")
            if coverage > 100:
                raise ArchiveError("invalid_coverage")
            closed_at = row["closed_at"] or None
            if status == "closed" and closed_at is None:
                raise ArchiveError("closed_at_required")
            period_start = row["period_start"]
            period_end = row["period_end"]
            record = MonthRecord(
                year=year,
                month=month,
                period_start=period_start,
                period_end=period_end,
                status=status,
                measured_kwh=measured,
                reconstructed_kwh=reconstructed,
                covered_seconds=coverage / 100 * max(
                    0.0,
                    (datetime.fromisoformat(period_end)
                     - datetime.fromisoformat(period_start)).total_seconds(),
                ),
                unknown_seconds=unknown * 60,
                excluded_kwh=excluded,
                tariff_per_kwh=tariff,
                currency=row["currency"],
                origin="imported",
                closed_at=closed_at,
            )
            expected_cost = float(row["total_cost"])
            if abs(record.cost - expected_cost) > 0.02:
                raise ArchiveError("inconsistent_cost")
            return record
        except ArchiveError:
            raise
        except (KeyError, TypeError, ValueError) as err:
            raise ArchiveError(f"invalid_row:{line_number}") from err
