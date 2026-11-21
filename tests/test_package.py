import hashlib
import json
from pathlib import Path
import re
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "energy_report"


def key_shape(value):
    if isinstance(value, dict):
        return {key: key_shape(child) for key, child in value.items()}
    return None


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not PNG: {path}")
    return struct.unpack(">II", data[16:24])


class PackageTests(unittest.TestCase):
    def test_manifest_version_and_hacs_match(self):
        manifest = json.loads((INTEGRATION / "manifest.json").read_text())
        version = (ROOT / "VERSION").read_text().strip()
        hacs = json.loads((ROOT / "hacs.json").read_text())
        self.assertEqual(manifest["domain"], "energy_report")
        self.assertEqual(manifest["version"], version)
        self.assertEqual(manifest["categories"], ["energy"])
        self.assertEqual(manifest["integration_type"], "device")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(hacs["homeassistant"], "2026.11.0")

    def test_translation_shapes_match(self):
        english = json.loads((INTEGRATION / "translations" / "en.json").read_text())
        italian = json.loads((INTEGRATION / "translations" / "it.json").read_text())
        self.assertEqual(key_shape(english), key_shape(italian))

    def test_native_anomaly_repairs_are_packaged(self):
        repairs = (INTEGRATION / "repairs.py").read_text()
        strings = json.loads((INTEGRATION / "strings.json").read_text())
        self.assertIn("async_create_fix_flow", repairs)
        self.assertIn("consumption_anomaly", strings["issues"])
        self.assertIn("legacy_consumption_anomaly", strings["issues"])
        self.assertNotIn("description", strings["issues"]["consumption_anomaly"])
        self.assertIn("fix_flow", strings["issues"]["consumption_anomaly"])
        self.assertEqual(
            strings["entity"]["sensor"]["pending_anomalies"]["name"],
            "Anomalies to review",
        )

    def test_no_site_specific_entities_or_recipients(self):
        source = "\n".join(path.read_text() for path in INTEGRATION.glob("*.py"))
        for forbidden in ("shellyem_244cab", "6358993249", "notify.telegram", "sensor.shelly"):
            self.assertNotIn(forbidden, source)

    def test_readme_calls_product_an_integration(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Native Home Assistant", readme)
        self.assertNotIn("helper integration", readme.lower())
        self.assertIn("examples/history-import.csv", readme)
        self.assertIn("## Project Status", readme)
        self.assertIn("### Home Assistant Integration and Device", readme)
        self.assertIn("## Why It Exists", readme)
        self.assertIn("## Known Limitations", readme)
        self.assertIn(
            '<img src="https://raw.githubusercontent.com/issu-lab/energy-report/main/assets/issu-open-homelab-badge.png"',
            readme,
        )
        self.assertNotIn("energy-report-footer", readme)

    def test_readme_uses_marketplace_safe_images_and_destinations(self):
        readme = (ROOT / "README.md").read_text()
        self.assertTrue(
            readme.startswith(
                "![Energy Report](assets/energy-report-banner-light.png)"
            )
        )
        self.assertIn(
            '<img src="https://raw.githubusercontent.com/issu-lab/energy-report/main/assets/issu-open-homelab-badge.png"',
            readme,
        )
        self.assertIn(
            "](https://github.com/issu-lab/energy-report/blob/main/LICENSE)",
            readme,
        )
        local_html_images = re.findall(r'<img\s+src="assets/[^\"]+"', readme)
        self.assertEqual(local_html_images, [])
        self.assertIn('width="480"', readme)
        self.assertNotIn("<picture>", readme)

    def test_readme_report_example_is_english(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Notification text automatically follows the language", readme)
        self.assertIn("📊 Consumption: 183.65 kWh", readme)
        for italian_label in (
            "📊 Consumo:",
            "↔️ Mese precedente:",
            "📈 Totale annuale:",
            "✅ Copertura dati:",
            "💶 Tariffa:",
            "💰 Costo totale:",
        ):
            self.assertNotIn(italian_label, readme)

    def test_readme_has_marketplace_installation(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn(
            "https://my.home-assistant.io/badges/marketplace_repository.svg",
            readme,
        )
        self.assertIn(
            "https://my.home-assistant.io/redirect/marketplace_repository/"
            "?owner=issu-lab&repository=energy-report&category=integration",
            readme,
        )
        self.assertIn("Home Assistant 2026.11", readme)
        self.assertNotIn("HACS", readme)

    def test_visual_asset_dimensions(self):
        assets = ROOT / "assets"
        self.assertEqual(png_size(assets / "energy-report-banner-light.png"), (5120, 1280))
        self.assertEqual(png_size(assets / "energy-report-banner-dark.png"), (5120, 1280))
        self.assertEqual(png_size(assets / "energy-report-social-preview.png"), (1280, 640))
        self.assertEqual(png_size(INTEGRATION / "brand" / "icon.png"), (256, 256))
        self.assertEqual(png_size(INTEGRATION / "brand" / "icon@2x.png"), (512, 512))

    def test_canonical_footer_assets_are_unchanged(self):
        assets = ROOT / "assets"
        expected = {
            "energy-report-footer-dark.png": "7ad502ce864b6a20220ba8ccf1d5ff9d8dfa78483664501b9136c8b717860e05",
            "energy-report-footer-light.png": "b13d672fd8e3dd96e804d24bc340f437d983e48014103a0a49f8db666f9a2ab2",
        }
        for filename, digest in expected.items():
            self.assertEqual(hashlib.sha256((assets / filename).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
