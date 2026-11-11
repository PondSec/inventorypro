from datetime import datetime, timezone
from unittest import TestCase

from inventorypro.time import utc_now


class TimeUtilsTestCase(TestCase):
    def test_utc_now_returns_naive_utc_for_legacy_timestamp_contracts(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        current = utc_now()
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        self.assertIsNone(current.tzinfo)
        self.assertGreaterEqual(current, before)
        self.assertLessEqual(current, after)
