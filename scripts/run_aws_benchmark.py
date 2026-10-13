"""Launch one pinned, database-free Fargate benchmark and save its measurements."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import time
import uuid

from scripts.upload_benchmark_inputs import ROOT, command, save_report

SIZES = {"small": (1, 2), "large": (2, 4)}


def aws(service, operation, *arguments):
    return command(["aws", service, operation, "--region", "us-east-2", "--output", "json",
                    "--no-cli-pager", *arguments], timeout=30)


def validate_definition(definition, size, repository, pins, bucket):
    cpu, memory = SIZES[size]
    containers = definition.get("containerDefinitions", [])
    if definition.get("cpu") != str(cpu * 1024) or definition.get("memory") != str(memory * 1024):
        raise ValueError("Registered task size differs from the requested benchmark size.")
    if len(containers) != 1:
        raise ValueError("Benchmark must contain exactly one container.")
    container = containers[0]
    if container.get("name") != "worker" or container.get("command") != ["benchmark"] or container.get("entryPoint"):
        raise ValueError("Task does not run the expected benchmark entrypoint.")
    if container.get("image") != repository + "@sha256:" + pins["image_digest"]:
        raise ValueError("Task image differs from the pinned image.")
    environment = {row["name"]: row["value"] for row in container.get("environment", [])}
    if container.get("secrets") or any("DATABASE" in name or "SUPABASE" in name for name in environment):
        raise ValueError("Benchmark task must not receive database credentials.")
    expected = {"SAFETRIP_MODEL_S3_BUCKET": bucket, "SAFETRIP_BENCHMARK_S3_BUCKET": bucket,
                "SAFETRIP_MODEL_S3_KEY": pins["model_s3_key"],
                "SAFETRIP_MODEL_S3_VERSION_ID": pins["model_s3_version_id"],
                "SAFETRIP_MODEL_S3_SHA256": pins["model_archive_sha256"],
                "SAFETRIP_BENCHMARK_S3_KEY": pins["benchmark_s3_key"],
                "SAFETRIP_BENCHMARK_S3_VERSION_ID": pins["benchmark_s3_version_id"],
                "SAFETRIP_BENCHMARK_SHA256": pins["benchmark_sha256"]}
    if any(environment.get(name) != value for name, value in expected.items()):
        raise ValueError("Task S3 versions, keys, or checksums differ from the pinned inputs.")
    if container.get("logConfiguration", {}).get("options", {}).get("awslogs-group") != "/safetrip-iq/worker":
        raise ValueError("Task log destination differs from the expected benchmark log group.")


def timestamp(value):
    if isinstance(value, (int, float)):
        return float(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def interval(task, start, end):
    return round(max(0, timestamp(task[end]) - timestamp(task[start])), 3) if task.get(start) and task.get(end) else None


def estimated_cost(task, size):
    duration = interval(task, "pullStartedAt", "stoppedAt")
    address_duration = interval(task, "createdAt", "stoppedAt")
    if duration is None or address_duration is None:
        return None
    cpu, memory = SIZES[size]
    billed_seconds = max(60, math.ceil(duration))
    # Approximate IPv4 duration with creation-to-stop; exact ENI lifetime can differ.
    ipv4_seconds = max(60, math.ceil(address_duration))
    compute = billed_seconds / 3600 * (cpu * 0.04048 + memory * 0.004445)
    ipv4 = ipv4_seconds / 3600 * 0.005
    return {"compute_usd": round(compute, 6), "public_ipv4_usd": round(ipv4, 6),
            "total_compute_and_ipv4_usd": round(compute + ipv4, 6),
            "billed_compute_seconds": billed_seconds, "estimated_ipv4_seconds": ipv4_seconds,
            "rates": {"vcpu_hour_usd": 0.04048, "gib_hour_usd": 0.004445, "ipv4_hour_usd": 0.005},
            "limitations": "Ohio Linux x86 on-demand estimate; excludes storage, requests, logs, transfer, taxes, and credits. IPv4 lifetime is approximated. Confirm actual gross usage in Billing."}


def describe(cluster, arn):
    result = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", arn)
    if result.get("failures") or len(result.get("tasks", [])) != 1:
        raise RuntimeError("Cannot locate the benchmark task. Inspect its saved ARN in the ECS console.")
    return result["tasks"][0]


def stop_task(cluster, arn):
    aws("ecs", "stop-task", "--cluster", cluster, "--task", arn,
        "--reason", "SafeTrip benchmark watchdog or interruption")


def wait_for_stop(cluster, arn, report, path, timeout_minutes):
    deadline = timestamp(report["requested_at_utc"]) + timeout_minutes * 60
    previous = None
    stopped = False
    try:
        while True:
            task = describe(cluster, arn)
            report["last_status"] = task["lastStatus"]
            save_report(path, report)
            if task["lastStatus"] != previous:
                print(f"Task status: {task['lastStatus']}", flush=True)
                previous = task["lastStatus"]
            if task["lastStatus"] == "STOPPED":
                stopped = True
                return task
            if time.time() >= deadline:
                raise TimeoutError("Benchmark exceeded its runtime limit.")
            time.sleep(10)
    finally:
        if not stopped:
            try:
                stop_task(cluster, arn)
                report["stop_requested"] = True
                print("Stop requested for the unfinished task. Confirm STOPPED in the ECS console.", flush=True)
            except Exception:
                report["manual_stop_required"] = True
                print("Unable to request a stop. Stop the saved task in the ECS console; it may still be running.", flush=True)
            save_report(path, report)


def log_reports(task):
    task_id = task["taskArn"].rsplit("/", 1)[1]
    for attempt in range(12):
        try:
            logs = aws("logs", "get-log-events", "--log-group-name", "/safetrip-iq/worker",
                       "--log-stream-name", "benchmark/worker/" + task_id,
                       "--start-from-head", "--no-paginate", "--limit", "10000")
        except RuntimeError as error:
            if "ResourceNotFoundException" not in str(error):
                raise
            logs = {"events": []}
        records = {}
        for event in logs.get("events", []):
            for prefix, key in (("MODEL_BOOTSTRAP_JSON=", "model_bootstrap"), ("BENCHMARK_JSON=", "inference")):
                if event["message"].startswith(prefix):
                    records[key] = json.loads(event["message"][len(prefix):])
        if len(records) == 2:
            return records
        if attempt < 11:
            time.sleep(5)
    raise RuntimeError("Task stopped but complete benchmark metrics are not available. Inspect its CloudWatch log stream; rerun this command to retrieve metrics without relaunching.")


def validate_metrics(metrics, pins, inputs):
    bootstrap, inference = metrics["model_bootstrap"], metrics["inference"]
    if bootstrap.get("model_s3_version_id") != pins["model_s3_version_id"] or bootstrap.get("model_archive_sha256") != pins["model_archive_sha256"]:
        raise ValueError("Bootstrap metrics do not match the pinned model artifact.")
    if (inference.get("database_access") is not False or inference.get("input_sha256") != pins["benchmark_sha256"]
            or inference.get("model_version") != inputs["model_version"]
            or inference.get("model_s3_version_id") != pins["model_s3_version_id"]
            or inference.get("input_rows") != inputs["benchmark_rows"]):
        raise ValueError("Inference metrics do not match the expected benchmark provenance.")
    counts = inference.get("prediction_counts", {})
    if set(counts) != {"0", "1", "2", "3"} or any(type(value) is not int or value < 0 for value in counts.values()) or sum(counts.values()) != inputs["benchmark_rows"]:
        raise ValueError("Prediction counts are incomplete or invalid.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=SIZES, required=True)
    parser.add_argument("--report", help="New ignored report path; reuse it to resume the same task.")
    parser.add_argument("--timeout-minutes", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.timeout_minutes <= 30:
        parser.error("--timeout-minutes must be between 1 and 30")
    path = ROOT / (args.report or f".local/aws/benchmark-{args.size}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    outputs = command(["terraform", "-chdir=infra/terraform", "output", "-json"], timeout=30)
    outputs = {name: row["value"] for name, row in outputs.items()}
    pins = json.loads((ROOT / "infra/terraform/benchmark.auto.tfvars.json").read_text())
    inputs = json.loads((ROOT / ".local/aws/benchmark-inputs.json").read_text())
    report = {"size": args.size, "pins": pins, "cluster": outputs["ecs_cluster"],
              "task_definition": outputs["benchmark_task_arns"][args.size],
              "requested_at_utc": datetime.now(timezone.utc).isoformat(),
              "client_token": str(uuid.uuid4()), "complete": False}
    if path.exists():
        previous = json.loads(path.read_text())
        if any(previous.get(name) != report[name] for name in ("size", "pins", "cluster", "task_definition")):
            raise ValueError("Existing report refers to different task inputs; choose a new --report path.")
        report = previous
        if report.get("complete"):
            print(f"Benchmark already complete: {path.relative_to(ROOT)}. No new task started.")
            return 0
    identity = aws("sts", "get-caller-identity")
    if identity["Account"] != outputs["ecr_repository_url"].split(".", 1)[0]:
        raise ValueError("Authenticated AWS account differs from the Terraform account.")
    definition = aws("ecs", "describe-task-definition", "--task-definition", report["task_definition"])["taskDefinition"]
    validate_definition(definition, args.size, outputs["ecr_repository_url"], pins, outputs["model_bucket"])
    save_report(path, report)
    if not report.get("task_arn"):
        print(f"Launching one {args.size} benchmark ({SIZES[args.size][0]} vCPU / {SIZES[args.size][1]} GiB)...", flush=True)
        network = {"awsvpcConfiguration": {"subnets": [outputs["subnet_id"]],
                    "securityGroups": [outputs["security_group_id"]], "assignPublicIp": "ENABLED"}}
        result = aws("ecs", "run-task", "--cluster", report["cluster"], "--task-definition", report["task_definition"],
                     "--launch-type", "FARGATE", "--platform-version", "1.4.0", "--count", "1",
                     "--client-token", report["client_token"], "--network-configuration", json.dumps(network))
        if result.get("failures") or len(result.get("tasks", [])) != 1:
            raise RuntimeError("ECS could not launch the benchmark task. Inspect ECS capacity and permissions.")
        report["task_arn"] = result["tasks"][0]["taskArn"]
        save_report(path, report)
    task = wait_for_stop(report["cluster"], report["task_arn"], report, path, args.timeout_minutes)
    report.update(task_timestamps={name: task.get(name) for name in ("createdAt", "pullStartedAt", "pullStoppedAt", "startedAt", "stoppedAt")},
                  estimated_cost=estimated_cost(task, args.size),
                  image_pull_seconds=interval(task, "pullStartedAt", "pullStoppedAt"),
                  pull_to_stop_seconds=interval(task, "pullStartedAt", "stoppedAt"),
                  stop_code=task.get("stopCode"),
                  container_exit_codes=[row.get("exitCode") for row in task.get("containers", [])])
    save_report(path, report)
    if report["container_exit_codes"] != [0]:
        raise RuntimeError(f"Benchmark task stopped without success ({report['stop_code']}); check its CloudWatch log stream. No new task will launch when resuming this report.")
    metrics = log_reports(task)
    validate_metrics(metrics, pins, inputs)
    report.update(metrics, complete=True)
    save_report(path, report)
    print(f"Benchmark complete. Report: {path.relative_to(ROOT)}")
    print(json.dumps({"size": args.size, "pull_to_stop_seconds": report["pull_to_stop_seconds"],
                      "model_bootstrap_seconds": metrics["model_bootstrap"]["model_bootstrap_seconds"],
                      "inference_seconds": metrics["inference"]["inference_seconds"],
                      "peak_process_rss_bytes": metrics["inference"]["peak_process_rss_bytes"],
                      "estimated_cost": report["estimated_cost"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, KeyError, TimeoutError, subprocess.TimeoutExpired) as error:
        print(f"Benchmark stopped: {error}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("Benchmark interrupted; check the saved report and task stop status.")
        raise SystemExit(1)
