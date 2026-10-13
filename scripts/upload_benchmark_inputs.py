"""Upload only the verified checkpoint and historical fixture; never launch a task."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from safetrip.inference.integrity import model_fingerprint, verify_model
from safetrip.jobs import validate_advisories
from scripts.package_model import package

ROOT = Path(__file__).resolve().parents[1]


def command(arguments, *, timeout=900):
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Report only recognized codes and fixed advice, never raw CLI diagnostics.
        stage = "AWS identity lookup" if arguments[:3] == ["aws", "sts", "get-caller-identity"] else (
            "S3 upload" if arguments[:3] == ["aws", "s3api", "put-object"] else (
                "AWS " + " ".join(arguments[1:3]) if arguments[0] == "aws" else "Terraform output lookup"))
        error = re.search(r"An error occurred \(([A-Za-z0-9_.-]+)\)", result.stderr)
        if error:
            code = error.group(1)
            advice = "Refresh the temporary credentials in this terminal." if code in {
                "ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId", "InvalidToken", "UnrecognizedClientException"
            } else "Check this role's permissions." if code in {"AccessDenied", "AccessDeniedException"} else "Check AWS connectivity and configuration."
            raise RuntimeError(f"{stage} failed ({code}). {advice}")
        if "Unable to locate credentials" in result.stderr:
            raise RuntimeError(f"{stage} failed: no AWS credentials are available in this terminal.")
        if "could not be found" in result.stderr and "profile" in result.stderr.lower():
            raise RuntimeError(f"{stage} failed: the selected AWS profile cannot be loaded.")
        raise RuntimeError(f"{stage} failed; check login, permissions, and connectivity.")
    return json.loads(result.stdout)


def save_report(path, report):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)


def upload(bucket, key, source):
    result = command(["aws", "s3api", "put-object", "--region", "us-east-2",
                      "--bucket", bucket, "--key", key, "--body", str(source),
                      "--server-side-encryption", "AES256", "--output", "json"])
    version = result.get("VersionId")
    if not version or version == "null":
        raise ValueError("S3 did not return a pinned VersionId; check bucket versioning.")
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--advisories", default=".local/baselines/20261008T032611470774Z/travel_advisories.json")
    parser.add_argument("--output", default=".local/aws/benchmark-inputs.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate local inputs and print the intended actions without AWS calls.")
    args = parser.parse_args()
    manifest = ROOT / "docs/baseline/artifacts.json"
    model = ROOT / "results/checkpoint-189"
    verify_model(model, manifest)
    fingerprint = model_fingerprint(model)
    rows = validate_advisories(json.loads((ROOT / args.advisories).read_bytes()))
    # Upload only the two fields inference needs, excluding database provenance or other export fields.
    payload = json.dumps([{key: row[key] for key in ("iso3", "description_text")} for row in rows],
                         sort_keys=True, ensure_ascii=False).encode()
    input_hash = hashlib.sha256(payload).hexdigest()
    outputs = command(["terraform", "-chdir=infra/terraform", "output", "-json"])
    bucket = outputs["model_bucket"]["value"]
    registry = outputs["ecr_repository_url"]["value"].split("/", 1)[0]
    report = {"bucket": bucket, "model_version": fingerprint,
              "model_s3_key": f"models/{fingerprint}/checkpoint.tar",
              "benchmark_s3_key": f"benchmarks/advisories-{input_hash}.json",
              "benchmark_sha256": input_hash, "benchmark_rows": len(rows), "complete": False}
    if args.dry_run:
        print(f"Verified checkpoint and {len(rows)} historical advisories. Would upload two private, versioned S3 objects. No AWS calls or task launches performed.")
        return 0
    identity = command(["aws", "sts", "get-caller-identity", "--output", "json"])
    if registry.split(".", 1)[0] != identity["Account"]:
        raise ValueError("Authenticated account differs from the Terraform ECR account.")
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = json.loads(path.read_text())
        if any(previous.get(key) != report[key] for key in ("bucket", "model_version", "benchmark_sha256")):
            raise ValueError("Existing report pins different inputs; choose a new --output path.")
        report = previous
    with tempfile.TemporaryDirectory(prefix="upload-", dir=path.parent) as temporary:
        temporary = Path(temporary)
        if not report.get("model_s3_version_id"):
            print("Packaging the verified checkpoint, then uploading its immutable version...", flush=True)
            archive = temporary / "checkpoint.tar"
            packaged = package(model, manifest, archive)
            report["model_archive_sha256"] = packaged["sha256"]
            report["model_archive_bytes"] = packaged["bytes"]
            report["model_s3_version_id"] = upload(bucket, report["model_s3_key"], archive)
            save_report(path, report)
        if not report.get("benchmark_s3_version_id"):
            print(f"Uploading {len(rows)} historical advisories for the read-only benchmark...", flush=True)
            source = temporary / "advisories.json"
            source.write_bytes(payload)
            report["benchmark_s3_version_id"] = upload(bucket, report["benchmark_s3_key"], source)
            save_report(path, report)
    report["complete"] = True
    save_report(path, report)
    print(f"Pinned S3 versions and checksums saved to {path.relative_to(ROOT)}. Worker remains stopped.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as error:
        print(f"Upload stopped: {error}")
        raise SystemExit(1)
