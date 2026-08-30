"""CSV archive and history import for Energy Report."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .const import (
    ARCHIVE_FIELDS,
    ARCHIVE_FIELDS_V1,
    CSV_SCHEMA_VERSION,
    SUPPORTED_CSV_SCHEMA_VERSIONS,
)
from .models import LedgerState, MonthRecord


@dataclass(frozen=True)
class ImportPreview:
    """Validated history import awaiting confirmation."""

    path: Path
    records: tuple[MonthRecord, ...]
    closed_count: int
    open_count: int
    new_count: int
    identical_count: int
    current_conflict_count: int
    current_merge_safe: bool = False
    native_started_at: str | None = None


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

        return self.preview_import_path(candidate, state)

    def preview_import_path(self, candidate: Path, state: LedgerState) -> ImportPreview:
        """Validate an uploaded CSV path without changing state."""
        candidate = Path(candidate)
        if candidate.suffix.lower() != ".csv" or not candidate.is_file():
            raise ArchiveError("import_file_not_found")
        records: list[MonthRecord] = []
        seen: set[str] = set()
        new_count = 0
        identical_count = 0
        current_conflict_count = 0
        with candidate.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = tuple(reader.fieldnames or ())
            if headers not in {ARCHIVE_FIELDS, ARCHIVE_FIELDS_V1}:
                raise ArchiveError("invalid_headers")
            for line_number, row in enumerate(reader, start=2):
                record = self._parse_row(row, line_number)
                key = f"{record.year:04d}-{record.month:02d}"
                existing = state.months.get(key)
                if key in seen:
                    raise ArchiveError(f"month_conflict:{key}")
                if existing is None:
                    new_count += 1
                elif self._records_equal(existing, record) or self._already_merged(
                    existing, record
                ):
                    identical_count += 1
                elif existing.status == "open" and record.status == "open":
                    current_conflict_count += 1
                else:
                    raise ArchiveError(f"closed_month_conflict:{key}")
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
            new_count=new_count,
            identical_count=identical_count,
            current_conflict_count=current_conflict_count,
        )

    @staticmethod
    def prepare_current_merge(
        preview: ImportPreview,
        native_started_at: datetime,
    ) -> ImportPreview:
        """Mark a preview mergeable only when CSV ends before native accounting."""
        open_records = [record for record in preview.records if record.status == "open"]
        if (
            preview.current_conflict_count != 1
            or len(open_records) != 1
            or not open_records[0].snapshot_at
        ):
            return preview
        snapshot_at = datetime.fromisoformat(open_records[0].snapshot_at)
        if snapshot_at > native_started_at:
            return preview
        return replace(
            preview,
            current_merge_safe=True,
            native_started_at=native_started_at.isoformat(),
        )

    @staticmethod
    def apply_import(
        preview: ImportPreview,
        state: LedgerState,
        current_month_strategy: str = "keep_native",
        imported_at: str | None = None,
    ) -> set[int]:
        """Apply an already validated preview atomically in memory."""
        if current_month_strategy not in {
            "keep_native",
            "merge_non_overlapping",
            "replace_with_csv",
        }:
            raise ArchiveError("invalid_current_month_strategy")
        if current_month_strategy == "merge_non_overlapping" and not (
            preview.current_merge_safe and preview.native_started_at
        ):
            raise ArchiveError("current_month_merge_not_safe")
        if current_month_strategy == "merge_non_overlapping":
            open_records = [record for record in preview.records if record.status == "open"]
            if (
                len(open_records) != 1
                or not open_records[0].snapshot_at
                or datetime.fromisoformat(open_records[0].snapshot_at)
                > datetime.fromisoformat(preview.native_started_at)
            ):
                raise ArchiveError("current_month_overlap_not_excluded")
        for incoming in preview.records:
            key = f"{incoming.year:04d}-{incoming.month:02d}"
            existing = state.months.get(key)
            if (
                existing is not None
                and not CsvArchive._records_equal(existing, incoming)
                and not CsvArchive._already_merged(existing, incoming)
                and not (existing.status == "open" and incoming.status == "open")
            ):
                raise ArchiveError("import_changed_since_preview")
        applied: list[MonthRecord] = []
        for incoming in preview.records:
            key = f"{incoming.year:04d}-{incoming.month:02d}"
            existing = state.months.get(key)
            if existing is None:
                state.months[key] = incoming
                applied.append(incoming)
                continue
            if CsvArchive._records_equal(existing, incoming) or CsvArchive._already_merged(
                existing, incoming
            ):
                continue
            if existing.status != "open" or incoming.status != "open":
                raise ArchiveError("import_changed_since_preview")
            if current_month_strategy == "keep_native":
                continue
            state.import_backups.append(
                {
                    "changed_at": imported_at,
                    "strategy": current_month_strategy,
                    "month_key": key,
                    "record": existing.to_dict(),
                }
            )
            state.import_backups = state.import_backups[-10:]
            if current_month_strategy == "merge_non_overlapping":
                state.months[key] = replace(
                    incoming,
                    measured_kwh=incoming.measured_kwh + existing.measured_kwh,
                    reconstructed_kwh=(
                        incoming.reconstructed_kwh + existing.reconstructed_kwh
                    ),
                    shadow_power_kwh=(
                        incoming.shadow_power_kwh + existing.shadow_power_kwh
                    ),
                    covered_seconds=min(
                        incoming.period_seconds,
                        incoming.covered_seconds + existing.covered_seconds,
                    ),
                    unknown_seconds=(
                        incoming.unknown_seconds + existing.unknown_seconds
                    ),
                    excluded_kwh=incoming.excluded_kwh + existing.excluded_kwh,
                    tariff_per_kwh=existing.tariff_per_kwh,
                    currency=existing.currency,
                    origin="imported_merged",
                    imported_snapshot_measured_kwh=incoming.measured_kwh,
                    imported_snapshot_reconstructed_kwh=incoming.reconstructed_kwh,
                )
            else:
                state.months[key] = incoming
            applied.append(incoming)
            if current_month_strategy == "replace_with_csv":
                state.last_energy_kwh = None
                state.last_energy_at = None
                state.last_power_kw = None
                state.last_power_at = None
                state.energy_gap_active = False
                state.energy_gap_started_at = None
        state.last_import_at = imported_at
        state.last_import_summary = (
            f"applied={len(applied)}, identical={preview.identical_count}, "
            f"current_strategy={current_month_strategy}"
        )
        return {record.year for record in applied if record.status == "closed"}

    @staticmethod
    def _records_equal(left: MonthRecord, right: MonthRecord) -> bool:
        """Compare accounting values while ignoring runtime-only metadata."""
        return (
            left.status == right.status
            and left.year == right.year
            and left.month == right.month
            and left.period_start == right.period_start
            and left.period_end == right.period_end
            and abs(left.measured_kwh - right.measured_kwh) <= 0.001
            and abs(left.reconstructed_kwh - right.reconstructed_kwh) <= 0.001
            and abs(left.covered_seconds - right.covered_seconds) <= 60
            and abs(left.unknown_seconds - right.unknown_seconds) <= 60
            and abs(left.excluded_kwh - right.excluded_kwh) <= 0.001
            and abs(left.tariff_per_kwh - right.tariff_per_kwh) <= 0.000001
            and left.currency == right.currency
        )

    @staticmethod
    def _already_merged(existing: MonthRecord, incoming: MonthRecord) -> bool:
        """Return whether this exact imported snapshot is already in the ledger."""
        return (
            existing.status == "open"
            and incoming.status == "open"
            and existing.origin == "imported_merged"
            and existing.snapshot_at == incoming.snapshot_at
            and existing.imported_snapshot_measured_kwh is not None
            and existing.imported_snapshot_reconstructed_kwh is not None
            and abs(
                existing.imported_snapshot_measured_kwh - incoming.measured_kwh
            )
            <= 0.001
            and abs(
                existing.imported_snapshot_reconstructed_kwh
                - incoming.reconstructed_kwh
            )
            <= 0.001
        )

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
            "snapshot_at": record.snapshot_at or "",
            "closed_at": record.closed_at or "",
        }

    @staticmethod
    def _parse_row(row: dict[str, str], line_number: int) -> MonthRecord:
        try:
            if int(row["schema_version"]) not in SUPPORTED_CSV_SCHEMA_VERSIONS:
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
            snapshot_at = row.get("snapshot_at") or None
            if status == "closed" and closed_at is None:
                raise ArchiveError("closed_at_required")
            if status == "open" and int(row["schema_version"]) >= 2 and snapshot_at is None:
                raise ArchiveError("snapshot_at_required")
            period_start = row["period_start"]
            period_end = row["period_end"]
            period_start_dt = datetime.fromisoformat(period_start)
            period_end_dt = datetime.fromisoformat(period_end)
            if period_start_dt.utcoffset() is None or period_end_dt.utcoffset() is None:
                raise ArchiveError("timezone_required")
            if period_end_dt <= period_start_dt:
                raise ArchiveError("invalid_period")
            if snapshot_at is not None:
                snapshot_dt = datetime.fromisoformat(snapshot_at)
                if snapshot_dt.utcoffset() is None:
                    raise ArchiveError("timezone_required")
                if not period_start_dt <= snapshot_dt <= period_end_dt:
                    raise ArchiveError("invalid_snapshot_at")
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
                    (period_end_dt - period_start_dt).total_seconds(),
                ),
                unknown_seconds=unknown * 60,
                excluded_kwh=excluded,
                tariff_per_kwh=tariff,
                currency=row["currency"],
                origin="imported",
                snapshot_at=snapshot_at,
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
