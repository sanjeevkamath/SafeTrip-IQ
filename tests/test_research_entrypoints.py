"""Research entry points must be inspectable without starting ML work."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (ROOT / "research/bert/train.py", ROOT / "research/clustering/fit.py")


class ResearchEntrypointTests(unittest.TestCase):
    def test_imports_without_site_packages_or_training(self):
        code = (
            "import importlib.util, sys; "
            "spec = importlib.util.spec_from_file_location('experiment', sys.argv[1]); "
            "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)"
        )
        with tempfile.TemporaryDirectory() as directory:
            for path in ENTRYPOINTS:
                with self.subTest(path=path.name):
                    result = subprocess.run(
                        [sys.executable, "-I", "-S", "-c", code, str(path)],
                        cwd=directory, capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_help_works_outside_repository_without_ml_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in ENTRYPOINTS:
                with self.subTest(path=path.name):
                    result = subprocess.run(
                        [sys.executable, "-I", "-S", str(path), "--help"],
                        cwd=directory, capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage:", result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])
