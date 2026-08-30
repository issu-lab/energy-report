from datetime import datetime, timedelta, timezone
import unittest

from _load_pure import models, source


UTC = timezone.utc


class AccountingTests(unittest.TestCase):
    def test_units_are_strict_and_normalized(self):
        self.assertEqual(models.energy_to_kwh("1200", "Wh"), 1.2)
        self.assertEqual(models.energy_to_kwh(1.2, "kWh"), 1.2)
        self.assertEqual(models.power_to_kw(850, "W"), 0.85)
        self.assertIsNone(models.energy_to_kwh(-1, "kWh"))
        self.assertIsNone(models.power_to_kw("unknown", "W"))
        self.assertIsNone(models.energy_to_kwh(10, "J"))

    def test_cumulative_reset_preserves_total(self):
        state = models.LedgerState(last_energy_kwh=100, last_energy_at="2026-08-01T10:00:00+00:00")
        accepted = source.process_energy_reading(
            state, 101, datetime(2026, 8, 1, 11, tzinfo=UTC), 10, 0.28, "EUR"
        )
        self.assertEqual(accepted.status, "accepted")
        before = state.months["2026-08"].total_kwh
        reset = source.process_energy_reading(
            state, 0.2, datetime(2026, 8, 1, 12, tzinfo=UTC), 10, 0.28, "EUR"
        )
        self.assertEqual(reset.status, "reset")
        self.assertEqual(state.months["2026-08"].total_kwh, before)
        self.assertEqual(state.reset_count, 1)

    def test_implausible_jump_is_excluded_and_rebased(self):
        state = models.LedgerState(last_energy_kwh=10, last_energy_at="2026-08-01T10:00:00+00:00")
        result = source.process_energy_reading(
            state, 60, datetime(2026, 8, 1, 10, 1, tzinfo=UTC), 10, 0.28, "EUR"
        )
        self.assertEqual(result.status, "excluded")
        self.assertEqual(state.months["2026-08"].excluded_kwh, 50)
        self.assertEqual(state.last_energy_kwh, 60)
        self.assertEqual(state.anomaly_count, 1)

    def test_power_uses_trapezoidal_integration(self):
        state = models.LedgerState(last_power_kw=1, last_power_at="2026-08-01T10:00:00+00:00")
        delta = source.process_power_reading(
            state, 3, datetime(2026, 8, 1, 11, tzinfo=UTC), 0.28, "EUR", True
        )
        self.assertAlmostEqual(delta, 2)
        self.assertAlmostEqual(state.months["2026-08"].reconstructed_kwh, 2)

    def test_interval_is_split_at_month_boundary(self):
        state = models.LedgerState()
        start = datetime(2026, 7, 31, 23, 30, tzinfo=UTC)
        end = datetime(2026, 8, 1, 0, 30, tzinfo=UTC)
        state.add_energy_delta(start, end, 2, 0.28, "EUR")
        self.assertAlmostEqual(state.months["2026-07"].total_kwh, 1)
        self.assertAlmostEqual(state.months["2026-08"].total_kwh, 1)

    def test_closed_month_is_immutable(self):
        state = models.LedgerState()
        july = datetime(2026, 7, 1, tzinfo=UTC)
        state.ensure_month(july, 0.28, "EUR")
        state.close_month("2026-07", datetime(2026, 8, 1, 8, tzinfo=UTC))
        state.add_energy_delta(
            datetime(2026, 7, 31, 23, tzinfo=UTC),
            datetime(2026, 8, 1, 1, tzinfo=UTC),
            2,
            0.28,
            "EUR",
        )
        self.assertEqual(state.months["2026-07"].total_kwh, 0)
        self.assertAlmostEqual(state.months["2026-08"].total_kwh, 1)

    def test_forecast_requires_three_days_and_good_coverage(self):
        now = datetime(2026, 8, 5, tzinfo=UTC)
        record = models.new_month(now, 0.28, "EUR")
        elapsed = (now - datetime.fromisoformat(record.period_start)).total_seconds()
        record.measured_kwh = 40
        record.covered_seconds = elapsed
        energy, cost = models.forecast_month(record, now)
        self.assertIsNotNone(energy)
        self.assertAlmostEqual(cost, energy * 0.28)
        record.covered_seconds = elapsed * 0.5
        self.assertEqual(models.forecast_month(record, now), (None, None))

    def test_closed_month_with_low_coverage_is_incomplete(self):
        record = models.new_month(datetime(2026, 8, 5, tzinfo=UTC), 0.28, "EUR")
        record.reconstructed_kwh = 20
        record.covered_seconds = record.period_seconds * 0.7
        record.status = "closed"
        self.assertEqual(record.data_quality, "incomplete")

    def test_latest_closed_month_includes_imported_history(self):
        state = models.LedgerState(last_report_key=None)
        july = models.new_month(datetime(2026, 7, 1, tzinfo=UTC), 0.28, "EUR")
        july.status = "closed"
        july.origin = "imported"
        august = models.new_month(datetime(2026, 8, 1, tzinfo=UTC), 0.28, "EUR")
        state.months = {"2026-08": august, "2026-07": july}
        self.assertEqual(state.latest_closed_month_key, "2026-07")

    def test_latest_closed_month_prefers_newest_record(self):
        state = models.LedgerState(last_report_key="2026-06")
        for month in (6, 7):
            record = models.new_month(datetime(2026, month, 1, tzinfo=UTC), 0.28, "EUR")
            record.status = "closed"
            state.months[f"2026-{month:02d}"] = record
        self.assertEqual(state.latest_closed_month_key, "2026-07")


if __name__ == "__main__":
    unittest.main()
