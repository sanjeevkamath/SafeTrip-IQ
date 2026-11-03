import unittest
from safetrip.inference.document_inputs import token_windows


class DocumentInputTests(unittest.TestCase):
    def test_chunks_cover_every_token_and_respect_overlap(self):
        ids = list(range(1000))
        windows = token_windows(ids, policy="chunks", max_length=256, overlap=128)
        self.assertEqual(set().union(*(set(window) for window in windows)), set(ids))
        self.assertTrue(all(len(window) <= 254 for window in windows))
        self.assertEqual(windows[0][-128:], windows[1][:128])

    def test_head_tail_retains_end_and_short_documents_unchanged(self):
        ids = list(range(1000))
        window = token_windows(ids, policy="head_tail", max_length=512)[0]
        self.assertEqual(len(window), 510)
        self.assertEqual(window[:255], ids[:255])
        self.assertEqual(window[-255:], ids[-255:])
        self.assertEqual(token_windows([1, 2], policy="head_tail", max_length=512), [[1, 2]])

    def test_invalid_policy_and_overlap_fail(self):
        for arguments in ({"policy": "unknown", "max_length": 256},
                          {"policy": "chunks", "max_length": 256, "overlap": 254}):
            with self.assertRaises(ValueError):
                token_windows([1], **arguments)
