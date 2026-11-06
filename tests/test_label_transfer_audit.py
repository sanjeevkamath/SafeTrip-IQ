import unittest
from research.scripts.audit_label_transfer import CUES, CUE_LABELS, HEALTH_SENTENCE, subgroup
from research.scripts.audit_source_provenance import legacy_normalize


class LabelTransferAuditTests(unittest.TestCase):
    def test_subgroups_keep_class_support_and_prediction_alignment(self):
        rows = [{'text': 'COVID risk remains.', 'label': 2},
                {'text': 'Armed conflict.', 'label': 3},
                {'text': 'Obsolete COVID links removed.', 'label': 1}]
        result = subgroup(rows, [2, 1, 1])
        self.assertEqual(result['covid_mention']['rows'], 2)
        self.assertEqual(result['covid_mention']['class_counts'], {2: 1, 3: 1})
        self.assertEqual(result['covid_mention']['metrics']['accuracy'], 1)
        self.assertEqual(result['no_covid_mention']['metrics']['high_risk_underestimation_rate'], 1)

    def test_first_cue_is_a_screen_not_a_country_level_parser(self):
        text = 'Updates to do not travel areas. Exercise increased caution in Tunisia.'
        match = CUES.search(text)
        self.assertEqual(CUE_LABELS[match.group()], 3)
        # This demonstrates the documented regional/update-note false-positive risk.
        self.assertNotEqual(CUE_LABELS[match.group()], 1)

    def test_health_ablation_preserves_separate_risk_sentences(self):
        self.assertEqual(HEALTH_SENTENCE.sub(' ', 'COVID cases increased. Kidnapping occurs.'),
                         '  Kidnapping occurs.')

    def test_legacy_normalization_exposes_numeric_information_loss(self):
        self.assertEqual(legacy_normalize('Curfew begins at 21:00 on June 4, 2021.'),
                         'curfew begins at : on june , .')


if __name__ == '__main__':
    unittest.main()
