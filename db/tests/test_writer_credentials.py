"""Offline configuration tests. No real credentials or database writes."""

import base64
import json
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from db.scripts.supabase_writer import ROOT_ENV, get_writer_client, writer_credentials


def fake_jwt(role):
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode())
    return "test." + payload.decode().rstrip("=") + ".not-a-real-signature"


class WriterCredentialTests(unittest.TestCase):
    def setUp(self):
        self.env = {"SUPABASE_URL": "https://example.supabase.co"}

    def test_never_falls_back_to_public_credentials(self):
        for name in ("ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                writer_credentials({**self.env, name: fake_jwt("anon")})

    def test_rejects_public_or_malformed_legacy_key_without_echoing_it(self):
        for key in (fake_jwt("anon"), fake_jwt("authenticated"),
                    "sensitive-invalid-value", "a.@@@@.c", "a.W10.c"):
            with self.subTest(key_kind=key.split(".")[0]):
                with self.assertRaises(ValueError) as caught:
                    writer_credentials({**self.env, "SUPABASE_SERVICE_ROLE_KEY": key})
                self.assertNotIn(key, str(caught.exception))

    def test_accepts_service_role_shape(self):
        key = fake_jwt("service_role")
        self.assertEqual(writer_credentials({**self.env, "SUPABASE_SERVICE_ROLE_KEY": key}),
                         (self.env["SUPABASE_URL"], key))

    def test_accepts_secret_shape(self):
        key = "sb_secret_test_only"
        self.assertEqual(writer_credentials({**self.env, "SUPABASE_SECRET_KEY": key}),
                         (self.env["SUPABASE_URL"], key))

    def test_rejects_publishable_key_in_secret_variable(self):
        with self.assertRaises(ValueError):
            writer_credentials({**self.env, "SUPABASE_SECRET_KEY": "sb_publishable_test"})

    def test_rejects_ambiguous_configuration(self):
        with self.assertRaises(ValueError):
            writer_credentials({**self.env, "SUPABASE_SECRET_KEY": "sb_secret_test",
                                "SUPABASE_SERVICE_ROLE_KEY": fake_jwt("service_role")})

    def test_requires_clean_https_project_url(self):
        for url in ("", "http://example.supabase.co", "https://user:pass@example.com",
                    "https://example.com?key=secret", "https://example.com/rest/v1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                writer_credentials({"SUPABASE_URL": url, "SUPABASE_SECRET_KEY": "sb_secret_test"})

    def test_invalid_config_never_creates_client(self):
        create = Mock()
        dotenv = Mock()
        with patch.dict("sys.modules", {"dotenv": SimpleNamespace(load_dotenv=dotenv),
                                       "supabase": SimpleNamespace(create_client=create)}), \
                patch.dict("os.environ", self.env, clear=True):
            with self.assertRaises(ValueError):
                get_writer_client()
        create.assert_not_called()
        dotenv.assert_called_once_with(ROOT_ENV, override=False)

    def test_passes_explicit_backend_credential_to_client(self):
        key = "sb_secret_test"
        create = Mock()
        with patch.dict("sys.modules", {"dotenv": SimpleNamespace(load_dotenv=Mock()),
                                       "supabase": SimpleNamespace(create_client=create)}), \
                patch.dict("os.environ", {**self.env, "SUPABASE_SECRET_KEY": key}, clear=True):
            self.assertIs(get_writer_client(), create.return_value)
        create.assert_called_once_with(self.env["SUPABASE_URL"], key)


if __name__ == "__main__":
    unittest.main()
