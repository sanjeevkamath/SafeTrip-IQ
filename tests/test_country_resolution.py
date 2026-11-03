import unittest
from safetrip.ingestion.advisories import map_records
from safetrip.ingestion.countries import resolve_iso3


class CountryResolutionTests(unittest.TestCase):
    def test_preserves_legacy_codes_and_verified_current_alias(self):
        for name, code, expected in (("Cambodia", "CB", "KHM"), ("Cambodia", "KH", "KHM"),
                                     ("Niger", "NG", "NER"), ("Nigeria", "NI", "NGA"),
                                     ("Tunisia", "TN", "TUN"), ("Saint Kitts and Nevis", "KN", "KNA"),
                                     ("Germany", "GM", "DEU"), ("São Tomé and Príncipe", "TP", "STP")):
            self.assertEqual(resolve_iso3(name, code), expected)

    def test_conflicting_identity_fails_instead_of_wrong_country_write(self):
        with self.assertRaises(ValueError):
            resolve_iso3("Canada", "GM")
        self.assertEqual(resolve_iso3("Macau", "CH"), "MAC")

    def test_newest_duplicate_wins_independently_of_feed_order(self):
        def item(code, date, text):
            return f'<item><title>Cambodia - Level 2</title><category domain="Country-Tag">{code}</category><pubDate>{date}</pubDate><description>{text}</description></item>'
        new = item("KH", "Thu, 27 Aug 2026", "Kidnapping occurs.")
        old = item("CB", "Thu, 01 Jan 2026", "Theft occurs.")
        for xml in (new + old, old + new):
            rows = map_records("<rss><channel>" + xml + "</channel></rss>")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["iso3"], "KHM")
            self.assertEqual(rows[0]["description_text"], "kidnapping occurs.")

    def test_undated_conflicting_duplicates_fail(self):
        xml = '<rss><channel><item><title>Canada - Level 2</title><category domain="Country-Tag">CA</category><description>Crime occurs.</description></item><item><title>Canada - Level 2</title><category domain="Country-Tag">CA</category><description>Flooding occurs.</description></item></channel></rss>'
        with self.assertRaises(ValueError):
            map_records(xml)

    def test_regions_can_be_evaluated_but_not_silently_published_as_country(self):
        with self.assertRaisesRegex(ValueError, "aggregation policy"):
            resolve_iso3("Gaza", "IS")
        self.assertEqual(resolve_iso3("Gaza", "IS", allow_regions=True), "PSE")
        self.assertEqual(resolve_iso3("The West Bank", "IS", allow_regions=True), "PSE")
        with self.assertRaisesRegex(ValueError, "aggregation policy"):
            resolve_iso3("The West Bank", "IS")
