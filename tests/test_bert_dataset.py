import csv
from pathlib import Path
import tempfile
import unittest

from scripts.prepare_bert_dataset import prepare


class BertDatasetTests(unittest.TestCase):
    def test_reproducible_splits_keep_duplicates_and_similar_texts_together(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = {}
            rows = [(str(label), " ".join(f"evidence{label}_{row}_{word}" for word in range(10)))
                    for label in range(1, 5) for row in range(8)]
            for split, entries in (("train", rows), ("test", [rows[0], (rows[0][0], rows[0][1] + " extra")])):
                path = Path(directory) / (split + ".csv")
                with path.open("w", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(["label", "text"])
                    writer.writerows(entries)
                sources[split] = path
            splits, report = prepare(sources)
            self.assertEqual((splits, report), prepare(sources))
        groups = [{row["group_id"] for row in entries} for entries in splits.values()]
        texts = [{row["text_sha256"] for row in entries} for entries in splits.values()]
        for i in range(3):
            for j in range(i):
                self.assertFalse(groups[i] & groups[j])
                self.assertFalse(texts[i] & texts[j])
        related = [split for split, entries in splits.items() if any("evidence1_0_0" in row["text"] for row in entries)]
        self.assertEqual(len(related), 1)
        self.assertEqual(report["unique_cleaned_rows"], 33)
        self.assertEqual(report["grouping"]["largest_group_rows"], 2)
        self.assertTrue(all(set(value["class_counts"]) == {0, 1, 2, 3} for value in report["splits"].values()))
