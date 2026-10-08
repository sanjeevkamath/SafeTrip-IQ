import json
from pathlib import Path
import unittest

from pipeline.scoring import legacy_safety_score


class LegacyScoreBaselineTests(unittest.TestCase):
    def test_matches_every_captured_production_score(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/legacy_scores.json").read_text())
        self.assertEqual(len(fixture["rows"]), 212)
        for row in fixture["rows"]:
            with self.subTest(iso3=row["iso3"]):
                self.assertAlmostEqual(
                    legacy_safety_score(row["bert_score"], row["clustering_score"]),
                    row["safe_trip_score"], places=6,
                )

    def test_missing_component_is_not_interpreted_as_safest(self):
        self.assertEqual(legacy_safety_score(None, 2), 6.0)
        self.assertEqual(legacy_safety_score(3, None), 2.5)
        self.assertIsNone(legacy_safety_score(None, None))

    def test_rejects_invalid_classes(self):
        for values in ((4, 0), (-1, 0), (0, 5), (True, 0), (1.5, 0), ("1", 0)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                legacy_safety_score(*values)


if __name__ == "__main__":
    unittest.main()
