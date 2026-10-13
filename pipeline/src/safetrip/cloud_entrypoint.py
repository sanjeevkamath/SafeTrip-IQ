"""Prepare immutable cloud artifacts, then run the normal SafeTrip CLI."""
import json
import os
import sys


def main():
    from safetrip.inference.s3_checkpoint import bootstrap_from_environment
    try:
        report = bootstrap_from_environment()
        if report is not None:
            print("MODEL_BOOTSTRAP_JSON=" + json.dumps(report, sort_keys=True), flush=True)
    except Exception as error:
        # SDK exception strings can contain request details. Do not print them.
        print(f"Model bootstrap failed ({type(error).__name__}).", file=sys.stderr)
        return 1
    if sys.argv[1:] == ["benchmark"]:
        from safetrip.cloud_benchmark import main as benchmark
        try:
            return benchmark()
        except Exception as error:
            print(f"Benchmark failed ({type(error).__name__}).", file=sys.stderr)
            return 1
    os.execvp("safetrip", ["safetrip", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
