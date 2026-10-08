"""Explicit runtime configuration; no credential loading on import."""
import os
from pathlib import Path


def project_root():
    if os.environ.get("SAFETRIP_PROJECT_ROOT"):
        return Path(os.environ["SAFETRIP_PROJECT_ROOT"]).expanduser().resolve()
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for candidate in (start, *start.parents):
            if (candidate / "pyproject.toml").is_file() and (candidate / "docs/baseline/artifacts.json").is_file():
                return candidate
    return Path.cwd()


def resolve_path(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else project_root() / path


def load_environment():
    from dotenv import load_dotenv
    load_dotenv(project_root() / ".env", override=False)
