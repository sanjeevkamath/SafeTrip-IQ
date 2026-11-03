import tempfile
from pathlib import Path
import unittest

from scripts.audit_bert_data import audit


class BertDataAuditTests(unittest.TestCase):
    def test_detects_duplicates_created_by_redaction_and_label_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = {}
            for split, text in (("train", "1,Canada Level 1: Exercise normal precautions. Crime occurs.\n"),
                                ("test", "4,France Level 4: Do not travel. Crime occurs.\n")):
                path = Path(directory) / (split + ".csv")
                path.write_text("label,text\n" + text)
                sources[split] = path
            result = audit(sources)
        self.assertEqual(result["duplicate_analysis"]["raw"]["cross_split_groups"], 0)
        cleaned = result["duplicate_analysis"]["cleaned"]
        self.assertEqual(cleaned["cross_split_groups"], 1)
        self.assertEqual(cleaned["conflicting_label_groups"], 1)
        self.assertFalse(result["country_time_provenance_available"])

    def test_empty_after_redaction_is_reported_and_invalid_labels_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text("label,text\n1,Canada Level 1 Exercise normal precautions\n")
            self.assertEqual(audit({"train": path})["sources"]["train"]["empty_after_cleaning"], 1)
            path.write_text("label,text\n5,Crime occurs\n")
            with self.assertRaises(ValueError):
                audit({"train": path})
