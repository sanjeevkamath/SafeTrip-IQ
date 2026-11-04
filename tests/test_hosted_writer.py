"""Credential-free boundary tests for hosted writer setup and URL handling."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy.engine import make_url
from safetrip.persistence.postgres import writer_url_allowed

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hosted_advisories',ROOT/'db/scripts/hosted_advisories.py')
hosted=importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosted)


class HostedWriterTests(unittest.TestCase):
    def test_writer_identity_accepts_only_expected_pooler_form(self):
        self.assertTrue(writer_url_allowed(make_url('postgresql+psycopg://safetrip_writer@localhost/test')))
        self.assertTrue(writer_url_allowed(make_url(
            'postgresql+psycopg://safetrip_writer.example@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=verify-full')))
        for url in [
            'postgresql+psycopg://postgres@localhost/test',
            'postgresql+psycopg://safetrip_writer@localhost/test?user=postgres',
            'postgresql+psycopg://safetrip_writer@localhost/test?host=other',
            'postgresql+psycopg://safetrip_writer.example@localhost:5432/postgres?sslmode=verify-full',
            'postgresql+psycopg://safetrip_writer.example@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require',
            'postgresql+psycopg://safetrip_writer.example@aws-0-us-east-2.pooler.supabase.com:6543/postgres?sslmode=verify-full',
        ]:
            with self.subTest(url=url): self.assertFalse(writer_url_allowed(make_url(url)))

    def test_private_config_permissions_and_target_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'writer.json';ca=Path(directory)/'ca.crt';ca.write_text('test certificate placeholder')
            data={'host':'aws-0-us-east-2.pooler.supabase.com','port':'5432','dbname':'postgres',
                  'user':'safetrip_writer.example','password':'synthetic-test-only'}
            config.write_text(json.dumps(data));config.chmod(0o600)
            with patch.object(hosted,'CONFIG',config),patch.object(hosted,'CA',ca):
                self.assertEqual(hosted.read_config()['user'],'safetrip_writer.example')
                config.chmod(0o644)
                with self.assertRaises(ValueError):hosted.read_config()
                config.chmod(0o600);data['user']='postgres.example';config.write_text(json.dumps(data))
                with self.assertRaises(ValueError):hosted.read_config()

    def test_import_is_blocked_before_credentials_for_an_unbounded_capture(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'capture.json';path.write_text('{"iso3":null}')
            with patch.object(hosted,'read_config') as credentials:
                with self.assertRaises(ValueError):
                    hosted.ingest(SimpleNamespace(input=str(path),output=str(Path(directory)/'result.json')))
                credentials.assert_not_called()


if __name__=='__main__': unittest.main()
