"""Measure the real verification/extraction path with a local archive copy."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
import time

from safetrip.inference.s3_checkpoint import bootstrap_from_s3


class LocalArchiveClient:
    def __init__(self, archive):
        self.archive = Path(archive)
        self.copy_seconds = None

    def download_file(self, bucket, key, destination, ExtraArgs):
        started = time.monotonic()
        shutil.copyfile(self.archive, destination)
        self.copy_seconds = round(time.monotonic() - started, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--manifest", default="docs/baseline/artifacts.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error("Choose an unused report path.")
    client = LocalArchiveClient(args.archive)
    with tempfile.TemporaryDirectory(prefix="safetrip-bootstrap-") as temporary:
        result = bootstrap_from_s3(bucket="local-benchmark", key="checkpoint.tar",
                                   version_id="local-fixture", archive_sha256=args.sha256,
                                   destination=Path(temporary) / "checkpoint-189",
                                   manifest=args.manifest, client=client)
    report = {"measured_at_utc": datetime.now(timezone.utc).isoformat(),
              "mode": "local_copy_then_verify_and_extract", "local_copy_seconds": client.copy_seconds,
              **result,
              "limitations": ["Local filesystem copy substitutes for S3; it does not measure AWS networking, task startup, or ECR download."]}
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
