"""Generate ignored Terraform inputs from pinned S3/ECR reports; no AWS writes."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def task_inputs(inputs, image_report, outputs):
    if not inputs.get("complete"):
        raise ValueError("Complete the S3 uploads first.")
    if inputs.get("bucket") != outputs["model_bucket"]["value"]:
        raise ValueError("S3 upload bucket differs from the current Terraform bucket.")
    images = image_report.get("imageDetails", [])
    if len(images) != 1:
        raise ValueError("The ECR report must identify exactly one image.")
    image = images[0]
    repository = outputs["ecr_repository_url"]["value"]
    registry, repository_name = repository.split("/", 1)
    if image.get("registryId") != registry.split(".", 1)[0] or image.get("repositoryName") != repository_name:
        raise ValueError("Image metadata differs from the Terraform repository/account.")
    digest = image.get("imageDigest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("ECR image digest is invalid.")
    names = ("model_s3_key", "model_s3_version_id", "model_archive_sha256",
             "benchmark_s3_key", "benchmark_s3_version_id", "benchmark_sha256")
    if any(not isinstance(inputs.get(name), str) or not inputs[name] for name in names):
        raise ValueError("S3 artifact versions, keys, or hashes are missing.")
    if any(inputs[name] == "null" for name in ("model_s3_version_id", "benchmark_s3_version_id")):
        raise ValueError("S3 object versions must be pinned.")
    if any(not re.fullmatch(r"[0-9a-f]{64}", inputs[name]) for name in ("model_archive_sha256", "benchmark_sha256")):
        raise ValueError("Artifact SHA-256 hashes are invalid.")
    return {"benchmark_enabled": True, "image_digest": digest.removeprefix("sha256:"),
            **{name: inputs[name] for name in names}}


def main():
    inputs = json.loads((ROOT / ".local/aws/benchmark-inputs.json").read_text())
    image = json.loads((ROOT / ".local/aws/benchmark-image.json").read_text())
    result = subprocess.run(["terraform", "-chdir=infra/terraform", "output", "-json"],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Cannot read local Terraform outputs.")
    values = task_inputs(inputs, image, json.loads(result.stdout))
    output = ROOT / "infra/terraform/benchmark.auto.tfvars.json"
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, indent=2) + "\n")
    temporary.replace(output)
    print("Pinned artifact configuration saved to infra/terraform/benchmark.auto.tfvars.json (Git-ignored).")
    print("Terraform will now propose two benchmark task definitions. No resources created or tasks launched.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, FileNotFoundError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"Preparation stopped: {error}")
        raise SystemExit(1)
