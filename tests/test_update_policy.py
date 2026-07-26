import unittest

from inventorypro.domains.updates.policy import (
    normalize_maintenance_window,
    normalize_update_settings,
)


DEFAULT_UPDATES = {
    "autoUpdateEnabled": False,
    "channel": "stable",
    "checkIntervalMinutes": 360,
    "maintenanceWindow": "03:30",
}


class UpdatePolicyTestCase(unittest.TestCase):
    def test_maintenance_window_normalizes_supported_formats(self):
        for raw_window, normalized_window in (
            ("09:00", "09:00"),
            ("9:00", "09:00"),
            ("09:00:00", "09:00"),
            ("23:30", "23:30"),
            ("00:00", "00:00"),
        ):
            with self.subTest(raw_window=raw_window):
                self.assertEqual(normalize_maintenance_window(raw_window), normalized_window)

        self.assertIsNone(normalize_maintenance_window("09:00:30"))
        self.assertIsNone(normalize_maintenance_window("24:00"))

    def test_enabled_updates_require_signed_channel_interval_and_window(self):
        settings, errors = normalize_update_settings(
            {
                "autoUpdateEnabled": True,
                "channel": "preview",
                "checkIntervalMinutes": "invalid",
                "maintenanceWindow": "09:00:30",
            },
            DEFAULT_UPDATES,
        )

        self.assertTrue(settings["autoUpdateEnabled"])
        self.assertEqual(settings["channel"], "preview")
        self.assertEqual(
            errors,
            {
                "updates.channel": "Nur der signierte Stable-Kanal ist zulässig.",
                "updates.checkIntervalMinutes": "Prüfintervall muss eine Zahl sein.",
                "updates.maintenanceWindow": (
                    "Wartungsfenster muss eine gültige Uhrzeit sein "
                    "(z. B. 09:00, 9:00 oder 09:00:00)."
                ),
            },
        )

    def test_disabled_updates_normalize_invalid_values_to_safe_defaults(self):
        settings, errors = normalize_update_settings(
            {
                "autoUpdateEnabled": False,
                "channel": "preview",
                "checkIntervalMinutes": "invalid",
                "maintenanceWindow": "",
            },
            DEFAULT_UPDATES,
        )

        self.assertEqual(errors, {})
        self.assertEqual(settings, DEFAULT_UPDATES)


if __name__ == "__main__":
    unittest.main()
