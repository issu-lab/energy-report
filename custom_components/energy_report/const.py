"""Constants for Energy Report."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "energy_report"
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.BUTTON]

CONF_NAME = "name"
CONF_INSTANCE_ID = "instance_id"
CONF_SOURCE_MODE = "source_mode"
CONF_ENERGY_SENSOR = "energy_sensor"
CONF_POWER_SENSOR = "power_sensor"
CONF_TARIFF = "tariff"
CONF_NOTIFICATION_SERVICE = "notification_service"
CONF_NOTIFICATION_TARGET = "notification_target"

MODE_ENERGY = "energy"
MODE_POWER = "power"
MODE_DUAL = "dual"
SOURCE_MODES = (MODE_ENERGY, MODE_POWER, MODE_DUAL)

OPT_MAX_POWER_KW = "max_power_kw"
OPT_SOURCE_TIMEOUT_MINUTES = "source_timeout_minutes"
OPT_REPORT_HOUR = "report_hour"
OPT_NOTIFICATION_SERVICE = CONF_NOTIFICATION_SERVICE
OPT_NOTIFICATION_TARGET = CONF_NOTIFICATION_TARGET
OPT_AUTO_ACCEPT_TOLERANCE_KWH = "auto_accept_tolerance_kwh"

DEFAULT_MAX_POWER_KW = 10.0
DEFAULT_SOURCE_TIMEOUT_MINUTES = 15
DEFAULT_REPORT_HOUR = 8
DEFAULT_TARIFF = 0.24
DEFAULT_AUTO_ACCEPT_TOLERANCE_KWH = 0.05
AUTO_ACCEPT_MONTHLY_LIMIT_KWH = 0.5
AUTO_ACCEPT_MONTHLY_EVENT_LIMIT = 10
DEFAULTS = {
    OPT_MAX_POWER_KW: DEFAULT_MAX_POWER_KW,
    OPT_SOURCE_TIMEOUT_MINUTES: DEFAULT_SOURCE_TIMEOUT_MINUTES,
    OPT_REPORT_HOUR: DEFAULT_REPORT_HOUR,
    OPT_AUTO_ACCEPT_TOLERANCE_KWH: DEFAULT_AUTO_ACCEPT_TOLERANCE_KWH,
}

STORE_VERSION = 1
STORE_KEY_PREFIX = "energy_report"
CSV_SCHEMA_VERSION = 2
SUPPORTED_CSV_SCHEMA_VERSIONS = (1, 2)
ARCHIVE_FIELDS = (
    "schema_version",
    "record_status",
    "year",
    "month",
    "period_start",
    "period_end",
    "measured_kwh",
    "reconstructed_kwh",
    "total_kwh",
    "coverage_percent",
    "unknown_duration_minutes",
    "excluded_kwh",
    "tariff_per_kwh",
    "currency",
    "total_cost",
    "data_quality",
    "origin",
    "snapshot_at",
    "closed_at",
)

ARCHIVE_FIELDS_V1 = tuple(field for field in ARCHIVE_FIELDS if field != "snapshot_at")

EVENT_REPORT_GENERATED = "energy_report_report_generated"
ANOMALY_ISSUE_PREFIX = "consumption_anomaly_"
