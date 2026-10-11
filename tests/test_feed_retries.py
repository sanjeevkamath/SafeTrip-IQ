import types
import unittest
from unittest.mock import Mock, patch

from safetrip.ingestion.advisories import fetch_feed_bytes


class FeedRetryTests(unittest.TestCase):
    def test_retry_limits_and_nonretryable_errors(self):
        class ConnectionError(Exception): pass
        class Timeout(Exception): pass
        class SSLError(ConnectionError): pass
        class HTTPError(Exception): pass

        def response(status):
            item = Mock(status_code=status, content=b"raw XML")
            if status >= 400:
                item.raise_for_status.side_effect = HTTPError()
            return item

        cases = [([response(503), response(200)], 2, None),
                 ([response(429), response(502), response(200)], 3, None),
                 ([Timeout(), ConnectionError(), response(200)], 3, None),
                 ([response(503)] * 3, 3, HTTPError),
                 ([Timeout()] * 3, 3, Timeout),
                 ([response(404)], 1, HTTPError),
                 ([SSLError()], 1, SSLError)]
        for replies, count, error in cases:
            fake = types.SimpleNamespace(get=Mock(side_effect=replies), exceptions=types.SimpleNamespace(
                SSLError=SSLError, ConnectionError=ConnectionError, Timeout=Timeout))
            with self.subTest(count=count, error=error), patch.dict('sys.modules', {'requests':fake}), patch('time.sleep') as sleep:
                if error:
                    with self.assertRaises(error): fetch_feed_bytes()
                else:
                    self.assertEqual(fetch_feed_bytes(), b"raw XML")
                self.assertEqual(fake.get.call_count, count)
                self.assertEqual(sleep.call_count, count - 1)
                self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2][:count - 1])
