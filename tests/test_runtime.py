import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from safetrip import jobs
from safetrip.cli import main
from safetrip.ingestion.advisories import clean_html_to_text, map_records
from safetrip.persistence.repository import write_bert_scores

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/advisories.xml"


class RuntimeTests(unittest.TestCase):
    def test_all_runtime_modules_import_without_optional_dependencies(self):
        code = "import safetrip, pkgutil, importlib; [importlib.import_module(m.name) for m in pkgutil.walk_packages(safetrip.__path__, safetrip.__name__ + '.')]; import sys; assert not {'torch','transformers','requests','supabase','dotenv'} & sys.modules.keys()"
        result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_writer_wrappers_do_no_work_on_import(self):
        code = (
            "import importlib, sys; sys.path.insert(0, sys.argv[1]); "
            "[importlib.import_module(name) for name in "
            "['populate_countries','populate_clustering','populate_travel_advisories','score_advisories','modify_clustering']]; "
            "assert not {'torch','requests','supabase','dotenv'} & sys.modules.keys()"
        )
        result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT / "db/scripts")], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_mapping_and_existing_cleaning_are_preserved(self):
        rows = jobs.ingest(FIXTURE)
        self.assertEqual([row["iso3"] for row in rows], ["CAN", "JPN"])
        self.assertEqual(rows[0]["description_text"], "exercise normal precautions. watch for winter road conditions.")
        self.assertEqual(clean_html_to_text("<p>Crime &amp; theft.</p> Review the Traveler’s Checklist. More text."), "crime & theft.")

    def test_unmapped_or_empty_feed_fails(self):
        for xml in ("<rss><channel/></rss>", "<rss><channel><item><title>Unknown - Level 2</title><description>Example</description></item></channel></rss>"):
            with self.assertRaises(ValueError):
                map_records(xml)

    def test_invalid_inputs_rejected_before_loading_model(self):
        with patch("safetrip.inference.bert.load_model") as load:
            for rows in ([], [{"iso3":"CAN", "description_text":""}], [{"iso3":"CAN", "description_text":"text"}]*2):
                with self.assertRaises(ValueError): jobs.score(rows, "missing-checkpoint")
            load.assert_not_called()

    def test_refresh_defaults_to_local_artifact(self):
        with tempfile.TemporaryDirectory() as directory, patch("safetrip.config.load_environment"), patch.dict("os.environ", {}, clear=True), patch("safetrip.persistence.supabase.get_writer_client") as writer, patch("safetrip.jobs.score", return_value=[{"iso3":"CAN", "bert_score":0}]) as scoring:
            output = Path(directory) / "refresh.json"
            self.assertEqual(main(["refresh", "--input", str(FIXTURE), "--output", str(output)]), 0)
            artifact = json.loads(output.read_text())
            self.assertEqual(len(artifact["advisories"]), 2)
            self.assertEqual(artifact["bert_scores"][0]["bert_score"], 0)
            writer.assert_not_called()
            scoring.assert_called_once()
            # No overwrite and no new scoring/publication when a run path is reused.
            self.assertEqual(main(["refresh", "--input", str(FIXTURE), "--output", str(output), "--write"]), 1)
            writer.assert_not_called()
            scoring.assert_called_once()

    def test_explicit_publication_uses_separate_repository_boundary(self):
        with tempfile.TemporaryDirectory() as directory, patch("safetrip.config.load_environment"), patch.dict("os.environ", {}, clear=True), patch("safetrip.persistence.supabase.get_writer_client") as writer, patch("safetrip.persistence.repository.write_advisories") as publish:
            output = Path(directory) / "ingested.json"
            self.assertEqual(main(["ingest", "--input", str(FIXTURE), "--output", str(output), "--write"]), 0)
            publish.assert_called_once_with(writer.return_value, json.loads(output.read_text()))

    def test_unknown_scored_country_prevents_all_writes(self):
        client = Mock()
        client.table.return_value.select.return_value.execute.return_value.data = [{"iso3":"CAN"}]
        with self.assertRaises(ValueError):
            write_bert_scores(client, [{"iso3":"CAN"}, {"iso3":"ZZZ"}])
        client.table.return_value.upsert.assert_not_called()
