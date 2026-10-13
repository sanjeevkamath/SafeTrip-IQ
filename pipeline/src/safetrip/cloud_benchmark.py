"""One-shot Fargate inference measurement; no database access or publication."""
import hashlib
import json
import os
import resource
import sys
import time


def main():
    from safetrip import jobs
    required = ("SAFETRIP_BENCHMARK_S3_BUCKET", "SAFETRIP_BENCHMARK_S3_KEY",
                "SAFETRIP_BENCHMARK_S3_VERSION_ID", "SAFETRIP_BENCHMARK_SHA256")
    if any(not os.environ.get(name) for name in required):
        raise ValueError("Pinned benchmark input configuration is incomplete.")
    import boto3
    started = time.monotonic()
    response = boto3.client("s3").get_object(
        Bucket=os.environ["SAFETRIP_BENCHMARK_S3_BUCKET"],
        Key=os.environ["SAFETRIP_BENCHMARK_S3_KEY"],
        VersionId=os.environ["SAFETRIP_BENCHMARK_S3_VERSION_ID"])
    body = response["Body"].read()
    digest = hashlib.sha256(body).hexdigest()
    if digest != os.environ["SAFETRIP_BENCHMARK_SHA256"]:
        raise ValueError("Benchmark input checksum differs from the pinned value.")
    rows = jobs.validate_advisories(json.loads(body))
    input_seconds = time.monotonic() - started
    metadata = {"source_kind": "historical_benchmark"}
    inference_started = time.monotonic()
    scores = jobs.score(rows, os.environ["SAFETRIP_MODEL_PATH"], metadata=metadata)
    inference_seconds = time.monotonic() - inference_started
    report = {
        "input_rows": len(rows), "input_sha256": digest,
        "input_download_seconds": round(input_seconds, 3),
        "inference_seconds": round(inference_seconds, 3),
        "total_after_model_bootstrap_seconds": round(time.monotonic() - started, 3),
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "model_version": metadata["model_version"],
        "model_s3_version_id": metadata.get("model_s3_version_id"),
        "prediction_counts": {str(value): sum(row["bert_score"] == value for row in scores)
                              for value in range(4)},
        "database_access": False,
    }
    print("BENCHMARK_JSON=" + json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Benchmark failed ({type(error).__name__}).", file=sys.stderr)
        raise SystemExit(1)
