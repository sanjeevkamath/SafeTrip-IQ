import unittest
from unittest.mock import Mock, patch

from safetrip import jobs
from safetrip.ingestion.advisories import CLEANING_VERSION, clean_html_to_text, map_records


class AdvisoryCleaningTests(unittest.TestCase):
    def test_labels_and_names_removed_but_risk_evidence_retained(self):
        text = clean_html_to_text(
            "<p>Country Summary: France – Level 4: Do not travel to France "
            "due to kidnapping and violent crime. Border closures affect transport.</p>"
        )
        self.assertNotIn("france", text)
        self.assertNotIn("level", text)
        self.assertNotIn("do not travel", text)
        self.assertIn("kidnapping and violent crime", text)
        self.assertIn("border closures affect transport", text)

    def test_singular_recommendation_and_country_abbreviations(self):
        text = clean_html_to_text(
            "Exercise normal precaution in the Republic of Korea (ROK). "
            "The DRC and DPRK face armed conflict."
        )
        for cue in ("precaution", "korea", "rok", "drc", "dprk"):
            self.assertNotIn(cue, text)
        self.assertIn("armed conflict", text)
        self.assertIn("rocky roads", clean_html_to_text("Rocky roads remain dangerous."))

    def test_all_four_recommendations_and_level_formats(self):
        for cue in ("Level 1: Exercise normal precautions", "Level 2: Exercise increased caution",
                    "Level 3: Reconsider travel", "Level 4: Do not travel",
                    "Advisory Level IV", "Level three", "Level-4"):
            with self.subTest(cue=cue):
                self.assertEqual(clean_html_to_text(cue + ". Violent crime occurs."), "violent crime occurs.")

    def test_aliases_cross_country_references_and_word_boundaries(self):
        text = clean_html_to_text(
            "Myanmar (Burma), Côte d’Ivoire and South Korea. Canadian roads and turkeys. "
            "Chad and chador. Russia and the United States."
        )
        for name in ("myanmar", "burma", "ivoire", "south korea", "chad ", "russia", "united states"):
            self.assertNotIn(name, text)
        for word in ("canadian", "turkeys", "chador", "roads"):
            self.assertIn(word, text)

    def test_feed_specific_country_and_raw_text_preserved(self):
        xml = '<rss><channel><item><title>Example Islands - Level 3</title><category domain="Country-Tag">CA</category><description>Reconsider travel to Example Islands due to armed robbery.</description></item></channel></rss>'
        row = map_records(xml)[0]
        self.assertEqual(row["iso3"], "CAN")
        self.assertEqual(row["country_name"], "Example Islands")
        self.assertIn("Example Islands", row["description_raw_html"])
        self.assertNotIn("example islands", row["description_text"])
        self.assertIn("armed robbery", row["description_text"])

    def test_boilerplate_does_not_erase_following_risk_sentence(self):
        self.assertEqual(clean_html_to_text(
            "Crime occurs. Enroll in the Smart Traveler Enrollment Program (STEP) to receive messages and Alerts. Kidnapping occurs."
        ), "crime occurs. kidnapping occurs.")

    def test_encoded_html_and_repeated_cleaning(self):
        text = clean_html_to_text("&lt;p&gt;Canada Level 3: Reconsider travel. Crime &amp; theft.&lt;/p&gt;")
        self.assertNotIn("<", text)
        self.assertIn("crime & theft", text)
        self.assertEqual(clean_html_to_text(text), text)

    def test_preserves_government_restrictions_and_removes_malformed_labels(self):
        text = clean_html_to_text("Level 3Travel Health Notice. Avoid nonessential travel. U.S. government employees working in France must obtain special authorization due to kidnapping.")
        self.assertNotIn("level 3", text)
        self.assertNotIn("avoid nonessential travel", text)
        self.assertIn("must obtain special authorization due to kidnapping", text)

    def test_json_scoring_inputs_cleaned_without_mutation(self):
        rows = [{"iso3": "CAN", "description_text": "Canada Level 3: Reconsider travel. Violent crime occurs."}]
        prepared = jobs.prepare_model_rows(rows)
        self.assertIn("Canada", rows[0]["description_text"])
        self.assertEqual(prepared[0]["description_text"], "violent crime occurs.")

    def test_label_only_text_fails_before_model_load(self):
        with patch("safetrip.inference.bert.load_model") as load:
            with self.assertRaises(ValueError):
                jobs.score([{"iso3": "CAN", "description_text": "Canada Level 1: Exercise normal precautions."}], "unused")
            load.assert_not_called()

    def test_model_receives_redacted_text_and_records_cleaning_version(self):
        metadata = {}
        with patch("safetrip.inference.integrity.model_fingerprint", return_value="model"), \
             patch("safetrip.inference.bert.load_model", return_value=(Mock(), Mock())), \
             patch("safetrip.inference.bert.score_texts", return_value=[2]) as inference:
            result = jobs.score([{"iso3": "CAN", "description_text": "Canada Level 3: Reconsider travel. Crime occurs."}], "model", metadata)
        self.assertEqual(inference.call_args.args[0], ["crime occurs."])
        self.assertEqual(result[0]["cleaned_text"], "crime occurs.")
        self.assertEqual(result[0]["iso3"], "CAN")
        self.assertEqual(metadata["cleaning_version"], CLEANING_VERSION)

    def test_mismatched_candidate_cleaner_fails_before_inference(self):
        model = Mock()
        model.config.safetrip_cleaning_version = "advisory-no-country-labels-v3"
        with patch("safetrip.inference.bert.load_model", return_value=(Mock(), model)), \
             patch("safetrip.inference.bert.score_texts") as inference:
            with self.assertRaisesRegex(ValueError, "preprocessing version"):
                jobs.score([{"iso3": "CAN", "description_text": "Violent crime occurs."}], "model")
            inference.assert_not_called()

    def test_new_cleaning_version_invalidates_even_identical_cached_text(self):
        publisher = Mock()
        publisher.cached_predictions.return_value = {"CAN": {
            "iso3": "CAN", "cleaned_text": "crime occurs.", "bert_score": 0,
            "status": "succeeded", "last_run_id": "old",
            "metadata": {"cleaning_version": "legacy-advisory-v1", "model_version": "model", "inference_version": "bert-document-inputs-v2"},
        }}
        metadata = {"cleaning_version": "legacy-advisory-v1"}
        with patch("safetrip.inference.integrity.model_fingerprint", return_value="model"), patch("safetrip.jobs.score", return_value=[{"iso3": "CAN", "bert_score": 1}]) as score:
            _, reused = jobs.incremental_score([{"iso3": "CAN", "description_text": "crime occurs."}], "model", publisher, metadata)
        score.assert_called_once()
        self.assertEqual(reused, [])
        self.assertEqual(metadata["cleaning_version"], CLEANING_VERSION)
