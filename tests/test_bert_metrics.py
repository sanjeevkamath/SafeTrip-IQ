import unittest
from research.scripts.evaluate_bert_validation import metrics


class BertMetricsTests(unittest.TestCase):
    def test_per_class_metrics_and_high_risk_underestimation(self):
        result = metrics([0, 1, 2, 3], [0, 1, 1, 2])
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["high_risk_underestimation_rate"], 1.0)
        self.assertEqual(result["high_risk_predicted_low_risk_rate"], 0.5)
        self.assertEqual(result["per_advisory_level"]["4"]["recall"], 0.0)
        self.assertEqual(result["confusion_matrix_actual_rows_predicted_columns"][3][2], 1)

    def test_invalid_class_or_missing_predictions_rejected(self):
        for labels, predictions in (([], []), ([0], []), ([4], [1])):
            with self.assertRaises(ValueError):
                metrics(labels, predictions)
