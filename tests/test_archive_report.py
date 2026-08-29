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

    def test_archive_round_trip_and_conflict_rejection(self):
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
            with self.assertRaises(archive.ArchiveError):
                writer.preview_import("history.csv", imported)

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
            writer.apply_import(preview, runtime)
            self.assertEqual(runtime.months["2026-08"].total_kwh, 143.8)

    def test_report_is_compact_and_warnings_follow_cost(self):
        record = self._closed_record()
        record.unknown_seconds = 600
        rendered = report.render_monthly_report("Casa", record, None, 500, "it")
        self.assertIn("⚡ ENERGY REPORT · Casa", rendered.message)
        self.assertIn("🔄 Ricostruita da potenza", rendered.message)
        self.assertLess(rendered.message.index("💰 Costo totale"), rendered.message.index("⚠️ Da verificare"))


if __name__ == "__main__":
    unittest.main()
