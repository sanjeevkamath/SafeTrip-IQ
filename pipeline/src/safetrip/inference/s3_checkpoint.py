"""Download a pinned checkpoint archive before the worker touches a database."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import time

from safetrip.inference.integrity import verify_model


def bootstrap_from_s3(*, bucket, key, version_id, archive_sha256, destination, manifest, client=None):
    if not all((bucket, key, version_id, archive_sha256)):
        raise ValueError("Bucket, key, S3 version ID, and archive SHA-256 are required.")
    if len(archive_sha256) != 64 or any(c not in "0123456789abcdef" for c in archive_sha256):
        raise ValueError("Archive SHA-256 must be lowercase hexadecimal.")
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("Checkpoint destination already exists; refusing to replace it.")
    expected = json.loads(Path(manifest).read_text())["model_files"]
    if not expected or any(Path(name).name != name for name in expected):
        raise ValueError("Invalid model manifest filenames.")
    if client is None:
        import boto3
        client = boto3.client("s3")

    started = time.monotonic()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="safetrip-model-", dir=destination.parent) as temporary:
        temporary = Path(temporary)
        archive = temporary / "checkpoint.tar"
        client.download_file(bucket, key, str(archive), ExtraArgs={"VersionId": version_id})
        archive_bytes = archive.stat().st_size
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != archive_sha256:
            raise ValueError("Downloaded checkpoint archive checksum differs from the pinned value.")

        extracted = temporary / "model"
        extracted.mkdir()
        seen = set()
        with tarfile.open(archive, mode="r:") as source:
            for member in source:
                if member.name not in expected or not member.isfile() or member.name in seen:
                    raise ValueError("Checkpoint archive has an unexpected member.")
                if member.size != expected[member.name]["bytes"]:
                    raise ValueError("Checkpoint archive member has an unexpected size.")
                seen.add(member.name)
                with source.extractfile(member) as input_stream, (extracted / member.name).open("xb") as output:
                    shutil.copyfileobj(input_stream, output, length=1024 * 1024)
        if seen != set(expected):
            raise ValueError("Checkpoint archive is missing model files.")
        verify_model(extracted, manifest)
        extracted.rename(destination)
    return {"model_s3_version_id": version_id, "model_archive_sha256": archive_sha256,
            "model_download_bytes": archive_bytes,
            "model_bootstrap_seconds": round(time.monotonic() - started, 3)}


def bootstrap_from_environment():
    bucket = os.environ.get("SAFETRIP_MODEL_S3_BUCKET")
    if not bucket:
        return None
    return bootstrap_from_s3(
        bucket=bucket,
        key=os.environ.get("SAFETRIP_MODEL_S3_KEY"),
        version_id=os.environ.get("SAFETRIP_MODEL_S3_VERSION_ID"),
        archive_sha256=os.environ.get("SAFETRIP_MODEL_S3_SHA256"),
        destination=os.environ["SAFETRIP_MODEL_PATH"],
        manifest=os.environ["SAFETRIP_MODEL_MANIFEST"],
    )
