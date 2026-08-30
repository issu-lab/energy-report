from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from _load_pure import archive, models, report


UTC = timezone.utc


class ArchiveAndReportTests(unittest.TestCase):
    def _closed_record(self):
        record = models.new_month(datetime(2026, 7, 15, tzinfo=UTC), 0.28, "EUR")
        record.measured_kwh = 182.45
        record.reconstructed_kwh = 1.2
        record.covered_seconds = record.period_seconds
        record.status = "closed"
        record.closed_at = "2026-08-01T08:00:00+00:00"
        return record

    def test_archive_round_trip_and_identical_month_is_ignored(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            state = models.LedgerState(months={"2026-07": self._closed_record()})
            target = writer.write_year(state, 2026)
            writer.import_dir.mkdir(parents=True)
            import_path = writer.import_dir / "history.csv"
            import_path.write_bytes(target.read_bytes())
            preview = writer.preview_import("history.csv", models.LedgerState())
            self.assertEqual(preview.closed_count, 1)
            imported = models.LedgerState()
            years = writer.apply_import(preview, imported)
            self.assertEqual(years, {2026})
            self.assertAlmostEqual(imported.months["2026-07"].total_kwh, 183.65)
            duplicate = writer.preview_import("history.csv", imported)
            self.assertEqual(duplicate.identical_count, 1)
            self.assertEqual(duplicate.new_count, 0)

    def test_import_path_cannot_escape_fixed_directory(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            with self.assertRaises(archive.ArchiveError):
                writer.preview_import("../secret.csv", models.LedgerState())

    def test_open_current_month_can_replace_empty_runtime_placeholder(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            imported = models.new_month(datetime(2026, 8, 15, tzinfo=UTC), 0.28, "EUR")
            imported.measured_kwh = 143.8
            imported.snapshot_at = "2026-08-15T12:00:00+00:00"
            writer.instance_dir.mkdir(parents=True)
            # The generated archive intentionally omits open rows, so write the
            # documented row through the same serializer for import testing.
            writer.import_dir.mkdir(parents=True)
            path = writer.import_dir / "open.csv"
            import csv
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv_writer = csv.DictWriter(handle, fieldnames=archive.ARCHIVE_FIELDS)
                csv_writer.writeheader()
                csv_writer.writerow(writer._row(imported))
            runtime = models.LedgerState(
                months={"2026-08": models.new_month(datetime(2026, 8, 20, tzinfo=UTC), 0.28, "EUR")}
            )
            preview = writer.preview_import("open.csv", runtime)
            writer.apply_import(preview, runtime, "replace_with_csv")
            self.assertEqual(runtime.months["2026-08"].total_kwh, 143.8)

    def test_open_current_month_requires_explicit_replacement_and_keeps_backup(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            incoming = models.new_month(datetime(2026, 8, 15, tzinfo=UTC), 0.28, "EUR")
            incoming.measured_kwh = 143.8
            incoming.snapshot_at = "2026-08-15T12:00:00+00:00"
            writer.import_dir.mkdir(parents=True)
            import csv
            path = writer.import_dir / "open.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv_writer = csv.DictWriter(handle, fieldnames=archive.ARCHIVE_FIELDS)
                csv_writer.writeheader()
                csv_writer.writerow(writer._row(incoming))
            native = models.new_month(datetime(2026, 8, 20, tzinfo=UTC), 0.28, "EUR")
            native.measured_kwh = 12.5
            runtime = models.LedgerState(
                months={"2026-08": native},
                last_energy_kwh=900.0,
                last_energy_at="2026-08-20T10:00:00+00:00",
            )
            preview = writer.preview_import("open.csv", runtime)
            self.assertEqual(preview.current_conflict_count, 1)
            writer.apply_import(preview, runtime, "keep_native", "2026-08-20T12:00:00+00:00")
            self.assertEqual(runtime.months["2026-08"].total_kwh, 12.5)
            writer.apply_import(preview, runtime, "replace_with_csv", "2026-08-20T12:01:00+00:00")
            self.assertEqual(runtime.months["2026-08"].total_kwh, 143.8)
            self.assertEqual(len(runtime.import_backups), 1)
            self.assertIsNone(runtime.last_energy_kwh)

    def test_safe_current_month_merge_adds_native_delta_and_keeps_baseline(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            incoming = models.new_month(datetime(2026, 8, 15, tzinfo=UTC), 0.24, "EUR")
            incoming.measured_kwh = 143.8
            incoming.covered_seconds = 14 * 86400
            incoming.snapshot_at = "2026-08-15T12:00:00+00:00"
            native = models.new_month(datetime(2026, 8, 20, tzinfo=UTC), 0.28, "EUR")
            native.measured_kwh = 12.5
            native.reconstructed_kwh = 0.5
            native.covered_seconds = 4 * 86400
            runtime = models.LedgerState(
                months={"2026-08": native},
                last_energy_kwh=900.0,
                last_energy_at="2026-08-20T10:00:00+00:00",
            )
            preview = archive.ImportPreview(
                path=writer.import_dir / "open.csv",
                records=(incoming,),
                closed_count=0,
                open_count=1,
                new_count=0,
                identical_count=0,
                current_conflict_count=1,
                current_merge_safe=True,
                native_started_at="2026-08-16T10:00:00+00:00",
            )
            writer.apply_import(
                preview,
                runtime,
                "merge_non_overlapping",
                "2026-08-20T12:00:00+00:00",
            )
            merged = runtime.months["2026-08"]
            self.assertAlmostEqual(merged.total_kwh, 156.8)
            self.assertEqual(merged.tariff_per_kwh, 0.28)
            self.assertEqual(merged.origin, "imported_merged")
            self.assertEqual(runtime.last_energy_kwh, 900.0)
            self.assertEqual(len(runtime.import_backups), 1)
            writer.apply_import(
                preview,
                runtime,
                "merge_non_overlapping",
                "2026-08-20T12:05:00+00:00",
            )
            self.assertAlmostEqual(runtime.months["2026-08"].total_kwh, 156.8)
            self.assertEqual(len(runtime.import_backups), 1)

    def test_current_month_merge_is_rejected_without_overlap_proof(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            incoming = models.new_month(datetime(2026, 8, 15, tzinfo=UTC), 0.24, "EUR")
            incoming.snapshot_at = "2026-08-15T12:00:00+00:00"
            native = models.new_month(datetime(2026, 8, 20, tzinfo=UTC), 0.24, "EUR")
            preview = archive.ImportPreview(
                path=writer.import_dir / "open.csv",
                records=(incoming,),
                closed_count=0,
                open_count=1,
                new_count=0,
                identical_count=0,
                current_conflict_count=1,
            )
            with self.assertRaisesRegex(archive.ArchiveError, "merge_not_safe"):
                writer.apply_import(
                    preview,
                    models.LedgerState(months={"2026-08": native}),
                    "merge_non_overlapping",
                )

    def test_merge_preview_requires_snapshot_before_native_start(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            incoming = models.new_month(datetime(2026, 8, 15, tzinfo=UTC), 0.24, "EUR")
            incoming.snapshot_at = "2026-08-15T12:00:00+00:00"
            preview = archive.ImportPreview(
                path=writer.import_dir / "open.csv",
                records=(incoming,),
                closed_count=0,
                open_count=1,
                new_count=0,
                identical_count=0,
                current_conflict_count=1,
            )
            unsafe = writer.prepare_current_merge(
                preview, datetime(2026, 8, 15, 11, 59, tzinfo=UTC)
            )
            safe = writer.prepare_current_merge(
                preview, datetime(2026, 8, 15, 12, 1, tzinfo=UTC)
            )
            self.assertFalse(unsafe.current_merge_safe)
            self.assertTrue(safe.current_merge_safe)

    def test_conflicting_closed_month_is_rejected(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            state = models.LedgerState(months={"2026-07": self._closed_record()})
            changed = self._closed_record()
            changed.measured_kwh += 1
            writer.instance_dir.mkdir(parents=True)
            target = writer.write_year(models.LedgerState(months={"2026-07": changed}), 2026)
            writer.import_dir.mkdir(parents=True)
            (writer.import_dir / "changed.csv").write_bytes(target.read_bytes())
            with self.assertRaisesRegex(archive.ArchiveError, "closed_month_conflict"):
                writer.preview_import("changed.csv", state)

    def test_schema_version_one_remains_importable(self):
        with TemporaryDirectory() as temporary:
            writer = archive.CsvArchive(temporary, "casa")
            record = self._closed_record()
            row = writer._row(record)
            row["schema_version"] = 1
            row.pop("snapshot_at")
            writer.import_dir.mkdir(parents=True)
            import csv
            path = writer.import_dir / "legacy.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv_writer = csv.DictWriter(handle, fieldnames=archive.ARCHIVE_FIELDS_V1)
                csv_writer.writeheader()
                csv_writer.writerow(row)
            preview = writer.preview_import("legacy.csv", models.LedgerState())
            self.assertEqual(preview.new_count, 1)

    def test_report_is_compact_and_warnings_follow_cost(self):
        record = self._closed_record()
        record.unknown_seconds = 600
        rendered = report.render_monthly_report("Casa", record, None, 500, "it")
        self.assertIn("⚡ ENERGY REPORT · Casa", rendered.message)
        self.assertIn("🔄 Ricostruita da potenza", rendered.message)
        self.assertLess(rendered.message.index("💰 Costo totale"), rendered.message.index("⚠️ Da verificare"))


if __name__ == "__main__":
    unittest.main()
